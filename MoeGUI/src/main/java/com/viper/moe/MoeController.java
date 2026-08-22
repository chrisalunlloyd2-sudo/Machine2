package com.viper.moe;

import javafx.application.Platform;
import javafx.geometry.Insets;
import javafx.geometry.Orientation;
import javafx.scene.Parent;
import javafx.scene.chart.LineChart;
import javafx.scene.chart.NumberAxis;
import javafx.scene.chart.XYChart;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import javafx.scene.text.Font;
import javafx.scene.text.FontWeight;
import javafx.animation.KeyFrame;
import javafx.animation.Timeline;
import javafx.util.Duration;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Moe GUI — main layout controller.
 * Root: TabPane with "Swarm Orchestrator" and "Blueprint Tracker"
 * Swarm Orchestrator Tab: SplitPane(left=sidebar, center=SplitPane(left=chat+input, right=LineChart))
 * Blueprint Tracker Tab: ProgressBar, large completion Label, and VBox phases list
 */
public class MoeController {

    private final PythonBridge bridge     = new PythonBridge();
    private String selectedProject = null;
    private final ListView<DbStatus.ProjectItem> projectList = new ListView<>();
    private final VBox             chatBox      = new VBox(8);
    private final ScrollPane       chatScroll   = new ScrollPane(chatBox);
    private final TextField        inputField   = new TextField();
    private final Button           sendBtn      = new Button("SEND");
    private final VBox             dbStatusBox  = new VBox(4);
    private final Label            agentLabel   = new Label("Agent: ready");
    private final Label            bridgeStatus = new Label("● Moe offline");
    private Timeline               liveTimer;
    
    // Thinking bubble — shown while waiting for response
    private VBox                   thinkingBubble = null;
    private Label                  thinkingLabel  = null;
    private Timeline               thinkingTimer  = null;
    private final AtomicInteger    elapsedSecs    = new AtomicInteger(0);

    // Ship-to-notes: track last Moe response for one-click save
    private String                 lastMoeResponse  = null;
    private Button                 shipBtn;
    private ViperNotesController   notesController  = null;

    public void setNotesController(ViperNotesController nc) { this.notesController = nc; }

    static final String TELE_DB = "C:\\Viper\\databases\\telemetry\\telemetry.db";

    private static Connection openDb() throws Exception {
        Class.forName("org.sqlite.JDBC");
        return DriverManager.getConnection(
            "jdbc:sqlite:" + TELE_DB + "?busy_timeout=5000&journal_mode=WAL");
    }

    // Telemetry & Blueprint tracking components
    private final ProgressBar      blueprintProgressBar = new ProgressBar(0.0);
    private final Label            completionLabel      = new Label("0.0%");
    private final VBox             phasesContainer      = new VBox(10);
    
    private final XYChart.Series<Number, Number> cpuSeries = new XYChart.Series<>();
    private final XYChart.Series<Number, Number> ramSeries = new XYChart.Series<>();
    private final LineChart<Number, Number>      telemetryChart = createTelemetryChart();
    private int                    timeIndex            = 0;
    private final ObjectMapper     mapper               = new ObjectMapper();

    private LineChart<Number, Number> createTelemetryChart() {
        NumberAxis xAxis = new NumberAxis();
        NumberAxis yAxis = new NumberAxis(0, 100, 10);
        xAxis.setLabel("Time (s)");
        yAxis.setLabel("Usage %");
        LineChart<Number, Number> chart = new LineChart<>(xAxis, yAxis);
        chart.setTitle("Live Telemetry Visualizer");
        chart.setCreateSymbols(false);
        cpuSeries.setName("CPU Usage");
        ramSeries.setName("RAM Usage");
        chart.getData().add(cpuSeries);
        chart.getData().add(ramSeries);
        return chart;
    }

    public Parent buildLayout() {
        // ── LEFT SIDEBAR ──────────────────────────────────────────────────
        Label projectsHeader = header("PROJECTS  (live)");
        projectList.setPrefHeight(320);
        projectList.getStyleClass().add("sidebar-list");
        loadProjectsFromDb();
        projectList.setOnMouseClicked(e -> {
            DbStatus.ProjectItem sel = projectList.getSelectionModel().getSelectedItem();
            if (sel != null) {
                selectedProject = sel.name();
                sendQuery("Give me a full intelligence report on " + sel.name() +
                    ": git status, pending tasks, recent commits, what to work on next, and any issues.", sel.name());
            }
        });

        Button refreshBtn = new Button("↻ Refresh");
        refreshBtn.getStyleClass().add("clear-btn");
        refreshBtn.setMaxWidth(Double.MAX_VALUE);
        refreshBtn.setOnAction(e -> loadProjectsFromDb());

        Label autoHeader = header("TALON AUTOMATION");
        Button syncExcelBtn = new Button("Sync Master Excel");
        Button syncAccessBtn = new Button("Sync Access DB");
        Button talonLoopBtn = new Button("Start Talon Loop");

        syncExcelBtn.setMaxWidth(Double.MAX_VALUE);
        syncAccessBtn.setMaxWidth(Double.MAX_VALUE);
        talonLoopBtn.setMaxWidth(Double.MAX_VALUE);

        syncExcelBtn.getStyleClass().add("clear-btn");
        syncAccessBtn.getStyleClass().add("clear-btn");
        talonLoopBtn.getStyleClass().add("clear-btn");

        syncExcelBtn.setOnAction(e -> sendQuery("automate excel sync"));
        syncAccessBtn.setOnAction(e -> sendQuery("automate access sync"));
        talonLoopBtn.setOnAction(e -> {
            if (talonLoopBtn.getText().contains("Start")) {
                sendQuery("kqml (achieve :content (start-loop))");
                talonLoopBtn.setText("Stop Talon Loop");
            } else {
                sendQuery("kqml (achieve :content (stop-loop))");
                talonLoopBtn.setText("Start Talon Loop");
            }
        });

        Label agentHeader = header("ACTIVE AGENT");
        agentLabel.getStyleClass().add("agent-label");

        Label dbHeader = header("DB STATUS");
        dbStatusBox.getStyleClass().add("db-status");

        VBox sidebar = new VBox(8,
            projectsHeader, projectList, refreshBtn,
            new Separator(),
            autoHeader, syncExcelBtn, syncAccessBtn, talonLoopBtn,
            new Separator(),
            agentHeader, agentLabel,
            new Separator(),
            dbHeader, dbStatusBox
        );
        sidebar.setPadding(new Insets(12));
        sidebar.setPrefWidth(220);
        sidebar.getStyleClass().add("sidebar");

        // ── CHAT AREA ──────────────────────────────────────────────────────
        chatBox.setPadding(new Insets(12));
        chatBox.getStyleClass().add("chat-box");
        chatScroll.setFitToWidth(true);
        chatScroll.getStyleClass().add("chat-scroll");
        VBox.setVgrow(chatScroll, Priority.ALWAYS);

        addMessage("MOE", "Moe online. Ask me anything about your projects.\n" +
            "Try: \"What's next on ViperNote?\" or \"best tool for BM25 in Python\"", "moe-msg");

        // ── INPUT BAR ──────────────────────────────────────────────────────
        inputField.setPromptText("Ask Moe anything...");
        inputField.getStyleClass().add("input-field");
        inputField.setOnAction(e -> sendFromInput());
        HBox.setHgrow(inputField, Priority.ALWAYS);

        Button clearBtn = new Button("CLEAR");
        sendBtn.getStyleClass().add("send-btn");
        clearBtn.getStyleClass().add("clear-btn");
        sendBtn.setOnAction(e -> sendFromInput());
        clearBtn.setOnAction(e -> { chatBox.getChildren().clear(); inputField.clear(); });

        shipBtn = new Button("⊕ NOTES");
        shipBtn.getStyleClass().add("clear-btn");
        shipBtn.setDisable(true);
        shipBtn.setStyle("-fx-text-fill:#00cfff;");
        shipBtn.setOnAction(e -> shipToNotes());

        HBox inputBar = new HBox(8, inputField, sendBtn, clearBtn, shipBtn);
        inputBar.setPadding(new Insets(8, 12, 12, 12));
        inputBar.getStyleClass().add("input-bar");

        // ── BRIDGE STATUS ──────────────────────────────────────────────────
        bridgeStatus.getStyleClass().add("bridge-status");
        HBox statusBar = new HBox(bridgeStatus);
        statusBar.setPadding(new Insets(4, 12, 4, 12));
        statusBar.getStyleClass().add("status-bar");

        VBox chatAndInputPane = new VBox(chatScroll, inputBar, statusBar);
        chatAndInputPane.getStyleClass().add("center-pane");

        // Split chat panel horizontally to include LineChart on the right
        SplitPane centerSplit = new SplitPane(chatAndInputPane, telemetryChart);
        centerSplit.setOrientation(Orientation.HORIZONTAL);
        centerSplit.setDividerPositions(0.65);

        // Sidebar on left, centerSplit on right
        SplitPane swarmOrchestratorSplit = new SplitPane(sidebar, centerSplit);
        swarmOrchestratorSplit.setDividerPositions(0.20);
        swarmOrchestratorSplit.setOrientation(Orientation.HORIZONTAL);
        swarmOrchestratorSplit.getStyleClass().add("root-split");

        // TabPane containing Swarm Orchestrator and Blueprint Tracker
        TabPane tabPane = new TabPane();
        tabPane.getStyleClass().add("main-tab-pane");

        Tab orchestratorTab = new Tab("Swarm Orchestrator");
        orchestratorTab.setClosable(false);
        orchestratorTab.setContent(swarmOrchestratorSplit);

        // Blueprint Tracker tab
        VBox blueprintLayout = new VBox(15);
        blueprintLayout.setPadding(new Insets(20));
        blueprintLayout.getStyleClass().add("blueprint-tracker-pane");
        
        Label bpTitle = new Label("VIPER SYSTEM BLUEPRINT STATUS");
        bpTitle.setFont(Font.font("Monospace", FontWeight.BOLD, 18));
        bpTitle.setStyle("-fx-text-fill: #00ffcc;");
        
        blueprintProgressBar.setPrefWidth(400);
        blueprintProgressBar.setMinHeight(20);
        
        completionLabel.setFont(Font.font("Monospace", FontWeight.BOLD, 36));
        completionLabel.setStyle("-fx-text-fill: #00ffcc;");
        
        HBox progressInfo = new HBox(20, blueprintProgressBar, completionLabel);
        progressInfo.setStyle("-fx-alignment: center-left;");
        
        Label phasesTitle = new Label("BLUEPRINT PHASES & ALIGNMENT");
        phasesTitle.setFont(Font.font("Monospace", FontWeight.BOLD, 14));
        
        ScrollPane phasesScroll = new ScrollPane(phasesContainer);
        phasesScroll.setFitToWidth(true);
        phasesScroll.setStyle("-fx-background-color: transparent; -fx-background: transparent;");
        VBox.setVgrow(phasesScroll, Priority.ALWAYS);
        
        blueprintLayout.getChildren().addAll(bpTitle, progressInfo, new Separator(), phasesTitle, phasesScroll);

        Tab blueprintTab = new Tab("Blueprint Tracker");
        blueprintTab.setClosable(false);
        blueprintTab.setContent(blueprintLayout);

        tabPane.getTabs().addAll(orchestratorTab, blueprintTab);
        return tabPane;
    }

    private void sendFromInput() {
        String text = inputField.getText().trim();
        if (text.isEmpty()) return;
        inputField.clear();
        sendQuery(text, selectedProject);
    }

    private void sendQuery(String query) {
        sendQuery(query, selectedProject);
    }

    private void sendQuery(String query, String project) {
        addMessage("YOU", query + (project != null ? " [ctx:" + project + "]" : ""), "user-msg");
        agentLabel.setText("Agent: routing...");
        bridgeStatus.setText("● thinking...");
        bridgeStatus.setStyle("-fx-text-fill: #ffaa00;");
        inputField.setDisable(true);
        sendBtn.setDisable(true);
        sendBtn.setText("...");
        showThinkingBubble();
        bridge.send(query, project);
    }

    private void showThinkingBubble() {
        removeThinkingBubble();
        elapsedSecs.set(0);

        thinkingLabel = new Label("Moe is thinking... (0s)  [SmolLM2 ~30-90s on this CPU]");
        thinkingLabel.getStyleClass().add("moe-msg");
        thinkingLabel.setStyle("-fx-text-fill: #ffaa00; -fx-font-style: italic;");
        thinkingLabel.setWrapText(true);
        thinkingLabel.setMaxWidth(Double.MAX_VALUE);

        Label roleLabel = new Label("MOE");
        roleLabel.getStyleClass().add("msg-role");
        roleLabel.setFont(Font.font("Monospace", FontWeight.BOLD, 11));

        thinkingBubble = new VBox(2, roleLabel, thinkingLabel);
        thinkingBubble.getStyleClass().add("msg-bubble");
        thinkingBubble.setPadding(new Insets(6, 10, 6, 10));
        chatBox.getChildren().add(thinkingBubble);
        chatScroll.layout();
        chatScroll.setVvalue(1.0);

        thinkingTimer = new Timeline(new KeyFrame(Duration.seconds(1), e -> {
            int secs = elapsedSecs.incrementAndGet();
            String dots = ".".repeat((secs % 3) + 1);
            thinkingLabel.setText(String.format(
                "Moe is thinking%s (%ds)  [SmolLM2 ~30-90s on this CPU]", dots, secs));
            chatScroll.setVvalue(1.0);
        }));
        thinkingTimer.setCycleCount(Timeline.INDEFINITE);
        thinkingTimer.play();
    }

    private void removeThinkingBubble() {
        if (thinkingTimer != null) { thinkingTimer.stop(); thinkingTimer = null; }
        if (thinkingBubble != null) {
            chatBox.getChildren().remove(thinkingBubble);
            thinkingBubble = null;
            thinkingLabel  = null;
        }
    }

    private void addMessage(String role, String text, String styleClass) {
        addMessage(role, text, styleClass, true);
    }

    private void addMessage(String role, String text, String styleClass, boolean persist) {
        Label roleLabel = new Label(role);
        roleLabel.getStyleClass().add("msg-role");
        roleLabel.setFont(Font.font("Monospace", FontWeight.BOLD, 11));

        Label body = new Label(text);
        body.setWrapText(true);
        body.getStyleClass().add(styleClass);
        body.setMaxWidth(Double.MAX_VALUE);

        VBox bubble = new VBox(2, roleLabel, body);
        bubble.getStyleClass().add("msg-bubble");
        bubble.setPadding(new Insets(6, 10, 6, 10));
        chatBox.getChildren().add(bubble);

        chatScroll.layout();
        chatScroll.setVvalue(1.0);

        if ("MOE".equals(role)) {
            lastMoeResponse = text;
            if (shipBtn != null) shipBtn.setDisable(false);
        }

        if (persist && !"MOE".equals(role) || persist && "MOE".equals(role)) {
            persistMessage(role, text);
        }
    }

    private void persistMessage(String role, String text) {
        Thread.ofVirtual().start(() -> {
            try (Connection con = openDb()) {
                con.createStatement().execute(
                    "CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                    "ts TEXT, role TEXT, message TEXT, project TEXT)");
                PreparedStatement ps = con.prepareStatement(
                    "INSERT INTO chat_history (ts, role, message, project) VALUES (?,?,?,?)");
                ps.setString(1, Instant.now().toString());
                ps.setString(2, role);
                ps.setString(3, text);
                ps.setString(4, selectedProject != null ? selectedProject : "");
                ps.executeUpdate();
            } catch (Exception ignored) {}
        });
    }

    private void loadChatHistory() {
        List<String[]> rows = new ArrayList<>();
        try (Connection con = openDb()) {
            con.createStatement().execute(
                "CREATE TABLE IF NOT EXISTS chat_history (id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "ts TEXT, role TEXT, message TEXT, project TEXT)");
            var rs = con.createStatement().executeQuery(
                "SELECT role, message FROM chat_history ORDER BY id DESC LIMIT 30");
            while (rs.next()) rows.add(0, new String[]{rs.getString(1), rs.getString(2)});
        } catch (Exception ignored) {}
        for (String[] r : rows) {
            String style = "MOE".equals(r[0]) ? "moe-msg" : "user-msg";
            addMessage(r[0], r[1], style, false);
        }
    }

    private void shipToNotes() {
        if (lastMoeResponse == null || lastMoeResponse.isBlank()) return;
        String title = lastMoeResponse.length() > 80
            ? lastMoeResponse.substring(0, 80) + "…" : lastMoeResponse;

        // Prefer ViperNotesController (persists in notes.db with notebooks)
        if (notesController != null) {
            notesController.ingestConversation(title, lastMoeResponse);
            if (shipBtn != null) { shipBtn.setText("✓ SAVED"); shipBtn.setDisable(true); }
            return;
        }

        // Fallback: write directly to harvested_notes in telemetry.db
        Thread.ofVirtual().start(() -> {
            try (Connection con = openDb()) {
                con.createStatement().execute(
                    "CREATE TABLE IF NOT EXISTS harvested_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                    "hash TEXT UNIQUE, machine TEXT, source TEXT, category TEXT, title TEXT, " +
                    "content TEXT, created_at TEXT)");
                String hash = Integer.toHexString(lastMoeResponse.hashCode());
                PreparedStatement ps = con.prepareStatement(
                    "INSERT OR IGNORE INTO harvested_notes (hash,machine,source,category,title,content,created_at) " +
                    "VALUES (?,?,?,?,?,?,?)");
                ps.setString(1, hash);
                ps.setString(2, "alice");
                ps.setString(3, "MoeGUI chat");
                ps.setString(4, "chat");
                ps.setString(5, title);
                ps.setString(6, lastMoeResponse);
                ps.setString(7, Instant.now().toString());
                ps.executeUpdate();
                Platform.runLater(() -> {
                    if (shipBtn != null) { shipBtn.setText("✓ SAVED"); shipBtn.setDisable(true); }
                });
            } catch (Exception e) {
                System.err.println("[MoeController] shipToNotes error: " + e.getMessage());
            }
        });
    }

    private void loadProjectsFromDb() {
        try {
            List<DbStatus.ProjectItem> items = DbStatus.projectList();
            projectList.getItems().setAll(items);
        } catch (Exception e) {
            projectList.getItems().setAll(new DbStatus.ProjectItem("DB error", 0));
        }
    }

    private Label header(String text) {
        Label l = new Label(text);
        l.getStyleClass().add("sidebar-header");
        l.setFont(Font.font("Monospace", FontWeight.BOLD, 10));
        return l;
    }

    public void startLiveUpdates() {
        bridge.setTokenCallback(token -> {
            if (thinkingLabel != null) {
                if (thinkingTimer != null) { thinkingTimer.stop(); thinkingTimer = null; }
                String current = thinkingLabel.getText();
                if (current.startsWith("Moe is thinking")) {
                    thinkingLabel.setStyle("-fx-text-fill: #ccffcc; -fx-font-style: normal;");
                    thinkingLabel.setText(token);
                } else {
                    thinkingLabel.setText(current + token);
                }
                chatScroll.setVvalue(1.0);
            }
        });

        bridge.setResponseCallback(answer -> {
            if (answer != null && answer.startsWith("GUI_DATA: ")) {
                handleGuiData(answer);
                return;
            }
            int elapsed = elapsedSecs.get();
            removeThinkingBubble();
            inputField.setDisable(false);
            sendBtn.setDisable(false);
            sendBtn.setText("SEND");
            agentLabel.setText("Agent: ready  (" + elapsed + "s)");
            bridgeStatus.setText("● Moe online");
            bridgeStatus.setStyle("-fx-text-fill: #44ff88;");
            if (shipBtn != null) { shipBtn.setText("⊕ NOTES"); shipBtn.setDisable(false); }
            addMessage("MOE", answer, "moe-msg");
            inputField.requestFocus();
        });

        loadChatHistory();

        boolean started = bridge.start();
        if (started) {
            bridgeStatus.setText("● Moe online");
            bridgeStatus.setStyle("-fx-text-fill: #44ff88;");
        } else {
            bridgeStatus.setText("● Moe offline (bridge not started)");
            bridgeStatus.setStyle("-fx-text-fill: #ff4444;");
        }

        refreshDbStatus();
        
        // Polling loop: every 5 seconds send gui_data and refresh DB status, every 30 seconds reload project list.
        liveTimer = new Timeline(
            new KeyFrame(Duration.seconds(5),  e -> {
                refreshDbStatus();
                bridge.send("gui_data");
            }),
            new KeyFrame(Duration.seconds(30), e -> loadProjectsFromDb())
        );
        liveTimer.setCycleCount(Timeline.INDEFINITE);
        liveTimer.play();
    }

    private void handleGuiData(String guiDataPayload) {
        String jsonStr = guiDataPayload.substring("GUI_DATA: ".length());
        try {
            JsonNode node = mapper.readTree(jsonStr);
            double cpu = node.get("cpu").asDouble();
            double ram = node.get("ram").asDouble();
            double completionPercentage = node.get("completion_percentage").asDouble();
            String activeAgent = node.get("active_agent").asText();

            // 1. Update Telemetry Visualizer Chart
            Platform.runLater(() -> {
                cpuSeries.getData().add(new XYChart.Data<>(timeIndex, cpu));
                ramSeries.getData().add(new XYChart.Data<>(timeIndex, ram));
                timeIndex++;
                if (cpuSeries.getData().size() > 20) {
                    cpuSeries.getData().remove(0);
                }
                if (ramSeries.getData().size() > 20) {
                    ramSeries.getData().remove(0);
                }

                // 2. Update Blueprint Progress Tracker components
                blueprintProgressBar.setProgress(completionPercentage / 100.0);
                completionLabel.setText(String.format("%.1f%%", completionPercentage));

                // 3. Update agent label
                agentLabel.setText("Agent: " + activeAgent);

                // 4. Update the phases list/grid in Blueprint Tracker tab
                phasesContainer.getChildren().clear();
                JsonNode phasesNode = node.get("phases");
                if (phasesNode != null && phasesNode.isArray()) {
                    for (JsonNode phaseNode : phasesNode) {
                        String name = phaseNode.get("name").asText();
                        int completed = phaseNode.get("completed").asInt();
                        int total = phaseNode.get("total").asInt();
                        
                        VBox phaseBox = new VBox(4);
                        phaseBox.setStyle("-fx-border-color: #555; -fx-border-width: 1px; -fx-padding: 8px; -fx-background-color: #2b2b2b; -fx-border-radius: 4px;");
                        
                        Label nameLbl = new Label(name);
                        nameLbl.setStyle("-fx-font-weight: bold; -fx-text-fill: #fff;");
                        
                        ProgressBar pBar = new ProgressBar(total > 0 ? (double) completed / total : 0.0);
                        pBar.setPrefWidth(350);
                        
                        Label statusLbl = new Label(completed + " / " + total + " completed (" + (total > 0 ? (completed * 100 / total) : 0) + "%)");
                        statusLbl.setStyle("-fx-text-fill: #aaa; -fx-font-size: 11px;");
                        
                        phaseBox.getChildren().addAll(nameLbl, pBar, statusLbl);
                        phasesContainer.getChildren().add(phaseBox);
                    }
                }
            });
        } catch (Exception e) {
            System.err.println("[MoeController] Failed to parse telemetry GUI_DATA: " + e.getMessage());
        }
    }

    private void refreshDbStatus() {
        try {
            Map<String, Map<String, Long>> snap = DbStatus.snapshot();
            dbStatusBox.getChildren().clear();
            snap.forEach((db, tables) -> {
                tables.forEach((table, count) -> {
                    Label l = new Label(String.format("%-10s %s: %,d", db, table, count));
                    l.getStyleClass().add("db-row");
                    l.setFont(Font.font("Monospace", 10));
                    dbStatusBox.getChildren().add(l);
                });
            });
        } catch (Exception ignored) {}
    }

    public void shutdown() {
        if (liveTimer != null) liveTimer.stop();
        bridge.shutdown();
    }
}

