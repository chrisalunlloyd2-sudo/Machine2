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
import java.nio.file.Paths;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.net.http.HttpClient;
import java.time.Duration;
import java.time.LocalDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.Map;
import java.util.PriorityQueue;

/**
 * VIPER Step 120-122: Omni-Network Manifold (Java)
 * Serves the VIPER RISC 3D HUD, handles plain-English chat via House Inference,
 * and distributes SQLite FTS5 local data to Machine 1 (Aegis/Brute Foundry).
 * 
 * VIPER Step 125 (Phase 7): Concept Blending
 * VIPER Step 131 (Phase 7): Temporal Vectoring (Time-decay RAG)
 * VIPER Step 141/150 (Phase 8): Sentinel Shielding (Syntax & Danger Pre-compilers)
 */
public class OmniNetworkManifold {
    private static final int PORT = 8085;
    private static final String DB_PATH = "C:/Users/viper/VIPER_JAVA_RISC/java_notes_suite/data/local_knowledge.db";
    
    // Step 131: RAM Cache for semantic embeddings now tracks Age!
    static class VectorEntry {
        float[] vector;
        long ageDays;
        
        VectorEntry(float[] vector, long ageDays) {
            this.vector = vector;
            this.ageDays = ageDays;
        }
    }
    
    private static final Map<String, VectorEntry> vectorCache = new HashMap<>();

    public static void main(String[] args) throws Exception {
        System.out.println("=== INITIALIZING OMNI-NETWORK MANIFOLD (JAVA) ===");
        
        // Ensure JDBC driver is loaded
        Class.forName("org.sqlite.JDBC");
        
        // Step 121 & 131: Load Semantic Vector Cache into memory with Temporal data
        loadVectorCache();

        HttpServer server = HttpServer.create(new InetSocketAddress("0.0.0.0", PORT), 0);
        
        // 1. WebUI (RISC 3D HUD)
        server.createContext("/", new UIHandler());
        
        // 2. Chat API for the HUD (Queries Local DB -> House Inference -> User)
        server.createContext("/chat", new ChatHandler());
        
        // 3. Global Network Distribution API (For Machine 1: Aegis & Brute Foundry)
        server.createContext("/api/omniscient-query", new DataProviderHandler());
        
        // 4. Phase 8: Sentinel Shielding API (Validates generated code)
        server.createContext("/api/sentinel-check", new SentinelShieldHandler());
        
        // 5. Phase 8: Data Recovery Hook (Rollback API)
        server.createContext("/api/backups", new BackupListHandler());
        server.createContext("/api/rollback", new RollbackHandler());

        server.setExecutor(null);
        server.start();
        System.out.println("VIPER Omni-Network Manifold Online on Port " + PORT);
        System.out.println("Ready to serve Brute Foundry, Aegis, and local HUD.");
        
        // Keep the server running
        while (true) {
            Thread.sleep(10000);
        }
    }

    private static void loadVectorCache() {
        System.out.println("Loading Hyper-Dimensional Vector Cache into RAM (with Temporal Dimension)...");
        long start = System.currentTimeMillis();
        long nowEpoch = LocalDateTime.now().toEpochSecond(ZoneOffset.UTC);
        
        String url = "jdbc:sqlite:" + DB_PATH;
        try (Connection conn = DriverManager.getConnection(url)) {
            // Join to get last_modified for Temporal Vectoring
            String sql = "SELECT v.file_hash, v.vector_blob, f.last_modified " +
                         "FROM local_files_vectors v " +
                         "JOIN local_files f ON v.file_hash = f.file_hash";
            try (PreparedStatement pstmt = conn.prepareStatement(sql);
                 ResultSet rs = pstmt.executeQuery()) {
                while (rs.next()) {
                    String hash = rs.getString("file_hash");
                    if (hash == null) continue;
                    byte[] blob = rs.getBytes("vector_blob");
                    String lastModifiedStr = rs.getString("last_modified");
                    
                    long ageDays = 0;
                    if (lastModifiedStr != null) {
                        try {
                            // Strip microsecond precision if it exists
                            if (lastModifiedStr.contains(".")) {
                                lastModifiedStr = lastModifiedStr.substring(0, lastModifiedStr.indexOf("."));
                            }
                            LocalDateTime ldt = LocalDateTime.parse(lastModifiedStr, DateTimeFormatter.ISO_LOCAL_DATE_TIME);
                            long fileEpoch = ldt.toEpochSecond(ZoneOffset.UTC);
                            ageDays = (nowEpoch - fileEpoch) / (60 * 60 * 24);
                            if (ageDays < 0) ageDays = 0;
                        } catch (Exception e) {
                            // ignore parse errors, default to 0
                        }
                    }
                    
                    vectorCache.put(hash, new VectorEntry(unpackVector(blob), ageDays));
                }
            }
        } catch (Exception e) {
            System.err.println("Failed to load vector cache: " + e.getMessage());
        }
        long ms = System.currentTimeMillis() - start;
        System.out.println("Loaded " + vectorCache.size() + " semantic temporal vectors in " + ms + "ms.");
    }

    static class UIHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            try {
                Path uiPath = Paths.get("C:/Users/viper/VIPER_JAVA_RISC/public/index.html");
                String html = Files.readString(uiPath, StandardCharsets.UTF_8);
                
                html = html.replace("http://127.0.0.1:11436/api/real-chat/predict", "http://127.0.0.1:8085/chat");
                html = html.replace("http://127.0.0.1:5000/chat", "http://127.0.0.1:8085/chat");

                byte[] response = html.getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "text/html; charset=UTF-8");
                exchange.sendResponseHeaders(200, response.length);
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(response);
                }
            } catch (Exception e) {
                String error = "Error loading UI: " + e.getMessage();
                exchange.sendResponseHeaders(500, error.length());
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(error.getBytes());
                }
            }
        }
    }

    static class ChatHandler implements HttpHandler {
        private final HttpClient httpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();

        @Override
        public void handle(HttpExchange exchange) throws IOException {
            exchange.getResponseHeaders().add("Access-Control-Allow-Origin", "*");
            exchange.getResponseHeaders().add("Access-Control-Allow-Headers", "Content-Type");
            
            if ("OPTIONS".equalsIgnoreCase(exchange.getRequestMethod())) {
                exchange.sendResponseHeaders(204, -1);
                return;
            }

            try {
                String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
                String prompt = "Hello";
                if (body.contains("\"message\"")) prompt = body.split("\"message\"\\s*:\\s*\"")[1].split("\"")[0];
                else if (body.contains("\"prompt\"")) prompt = body.split("\"prompt\"\\s*:\\s*\"")[1].split("\"")[0];
                
                // Query local LLM Karoo GP on port 11435
                String systemPrompt = "You are the Karoo GP autonomous strategist agent.";
                String requestBody = "{\"prompt\":\"" + escapeJson(prompt) + "\",\"system\":\"" + escapeJson(systemPrompt) + "\",\"route\":\"chat\"}";
                
                java.net.http.HttpRequest request = java.net.http.HttpRequest.newBuilder()
                        .uri(java.net.URI.create("http://127.0.0.1:11435/api/generate"))
                        .timeout(Duration.ofSeconds(12))
                        .header("Content-Type", "application/json")
                        .POST(java.net.http.HttpRequest.BodyPublishers.ofString(requestBody))
                        .build();
                        
                String responseBody;
                try {
                    java.net.http.HttpResponse<String> response = httpClient.send(request, java.net.http.HttpResponse.BodyHandlers.ofString());
                    responseBody = response.body();
                } catch (Exception ex) {
                    // Fallback to local DB semantic search if LLM times out or is busy
                    String context = semanticVectorSearch(prompt);
                    responseBody = "{\"response\": \"[FALLBACK] Axiomatic temporal alignment complete: " + escapeJson(context) + "\"}";
                }
                
                byte[] responseBytes = responseBody.getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json; charset=UTF-8");
                exchange.sendResponseHeaders(200, responseBytes.length);
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(responseBytes);
                }
            } catch (Exception e) {
                String err = "{\"response\": \"Logic Breach: " + escapeJson(e.getMessage()) + "\"}";
                exchange.sendResponseHeaders(500, err.length());
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(err.getBytes());
                }
            }
        }
    }

    static class DataProviderHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            exchange.getResponseHeaders().add("Access-Control-Allow-Origin", "*");
            try {
                String query = exchange.getRequestURI().getQuery();
                String searchTerm = "viper";
                boolean useVector = false;
                if (query != null) {
                    for (String param : query.split("&")) {
                        if (param.startsWith("q=")) searchTerm = param.split("=")[1];
                        if (param.equals("vector=true")) useVector = true;
                    }
                }
                
                String context = useVector ? semanticVectorSearch(searchTerm) : queryLocalKnowledgeFTS(searchTerm);
                String jsonResponse = "{\"status\": \"success\", \"data\": \"" + escapeJson(context) + "\"}";
                byte[] responseBytes = jsonResponse.getBytes(StandardCharsets.UTF_8);
                
                exchange.getResponseHeaders().set("Content-Type", "application/json; charset=UTF-8");
                exchange.sendResponseHeaders(200, responseBytes.length);
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(responseBytes);
                }
            } catch (Exception e) {
                String err = "{\"status\": \"error\", \"message\": \"" + escapeJson(e.getMessage()) + "\"}";
                exchange.sendResponseHeaders(500, err.length());
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(err.getBytes());
                }
            }
        }
    }

    // Phase 8: Data Recovery Hook - List Backups
    static class BackupListHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            exchange.getResponseHeaders().add("Access-Control-Allow-Origin", "*");
            try {
                Path dir = Paths.get("C:/Users/viper/VIPER_JAVA_RISC/java_notes_suite/data");
                StringBuilder sb = new StringBuilder("[");
                Files.list(dir).filter(p -> p.toString().endsWith(".backup") || p.toString().endsWith(".zip")).forEach(p -> {
                    sb.append("\"").append(p.getFileName().toString()).append("\",");
                });
                if (sb.length() > 1) sb.setLength(sb.length() - 1);
                sb.append("]");
                
                String jsonResponse = "{\"status\": \"success\", \"backups\": " + sb.toString() + "}";
                byte[] responseBytes = jsonResponse.getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json; charset=UTF-8");
                exchange.sendResponseHeaders(200, responseBytes.length);
                try (OutputStream os = exchange.getResponseBody()) { os.write(responseBytes); }
            } catch (Exception e) {
                String err = "{\"status\": \"error\"}";
                exchange.sendResponseHeaders(500, err.length());
                try (OutputStream os = exchange.getResponseBody()) { os.write(err.getBytes()); }
            }
        }
    }

    // Phase 8: Data Recovery Hook - Execute Rollback
    static class RollbackHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            exchange.getResponseHeaders().add("Access-Control-Allow-Origin", "*");
            try {
                String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
                String filename = "Unknown";
                if (body.contains("\"filename\"")) {
                    filename = body.split("\"filename\"\\s*:\\s*\"")[1].split("\"")[0];
                }
                
                // Execute PowerShell to restore
                String cmd = "powershell -Command \"Copy-Item -Path 'C:\\Users\\viper\\VIPER_JAVA_RISC\\java_notes_suite\\data\\" + filename + "' -Destination 'C:\\Users\\viper\\VIPER_JAVA_RISC\\java_notes_suite\\data\\local_knowledge.db' -Force\"";
                Runtime.getRuntime().exec(cmd);
                
                String jsonResponse = "{\"status\": \"success\", \"message\": \"Rollback initiated for " + escapeJson(filename) + "\"}";
                byte[] responseBytes = jsonResponse.getBytes(StandardCharsets.UTF_8);
                exchange.getResponseHeaders().set("Content-Type", "application/json; charset=UTF-8");
                exchange.sendResponseHeaders(200, responseBytes.length);
                try (OutputStream os = exchange.getResponseBody()) { os.write(responseBytes); }
            } catch (Exception e) {
                String err = "{\"status\": \"error\"}";
                exchange.sendResponseHeaders(500, err.length());
                try (OutputStream os = exchange.getResponseBody()) { os.write(err.getBytes()); }
            }
        }
    }

    // Step 141 & 150: Phase 8 Sentinel Shielding Endpoint
    static class SentinelShieldHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange exchange) throws IOException {
            exchange.getResponseHeaders().add("Access-Control-Allow-Origin", "*");
            try {
                String body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
                String code = "Unknown";
                if (body.contains("\"code\"")) {
                    code = body.split("\"code\"\\s*:\\s*\"")[1].split("\"")[0];
                }
                
                // Lightning Fast Danger Scans
                boolean safe = true;
                StringBuilder reason = new StringBuilder();
                
                String lowerCode = code.toLowerCase();
                
                // Step 141: Infinite Loop Detection
                if (lowerCode.contains("while($true)") || lowerCode.contains("while(true)") || lowerCode.contains("while (true)")) {
                    safe = false;
                    reason.append("PHASE 8 VIOLATION: Unbounded while(true) loop detected. ");
                }
                
                // Step 150: Dangerous Commands
                if (lowerCode.contains("rm -rf") || lowerCode.contains("drop table")) {
                    safe = false;
                    reason.append("PHASE 8 VIOLATION: Lethal deletion command detected. ");
                }
                
                String jsonResponse = "{\"safe\": " + safe + ", \"reason\": \"" + escapeJson(reason.toString()) + "\"}";
                byte[] responseBytes = jsonResponse.getBytes(StandardCharsets.UTF_8);
                
                exchange.getResponseHeaders().set("Content-Type", "application/json; charset=UTF-8");
                exchange.sendResponseHeaders(200, responseBytes.length);
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(responseBytes);
                }
            } catch (Exception e) {
                String err = "{\"safe\": false, \"reason\": \"Sentinel Parse Error: " + escapeJson(e.getMessage()) + "\"}";
                exchange.sendResponseHeaders(500, err.length());
                try (OutputStream os = exchange.getResponseBody()) {
                    os.write(err.getBytes());
                }
            }
        }
    }

    private static String queryLocalKnowledgeFTS(String keyword) {
        StringBuilder result = new StringBuilder();
        String url = "jdbc:sqlite:" + DB_PATH;
        try (Connection conn = DriverManager.getConnection(url)) {
            String sql = "SELECT file_path, snippet(local_files_fts, -1, '[', ']', '...', 64) as snip FROM local_files_fts WHERE local_files_fts MATCH ? LIMIT 3";
            try (PreparedStatement pstmt = conn.prepareStatement(sql)) {
                pstmt.setString(1, keyword);
                ResultSet rs = pstmt.executeQuery();
                while (rs.next()) {
                    String path = rs.getString("file_path");
                    String snip = rs.getString("snip");
                    if (path != null) result.append("File: ").append(path).append("\\n");
                    if (snip != null) result.append("Context: ").append(snip).append("\\n\\n");
                }
            }
            if (result.length() == 0) return "No exact matches found for: " + keyword;
        } catch (Exception e) {
            return "DB Error: " + e.getMessage();
        }
        return result.toString().replace("\\n", " ");
    }

    // Step 131: Temporal Vectoring Integration
    private static String semanticVectorSearch(String query) {
        if (vectorCache.isEmpty()) return queryLocalKnowledgeFTS(query);

        float[] queryVector;
        
        // Step 125: Concept Blending
        if (query.toLowerCase().contains(" and ")) {
            String[] concepts = query.toLowerCase().split(" and ");
            float[] vec1 = generatePseudoEmbedding(concepts[0].trim());
            float[] vec2 = generatePseudoEmbedding(concepts[1].trim());
            queryVector = blendVectors(vec1, vec2);
        } else {
            queryVector = generatePseudoEmbedding(query);
        }
        
        PriorityQueue<Map.Entry<String, Double>> pq = new PriorityQueue<>(
            (a, b) -> Double.compare(a.getValue(), b.getValue())
        );
        
        for (Map.Entry<String, VectorEntry> entry : vectorCache.entrySet()) {
            double baseSim = cosineSimilarity(queryVector, entry.getValue().vector);
            
            // Step 131: Temporal Decay (Penalize older vectors by 5% per 100 days)
            // e^{-lambda * t} decay
            double decayFactor = Math.exp(-entry.getValue().ageDays / 2000.0);
            double temporalScore = baseSim * decayFactor;
            
            pq.offer(java.util.Map.entry(entry.getKey(), temporalScore));
            if (pq.size() > 3) pq.poll();
        }
        
        if (pq.isEmpty()) return "No semantic matches found.";
        
        StringBuilder result = new StringBuilder();
        String url = "jdbc:sqlite:" + DB_PATH;
        try (Connection conn = DriverManager.getConnection(url)) {
            String sql = "SELECT file_path, substr(content, 1, 300) as snip FROM local_files WHERE file_hash = ?";
            try (PreparedStatement pstmt = conn.prepareStatement(sql)) {
                while (!pq.isEmpty()) {
                    Map.Entry<String, Double> top = pq.poll();
                    if (top == null || top.getKey() == null) continue;
                    pstmt.setString(1, top.getKey());
                    ResultSet rs = pstmt.executeQuery();
                    if (rs.next()) {
                        String path = rs.getString("file_path");
                        String snip = rs.getString("snip");
                        if (path != null && snip != null) {
                            result.append(String.format("[Score: %.2f] ", top.getValue()));
                            result.append("File: ").append(path).append("\\n");
                            result.append("Context: ").append(snip).append("...\\n\\n");
                        }
                    }
                }
            }
        } catch (Exception e) {
            return "Semantic Search DB Error: " + e.getMessage();
        }
        
        return result.toString().replace("\\n", " ");
    }
    
    public static float[] blendVectors(float[] v1, float[] v2) {
        float[] blended = new float[1536];
        if (v1 == null) v1 = new float[1536];
        if (v2 == null) v2 = new float[1536];
        for(int i = 0; i < 1536; i++) {
            float val1 = (i < v1.length) ? v1[i] : 0.0f;
            float val2 = (i < v2.length) ? v2[i] : 0.0f;
            blended[i] = (val1 + val2) / 2.0f;
        }
        return blended;
    }

    public static float[] unpackVector(byte[] blob) {
        float[] vector = new float[1536];
        if (blob == null) {
            System.err.println("[VIPER-SHIELD] Null vector blob detected. Initializing with zeroes.");
            return vector;
        }
        int expectedBytes = 1536 * 4;
        if (blob.length < expectedBytes) {
            System.err.println("[VIPER-SHIELD] Underflow vector blob detected: size " + blob.length + " bytes. Padding with zeroes.");
            java.nio.ByteBuffer buffer = java.nio.ByteBuffer.wrap(blob).order(java.nio.ByteOrder.LITTLE_ENDIAN);
            int availableFloats = blob.length / 4;
            for (int i = 0; i < availableFloats && i < 1536; i++) {
                vector[i] = buffer.getFloat();
            }
            return vector;
        }
        java.nio.ByteBuffer buffer = java.nio.ByteBuffer.wrap(blob).order(java.nio.ByteOrder.LITTLE_ENDIAN);
        for (int i = 0; i < 1536; i++) {
            if (buffer.remaining() >= 4) {
                vector[i] = buffer.getFloat();
            } else {
                vector[i] = 0.0f;
            }
        }
        return vector;
    }

    public static float[] generatePseudoEmbedding(String text) {
        try {
            java.security.MessageDigest md = java.security.MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(text.getBytes(StandardCharsets.UTF_8));
            float[] vector = new float[1536];
            for (int i = 0; i < 1536; i++) {
                int b = hash[i % hash.length] & 0xFF;
                vector[i] = (float) (b / 127.5 - 1.0);
            }
            return vector;
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    public static double cosineSimilarity(float[] vectorA, float[] vectorB) {
        if (vectorA == null || vectorB == null) return 0.0;
        double dotProduct = 0.0, normA = 0.0, normB = 0.0;
        int len = Math.min(vectorA.length, vectorB.length);
        for (int i = 0; i < len; i++) {
            dotProduct += vectorA[i] * vectorB[i];
            normA += vectorA[i] * vectorA[i];
            normB += vectorB[i] * vectorB[i];
        }
        for (int i = len; i < vectorA.length; i++) {
            normA += vectorA[i] * vectorA[i];
        }
        for (int i = len; i < vectorB.length; i++) {
            normB += vectorB[i] * vectorB[i];
        }
        if (normA == 0.0 || normB == 0.0) return 0.0;
        return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
    }
    
    private static String escapeJson(String raw) {
        if (raw == null) return "";
        return raw.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r");
    }
}
