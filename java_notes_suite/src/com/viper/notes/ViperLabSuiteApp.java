package com.viper.notes;

import javax.swing.BorderFactory;
import javax.swing.JButton;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.SwingUtilities;
import javax.swing.Timer;
import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.Desktop;
import java.awt.Dimension;
import java.awt.Font;
import java.awt.GridLayout;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;

public class ViperLabSuiteApp {
    private static final String APP_VERSION = "0.3.0-rolling-triplet-proof";
    private static final String URL = "http://127.0.0.1:18181";
    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(2))
            .build();

    private final JTextArea output = new JTextArea();
    private final JLabel status = new JLabel("starting");

    public static void main(String[] args) {
        if (!isAlive()) {
            Thread serverThread = new Thread(() -> {
                try {
                    ViperLabSuiteServer.main(new String[0]);
                } catch (Exception e) {
                    System.err.println("VIPER SDK server start failed: " + e.getMessage());
                }
            }, "viper-java-sdk-server");
            serverThread.setDaemon(false);
            serverThread.start();
        }
        SwingUtilities.invokeLater(() -> new ViperLabSuiteApp().show());
    }

    private void show() {
        JFrame frame = new JFrame("VIPER Java SDK");
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setMinimumSize(new Dimension(880, 560));

        JPanel root = new JPanel(new BorderLayout(10, 10));
        root.setBackground(new Color(13, 17, 23));
        root.setBorder(BorderFactory.createEmptyBorder(12, 12, 12, 12));

        JLabel title = new JLabel("VIPER Java SDK Standalone v" + APP_VERSION);
        title.setForeground(new Color(240, 246, 252));
        title.setFont(new Font("Consolas", Font.BOLD, 18));
        status.setForeground(new Color(139, 148, 158));
        status.setFont(new Font("Consolas", Font.PLAIN, 12));

        JPanel header = new JPanel(new BorderLayout());
        header.setOpaque(false);
        header.add(title, BorderLayout.WEST);
        header.add(status, BorderLayout.EAST);

        JPanel buttons = new JPanel(new GridLayout(2, 3, 8, 8));
        buttons.setOpaque(false);
        buttons.add(button("Open SDK", this::openSdk));
        buttons.add(button("Health", () -> print(get(URL + "/health"))));
        buttons.add(button("State", () -> print(get(URL + "/api/state"))));
        buttons.add(button("Benchmarks", () -> print(get(URL + "/api/benchmarks?limit=20"))));
        buttons.add(button("Capture Benchmark", this::captureBenchmark));
        buttons.add(button("ASCII Epoch Queue", () -> print(get(URL + "/api/ascii-epochs?limit=20"))));

        output.setEditable(false);
        output.setBackground(new Color(1, 4, 9));
        output.setForeground(new Color(210, 168, 255));
        output.setCaretColor(new Color(201, 209, 217));
        output.setFont(new Font("Consolas", Font.PLAIN, 12));
        output.setLineWrap(true);
        output.setWrapStyleWord(true);
        output.setText("Ready. The full themed SDK is available at " + URL);

        JScrollPane scroll = new JScrollPane(output);
        scroll.setBorder(BorderFactory.createLineBorder(new Color(48, 54, 61)));

        root.add(header, BorderLayout.NORTH);
        root.add(buttons, BorderLayout.CENTER);
        root.add(scroll, BorderLayout.SOUTH);

        frame.setContentPane(root);
        frame.pack();
        frame.setLocationRelativeTo(null);
        frame.setVisible(true);

        Timer timer = new Timer(5000, e -> refreshStatus());
        timer.setInitialDelay(250);
        timer.start();
    }

    private JButton button(String label, Runnable action) {
        JButton button = new JButton(label);
        button.setFocusPainted(false);
        button.setBackground(new Color(22, 27, 34));
        button.setForeground(new Color(201, 209, 217));
        button.setBorder(BorderFactory.createLineBorder(new Color(48, 54, 61)));
        button.setFont(new Font("Consolas", Font.PLAIN, 13));
        button.addActionListener(e -> action.run());
        return button;
    }

    private void openSdk() {
        try {
            if (Desktop.isDesktopSupported()) {
                Desktop.getDesktop().browse(URI.create(URL));
                print("Opened " + URL);
                return;
            }
        } catch (Exception e) {
            print("Open failed: " + e.getMessage());
        }
        print("Open manually: " + URL);
    }

    private void captureBenchmark() {
        String body = "{\"reason\":\"standalone_app\",\"timestamp\":\"" + Instant.now() + "\"}";
        print(post(URL + "/api/benchmark-snapshot", body));
    }

    private void refreshStatus() {
        boolean alive = isAlive();
        status.setText(alive ? "live " + URL : "waiting for " + URL);
        status.setForeground(alive ? new Color(63, 185, 80) : new Color(248, 81, 73));
    }

    private void print(String text) {
        output.setText(text == null || text.isBlank() ? "(empty)" : text);
        output.setCaretPosition(0);
    }

    private static boolean isAlive() {
        return get(URL + "/health").contains("\"status\":\"ok\"") || get(URL + "/health").contains("\"status\": \"ok\"");
    }

    private static String get(String url) {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(4))
                    .GET()
                    .build();
            return HTTP.send(request, HttpResponse.BodyHandlers.ofString()).body();
        } catch (Exception e) {
            return "REQUEST_ERROR: " + e.getMessage();
        }
    }

    private static String post(String url, String body) {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(url))
                    .timeout(Duration.ofSeconds(8))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(body))
                    .build();
            return HTTP.send(request, HttpResponse.BodyHandlers.ofString()).body();
        } catch (Exception e) {
            return "REQUEST_ERROR: " + e.getMessage();
        }
    }
}
