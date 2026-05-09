package com.viper.risc;

import com.sun.net.httpserver.HttpServer;
import com.sun.net.httpserver.HttpHandler;
import com.sun.net.httpserver.HttpExchange;

import java.io.IOException;
import java.io.OutputStream;
import java.io.InputStream;
import java.io.File;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.net.InetSocketAddress;
import java.security.MessageDigest;
import java.nio.charset.StandardCharsets;
import java.util.Date;

public class RiscServer {

    private static final int PORT = 8080;
    private static int loihiNeurons = 1000000;
    private static int rollingIndex = 0;

    public static void main(String[] args) throws IOException {
        System.out.println("🚀 INIT: VIPER RISC LAB (FULL JAVA ENVIRONMENT)");
        HttpServer server = HttpServer.create(new InetSocketAddress(PORT), 0);
        
        server.createContext("/", new UIHandler());
        server.createContext("/api/risc/export", new ExportHandler());
        server.createContext("/api/risc/deport", new DeportHandler());
        server.createContext("/api/loihi/neurons", new NeuronHandler());
        server.createContext("/api/blockchain/publish", new PublishHandler());
        server.createContext("/api/rolling", new RollingHandler());
        server.createContext("/api/loibi/predict", new PredictHandler());

        server.setExecutor(null);
        server.start();
        System.out.println("[SERVER] Listening on port " + PORT);
    }

    private static void logChunked(String message) {
        try {
            String timestamped = "[" + new Date().toString() + "] " + message + "\n";
            byte[] bytes = timestamped.getBytes(StandardCharsets.UTF_8);
            // 2KB chunking protocol
            int chunkSize = 2000;
            for (int i = 0; i < bytes.length; i += chunkSize) {
                int length = Math.min(bytes.length - i, chunkSize);
                byte[] chunk = new byte[length];
                System.arraycopy(bytes, i, chunk, 0, length);
                Files.write(Paths.get("VIPER_JAVA_RISC/system_log.txt"), chunk, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private static void enforceDelay() {
        try {
            Thread.sleep(5000); // 5s delay protocol
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static String sha256(String base) {
        try{
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(base.getBytes("UTF-8"));
            StringBuilder hexString = new StringBuilder();
            for (int i = 0; i < hash.length; i++) {
                String hex = Integer.toHexString(0xff & hash[i]);
                if(hex.length() == 1) hexString.append('0');
                hexString.append(hex);
            }
            return hexString.toString();
        } catch(Exception ex){
            throw new RuntimeException(ex);
        }
    }

    static class UIHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange t) throws IOException {
            File file = new File("VIPER_JAVA_RISC/public/index.html");
            if (file.exists()) {
                byte[] bytes = Files.readAllBytes(file.toPath());
                t.sendResponseHeaders(200, bytes.length);
                OutputStream os = t.getResponseBody();
                os.write(bytes);
                os.close();
            } else {
                String response = "404 (Not Found)\n";
                t.sendResponseHeaders(404, response.length());
                OutputStream os = t.getResponseBody();
                os.write(response.getBytes());
                os.close();
            }
        }
    }

    static class ExportHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange t) throws IOException {
            enforceDelay();
            String data = "RISC_EXPORT_PACKET_" + System.currentTimeMillis();
            String hash = sha256(data);
            String response = "{\"status\":\"ok\", \"hash\":\"" + hash + "\", \"data\":\"" + data + "\"}";
            logChunked("Exported SHA256 Packet: " + hash);
            
            t.getResponseHeaders().set("Content-Type", "application/json");
            t.sendResponseHeaders(200, response.getBytes().length);
            OutputStream os = t.getResponseBody();
            os.write(response.getBytes());
            os.close();
        }
    }

    static class DeportHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange t) throws IOException {
            enforceDelay();
            String response = "{\"status\":\"deported\", \"message\":\"Packet deported to RISC lab successfully\"}";
            logChunked("Deported packet back to RISC lab.");
            
            t.getResponseHeaders().set("Content-Type", "application/json");
            t.sendResponseHeaders(200, response.getBytes().length);
            OutputStream os = t.getResponseBody();
            os.write(response.getBytes());
            os.close();
        }
    }

    static class NeuronHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange t) throws IOException {
            loihiNeurons += (int)(Math.random() * 50); // Simulate neuron growth
            String response = "{\"neurons\":" + loihiNeurons + ", \"message\":\"Loihi twinning active. Karoo optimizing topology.\"}";
            logChunked("Neuron count requested. Current: " + loihiNeurons);
            
            t.getResponseHeaders().set("Content-Type", "application/json");
            t.sendResponseHeaders(200, response.getBytes().length);
            OutputStream os = t.getResponseBody();
            os.write(response.getBytes());
            os.close();
        }
    }

    static class PublishHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange t) throws IOException {
            enforceDelay();
            String response = "{\"status\":\"published\", \"ledger\":\"SHA-256 Blockchain Ledger Updated\"}";
            logChunked("Published Success DB via simulated Blockchain.");
            
            t.getResponseHeaders().set("Content-Type", "application/json");
            t.sendResponseHeaders(200, response.getBytes().length);
            OutputStream os = t.getResponseBody();
            os.write(response.getBytes());
            os.close();
        }
    }

    static class RollingHandler implements HttpHandler {
        @Override
        public void handle(HttpExchange t) throws IOException {
            rollingIndex++;
            String response = "{\"roll_id\":" + rollingIndex + ", \"data\":\"Perfect Info Lookup Recursive Response Phase " + rollingIndex + "\"}";
            logChunked("Served rolling response index: " + rollingIndex);
            
            t.getResponseHeaders().set("Content-Type", "application/json");
            t.sendResponseHeaders(200, response.getBytes().length);
            OutputStream os = t.getResponseBody();
            os.write(response.getBytes());
            os.close();
        }
    }
}
