package com.viper.notes;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public class ViperNotesServer {
    private static final int PORT = Integer.parseInt(System.getProperty("viper.notes.port", "8091"));
    private static final Path ROOT = Path.of("VIPER_JAVA_RISC", "java_notes_suite");
    private static final Path DATA = ROOT.resolve("data");
    private static final Path NOTES = DATA.resolve("notes.jsonl");
    private static final Path SCRIPTS = Path.of("VIPER_JAVA_RISC");

    public static void main(String[] args) throws Exception {
        Files.createDirectories(DATA);
        if (!Files.exists(NOTES)) {
            Files.writeString(NOTES, "", StandardCharsets.UTF_8);
        }
        HttpServer server = HttpServer.create(new InetSocketAddress(PORT), 0);
        server.createContext("/", new PageHandler());
        server.createContext("/api/notes", new NotesHandler());
        server.createContext("/api/scripts", new ScriptsHandler());
        server.setExecutor(null);
        server.start();
        System.out.println("VIPER Notes Dev Suite listening on http://127.0.0.1:" + PORT);
    }

    private static String sha256(String text) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(text.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : hash) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    private static void send(HttpExchange exchange, int status, String body, String contentType) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.getResponseHeaders().set("Content-Type", contentType + "; charset=utf-8");
        exchange.getResponseHeaders().set("Access-Control-Allow-Origin", "*");
        exchange.sendResponseHeaders(status, bytes.length);
        try (OutputStream os = exchange.getResponseBody()) {
            os.write(bytes);
        }
    }

    private static String escapeJson(String value) {
        return value.replace("\\", "\\\\").replace("\"", "\\\"").replace("\r", "\\r").replace("\n", "\\n");
    }

    static class PageHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if (!"GET".equals(exchange.getRequestMethod())) {
                send(exchange, 405, "method not allowed", "text/plain");
                return;
            }
            String html = """
                    <!doctype html>
                    <html lang="en">
                    <head>
                      <meta charset="utf-8">
                      <meta name="viewport" content="width=device-width, initial-scale=1">
                      <title>VIPER Notes Dev Suite</title>
                      <style>
                        body{margin:0;background:#020617;color:#dbeafe;font-family:Segoe UI,Arial,sans-serif}
                        main{max-width:980px;margin:0 auto;padding:18px}
                        h1{font-size:20px;color:#93c5fd;margin:0 0 14px}
                        section{border:1px solid rgba(56,189,248,.25);background:rgba(15,23,42,.72);padding:14px;margin:12px 0;border-radius:8px}
                        textarea,input{width:100%;box-sizing:border-box;background:#020617;color:#bae6fd;border:1px solid #38bdf8;border-radius:6px;padding:10px}
                        textarea{min-height:130px}
                        button{margin-top:8px;background:#06263a;color:#67e8f9;border:1px solid #38bdf8;border-radius:6px;padding:8px 12px;font-weight:700}
                        pre{white-space:pre-wrap;font-size:12px;color:#a7f3d0}
                        .muted{color:#94a3b8;font-size:12px}
                      </style>
                    </head>
                    <body>
                      <main>
                        <h1>VIPER Notes Dev Suite</h1>
                        <section>
                          <div class="muted">Hash-first notes. No deletes. Append-only local merge.</div>
                          <textarea id="note" placeholder="Note, TODO, script idea, host signal..."></textarea>
                          <button onclick="saveNote()">Save Note</button>
                        </section>
                        <section>
                          <h2>Recent Notes</h2>
                          <pre id="notes">loading...</pre>
                        </section>
                        <section>
                          <h2>Script Suite</h2>
                          <pre id="scripts">loading...</pre>
                        </section>
                      </main>
                      <script>
                        async function load(){
                          notes.textContent = JSON.stringify(await (await fetch('/api/notes')).json(), null, 2);
                          scripts.textContent = JSON.stringify(await (await fetch('/api/scripts')).json(), null, 2);
                        }
                        async function saveNote(){
                          const body = { text: note.value, source: 'java_notes_suite' };
                          await fetch('/api/notes', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
                          note.value='';
                          load();
                        }
                        load();
                      </script>
                    </body>
                    </html>
                    """;
            send(exchange, 200, html, "text/html");
        }
    }

    static class NotesHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            if ("GET".equals(exchange.getRequestMethod())) {
                List<String> lines = Files.exists(NOTES) ? Files.readAllLines(NOTES, StandardCharsets.UTF_8) : List.of();
                int start = Math.max(0, lines.size() - 50);
                send(exchange, 200, "{\"notes\":[" + String.join(",", lines.subList(start, lines.size())) + "]}", "application/json");
                return;
            }
            if ("POST".equals(exchange.getRequestMethod())) {
                String raw = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
                String hash = sha256(raw + Instant.now());
                String row = "{\"id\":\"NOTE_" + hash.substring(0, 12) + "\",\"timestamp\":\"" + Instant.now() + "\",\"sha256\":\"" + hash + "\",\"raw\":\"" + escapeJson(raw) + "\"}\n";
                Files.writeString(NOTES, row, StandardCharsets.UTF_8, java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND);
                send(exchange, 200, "{\"status\":\"saved\",\"sha256\":\"" + hash + "\"}", "application/json");
                return;
            }
            send(exchange, 405, "method not allowed", "text/plain");
        }
    }

    static class ScriptsHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            List<String> scripts = new ArrayList<>();
            if (Files.exists(SCRIPTS)) {
                try (var stream = Files.walk(SCRIPTS, 3)) {
                    stream.filter(Files::isRegularFile)
                            .filter(path -> path.toString().endsWith(".ps1") || path.toString().endsWith(".bat") || path.toString().endsWith(".py"))
                            .sorted(Comparator.comparing(Path::toString))
                            .limit(120)
                            .forEach(path -> scripts.add("\"" + escapeJson(SCRIPTS.relativize(path).toString()) + "\""));
                }
            }
            send(exchange, 200, "{\"scripts\":[" + String.join(",", scripts) + "]}", "application/json");
        }
    }
}
