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

    public boolean start() {
        try {
            ProcessBuilder pb = new ProcessBuilder(PYTHON, "-u", MOE_SERVER);
            pb.redirectErrorStream(false);
            process = pb.start();
            writer  = new BufferedWriter(new OutputStreamWriter(process.getOutputStream(), "UTF-8"));
            reader  = new BufferedReader(new InputStreamReader(process.getInputStream(),  "UTF-8"));

            pool.submit(this::readLoop);
            return true;
        } catch (Exception e) {
            System.err.println("[PythonBridge] Failed to start: " + e.getMessage());
            return false;
        }
    }

    public void send(String query) {
        send(query, null);
    }

    public void send(String query, String project) {
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
            if (responseCallback != null) {
                Platform.runLater(() -> responseCallback.accept("[Bridge error: " + e.getMessage() + "]"));
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
