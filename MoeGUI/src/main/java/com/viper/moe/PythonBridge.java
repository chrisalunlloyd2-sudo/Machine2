package com.viper.moe;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import javafx.application.Platform;

import java.io.*;
import java.util.Map;
import java.util.concurrent.*;
import java.util.function.Consumer;

/**
 * JSON-over-stdio bridge to Python Moe backend.
 * Each query is written as a JSON line to stdin; response arrives as JSON line on stdout.
 * Runs moe_server.py as a persistent child process.
 */
public class PythonBridge {

    private static final String MOE_SERVER = "C:\\Users\\viper\\gan-otg-db\\desktop_moe_orchestrator.py";
    private static final String PYTHON     = "C:\\Python314\\python.exe";

    private Process          process;
    private BufferedWriter   writer;
    private BufferedReader   reader;
    private final ObjectMapper mapper   = new ObjectMapper();
    private final ExecutorService pool  = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "moe-reader");
        t.setDaemon(true);
        return t;
    });
    private Consumer<String> responseCallback;
    private Consumer<String> tokenCallback;    // called for each streaming token

    public void setResponseCallback(Consumer<String> cb) {
        this.responseCallback = cb;
    }

    public void setTokenCallback(Consumer<String> cb) {
        this.tokenCallback = cb;
    }

    public synchronized boolean start() {
        try {
            ProcessBuilder pb = new ProcessBuilder(PYTHON, "-u", MOE_SERVER);
            pb.redirectErrorStream(false);
            process = pb.start();
            writer  = new BufferedWriter(new OutputStreamWriter(process.getOutputStream(), "UTF-8"));
            reader  = new BufferedReader(new InputStreamReader(process.getInputStream(),  "UTF-8"));

            drainStderr(process);
            pool.submit(this::readLoop);
            return true;
        } catch (Exception e) {
            System.err.println("[PythonBridge] Failed to start: " + e.getMessage());
            return false;
        }
    }

    /**
     * STDERR MUST BE READ OR THE CHILD CAN HANG FOREVER.
     *
     * redirectErrorStream(false) gives the child a separate stderr pipe, and
     * nothing here ever read it. That pipe has a small OS buffer (a few KB on
     * Windows); once it fills, the child BLOCKS on its next write to stderr and
     * never returns. The GUI then sits waiting for an answer from a process
     * that is alive, healthy and permanently stuck mid-write -- which looks
     * exactly like a slow model, so it would be waited on rather than
     * investigated.
     *
     * The orchestrator emits nothing on stderr at startup (measured: 0 bytes),
     * so this never bit on a clean run. It needed one Python warning or one
     * traceback during a five-day soak to arm itself.
     *
     * The lines are also worth keeping: stderr is where the Python side says
     * WHY it is about to die, and that was being discarded.
     */
    private void drainStderr(Process p) {
        Thread t = new Thread(() -> {
            try (BufferedReader er = new BufferedReader(
                    new InputStreamReader(p.getErrorStream(), "UTF-8"))) {
                String l;
                while ((l = er.readLine()) != null) {
                    System.err.println("[moe-py] " + l);
                }
            } catch (Exception ignored) {
                // The child exiting closes this stream; that is not an error.
            }
        }, "moe-stderr");
        t.setDaemon(true);
        t.start();
    }

    /** Is the Python child actually there? */
    public boolean isAlive() {
        return process != null && process.isAlive();
    }

    /**
     * Restart the child if it has died. Returns true if a bridge is available.
     *
     * THIS IS THE ACTUAL FIX for "The pipe is being closed". That string is
     * Windows' message for writing to a pipe whose far end is gone, and it was
     * being surfaced verbatim from send()'s catch block. The message was a
     * symptom; the defect is that ONE DEATH WAS PERMANENT. Nothing checked
     * liveness and nothing ever respawned, so after the child exited -- for any
     * reason at all -- every later query hit the same dead pipe and the only
     * cure was restarting the whole GUI by hand.
     *
     * Chris is on a phone. A desktop app that must be manually restarted to
     * recover is, from there, simply broken.
     */
    private synchronized boolean ensureAlive() {
        if (isAlive()) return true;
        try { if (writer != null) writer.close(); } catch (Exception ignored) {}
        try { if (process != null) process.destroyForcibly(); } catch (Exception ignored) {}
        System.err.println("[PythonBridge] child is gone -- restarting the bridge");
        boolean ok = start();
        if (ok && responseCallback != null) {
            Platform.runLater(() -> responseCallback.accept(
                    "[Moe bridge restarted -- the backend had exited. Resend that.]"));
        }
        return ok;
    }

    public void send(String query) {
        send(query, null);
    }

    public synchronized void send(String query, String project) {
        // Checked BEFORE the write, not after it fails. A dead pipe does not
        // always throw on the first write -- the bytes can land in a local
        // buffer and vanish -- so waiting for an exception can silently drop a
        // query rather than report it.
        if (!ensureAlive()) {
            if (responseCallback != null) {
                Platform.runLater(() -> responseCallback.accept(
                        "[Moe backend will not start. Check that " + PYTHON
                        + " and the orchestrator script both exist.]"));
            }
            return;
        }
        try {
            ObjectNode msg = mapper.createObjectNode();
            msg.put("query", query);
            if (project != null && !project.isEmpty()) {
                msg.put("project", project);
            }
            writer.write(mapper.writeValueAsString(msg));
            writer.newLine();
            writer.flush();
        } catch (Exception e) {
            // One retry: the child may have died between the check above and
            // this write. If a fresh bridge cannot take it either, say so in
            // words rather than passing on a Windows pipe message.
            if (ensureAlive()) {
                try {
                    ObjectNode msg = mapper.createObjectNode();
                    msg.put("query", query);
                    if (project != null && !project.isEmpty()) {
                        msg.put("project", project);
                    }
                    writer.write(mapper.writeValueAsString(msg));
                    writer.newLine();
                    writer.flush();
                    return;
                } catch (Exception ignored) {}
            }
            if (responseCallback != null) {
                Platform.runLater(() -> responseCallback.accept(
                        "[Moe backend is not responding: " + e.getMessage()
                        + ". The bridge was restarted; try again.]"));
            }
        }
    }

    private void readLoop() {
        try {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isBlank()) continue;
                try {
                    @SuppressWarnings("unchecked")
                    Map<String, Object> resp = mapper.readValue(line, Map.class);
                    boolean done  = Boolean.TRUE.equals(resp.get("done"));
                    String  token = (String) resp.get("token");
                    String  answer= (String) resp.get("answer");

                    if (token != null && tokenCallback != null) {
                        // Streaming token — append to live display
                        final String t = token;
                        Platform.runLater(() -> tokenCallback.accept(t));
                    }
                    if (done && answer != null && responseCallback != null) {
                        // Final answer — finalize the message bubble
                        final String a = answer;
                        Platform.runLater(() -> responseCallback.accept(a));
                    } else if (answer != null && !done && responseCallback != null) {
                        // Non-streaming answer (pipeline query, no tokens sent first)
                        final String a = answer;
                        Platform.runLater(() -> responseCallback.accept(a));
                    }
                } catch (Exception e) {
                    final String raw = line;
                    if (responseCallback != null) {
                        Platform.runLater(() -> responseCallback.accept(raw));
                    }
                }
            }
        } catch (IOException e) {
            if (responseCallback != null) {
                Platform.runLater(() -> responseCallback.accept("[Moe server disconnected]"));
            }
        }
    }

    public void shutdown() {
        try { writer.close(); } catch (Exception ignored) {}
        try { process.destroyForcibly(); } catch (Exception ignored) {}
        pool.shutdownNow();
    }
}
