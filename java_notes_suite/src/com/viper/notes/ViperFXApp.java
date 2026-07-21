package com.viper.notes;

import javafx.application.Application;
import javafx.application.Platform;
import javafx.scene.web.WebView;
import javafx.scene.web.WebEngine;
import javafx.scene.*;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import javafx.scene.paint.Color;
import javafx.scene.paint.PhongMaterial;
import javafx.scene.shape.Sphere;
import javafx.stage.Stage;
import javafx.geometry.Insets;
import javafx.geometry.Pos;
import javafx.scene.chart.LineChart;
import javafx.scene.chart.NumberAxis;
import javafx.scene.chart.XYChart;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Random;

public class ViperFXApp extends Application {
    private static final String MANIFOLD_URL = "http://127.0.0.1:8085"; // OmniNetworkManifold Java server
    private static final String DEV_SUITE_URL = "http://127.0.0.1:8091"; // ViperNotesServer
    private static final String LAB_SUITE_URL = "http://127.0.0.1:18181"; // ViperLabSuiteServer
    private static final String OTG_GAN_URL = "http://127.0.0.1:18082"; // OTG GAN bridge port
    private static final String HOUSE_INF_URL = "http://127.0.0.1:11435"; // House inference server port

    private static final HttpClient HTTP = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(2))
            .build();

    private static final List<Process> SPAWNED_PROCESSES = new ArrayList<>();

    private TextArea logOutput = new TextArea();
    private TextArea chatMessages = new TextArea();
    private TextField chatInput = new TextField();
    private Label statusLabel = new Label("System Status: Starting...");

    // Dependency manager labels
    private Label depCurrentVer = new Label("Current Version: Scanning...");
    private Label depLatestVer = new Label("Latest Version: Scanning...");
    private Label depStatusText = new Label("STATUS: Unknown");

    // Database health text area
    private TextArea dbHealthOutput = new TextArea();
    private TextArea promptInjectionsOutput = new TextArea();

    // Telemetry series
    private XYChart.Series<Number, Number> latencySeries = new XYChart.Series<>();
    private XYChart.Series<Number, Number> dbQueueSeries = new XYChart.Series<>();
    private XYChart.Series<Number, Number> resonanceSeries = new XYChart.Series<>();
    private int telemetrySampleIndex = 15;

    // Sprites chat elements
    private TextArea spriteChatArea = new TextArea();
    private TextField spriteChatInput = new TextField();
    private String selectedSprite = "Manager Sprite";

    // Governance UI text controls
    private TextArea govHealthOutput = new TextArea();
    private TextArea govPowOutput = new TextArea();
    private TextArea govTraceOutput = new TextArea();
    private VBox pendingProposalsContainer = new VBox(10);

    @Override
    public void start(Stage stage) {
        stage.setTitle("VIPER Native 3D Developer Console v2.0.0 (Overkill-Ed)");

        // Set global light high-visibility stylesheet
        String css = 
            ".root, .pane, .grid-pane, .scroll-pane, .border-pane, .vbox, .hbox { -fx-background-color: #ffffff; }" +
            ".scroll-pane .viewport { -fx-background-color: #ffffff; }" +
            ".scroll-pane { -fx-background-insets: 0; -fx-padding: 0; -fx-border-color: #cfd6dc; }" +
            ".tab-pane .tab-header-area .tab-header-background { -fx-background-color: #f3f4f6; }" +
            ".tab { -fx-background-color: #f3f4f6; -fx-text-fill: #24292f; -fx-font-family: 'Consolas'; -fx-font-size: 12px; -fx-padding: 8px 16px; -fx-border-color: #cfd6dc; -fx-border-width: 0 1 0 0; }" +
            ".tab:selected { -fx-background-color: #ffffff; -fx-text-fill: #0969da; -fx-font-weight: bold; }" +
            ".button { -fx-background-color: #f3f4f6; -fx-text-fill: #24292f; -fx-border-color: #cfd6dc; -fx-border-radius: 6px; -fx-background-radius: 6px; -fx-font-family: 'Consolas'; -fx-font-size: 11px; }" +
            ".button:hover { -fx-background-color: #e5e7eb; -fx-border-color: #0969da; }" +
            ".text-area, .text-field, .combo-box, .list-view { -fx-control-inner-background: #ffffff; -fx-text-fill: #24292f; -fx-font-family: 'Consolas'; -fx-border-color: #cfd6dc; -fx-border-radius: 6px; -fx-background-radius: 6px; }" +
            ".list-cell { -fx-background-color: #ffffff; -fx-text-fill: #24292f; }" +
            ".list-cell:selected { -fx-background-color: #f3f4f6; -fx-text-fill: #0969da; -fx-font-weight: bold; }" +
            ".label { -fx-text-fill: #24292f; -fx-font-family: 'Consolas'; -fx-font-size: 11px; }";

        TabPane tabPane = new TabPane();
        tabPane.getTabs().addAll(
            createManifoldTab(), 
            createTrainingTab(), 
            createOmniscientTab(), 
            createGovernanceTab(),
            createSystemHealthTab(),
            createOtgStatusTab()
        );
        tabPane.getStylesheets().add("data:text/css," + css.replace(" ", "%20"));

        VBox consolePane = new VBox(6);
        Label consoleTitle = new Label("System Console Output Log Trace");
        consoleTitle.setStyle("-fx-text-fill: #0969da; -fx-font-weight: bold; -fx-font-size: 11px;");
        logOutput.setEditable(false);
        logOutput.setPrefHeight(140);
        logOutput.setStyle("-fx-control-inner-background: #ffffff; -fx-text-fill: #24292f; -fx-font-family: 'Consolas'; -fx-border-color: #cfd6dc; -fx-border-radius: 6px;");
        consolePane.getChildren().addAll(consoleTitle, logOutput);

        MenuBar menuBar = new MenuBar();

        Menu fileMenu = new Menu("File");
        MenuItem backupItem = new MenuItem("Emergency DB Backup");
        backupItem.setOnAction(e -> {
            logOutput.appendText("\n[SYSTEM] Triggering Emergency Database Backup...\n");
            runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\karoo_epoch_upgrade.py", "backup");
        });
        MenuItem exitItem = new MenuItem("Exit Application");
        exitItem.setOnAction(e -> Platform.exit());
        fileMenu.getItems().addAll(backupItem, new SeparatorMenuItem(), exitItem);

        Menu ecosystemMenu = new Menu("Ecosystem");
        MenuItem ftsBuildItem = new MenuItem("Trigger FTS Context Build");
        ftsBuildItem.setOnAction(e -> {
            logOutput.appendText("\n[ECOSYSTEM] Manually triggering FTS Context build...\n");
            runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\viper_cognitive_injector.py", "");
        });
        MenuItem syncTimeItem = new MenuItem("Sync Atomic Time");
        syncTimeItem.setOnAction(e -> {
            logOutput.appendText("\n[ECOSYSTEM] Syncing time with Cloudflare...\n");
            runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\cloudflared_time_sync.py", "");
        });
        ecosystemMenu.getItems().addAll(ftsBuildItem, syncTimeItem);

        Menu govMenu = new Menu("Governance");
        MenuItem sweepItem = new MenuItem("Run Governance Sweep");
        sweepItem.setOnAction(e -> {
            logOutput.appendText("\n[GOV] Requesting manual Karoo sweep scan...\n");
            runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\karoo_governor.py", "");
        });
        MenuItem upgradeItem = new MenuItem("Execute Pending Upgrades");
        upgradeItem.setOnAction(e -> {
            logOutput.appendText("\n[GOV] Accepting and deploying all proposals...\n");
            runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\viper_orchestrator.py", "");
        });
        MenuItem rollbackItem = new MenuItem("Database Rollback Restore");
        rollbackItem.setOnAction(e -> triggerRollbacks());
        govMenu.getItems().addAll(sweepItem, upgradeItem, new SeparatorMenuItem(), rollbackItem);

        Menu helpMenu = new Menu("Help");
        MenuItem auditItem = new MenuItem("System Verification Audit");
        auditItem.setOnAction(e -> {
            logOutput.appendText("\n[HELP] Initiating E2E Verification Audit...\n");
            runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\audit_governance_suite.py", "");
        });
        MenuItem testItem = new MenuItem("Run Karoo Unit Tests");
        testItem.setOnAction(e -> {
            logOutput.appendText("\n[HELP] Launching Ecosystem Unit Tests...\n");
            runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\test_karoo_suite.py", "");
        });
        helpMenu.getItems().addAll(auditItem, testItem);

        menuBar.getMenus().addAll(fileMenu, ecosystemMenu, govMenu, helpMenu);

        // Triplet AI Kernel Chat Sidebar (E2E persistent sidebar!)
        VBox chatSidebar = new VBox(8);
        chatSidebar.setPadding(new Insets(10));
        chatSidebar.setPrefWidth(280);
        chatSidebar.setMinWidth(220);
        chatSidebar.setMaxWidth(400);
        chatSidebar.setStyle("-fx-background-color: #f6f8fa; -fx-border-color: #cfd6dc; -fx-border-width: 0 0 0 1;");

        Label chatTitle = new Label("Triplet AI Kernel Chat");
        chatTitle.setStyle("-fx-text-fill: #0969da; -fx-font-weight: bold; -fx-font-size: 11px;");

        chatMessages.setEditable(false);
        chatMessages.setWrapText(true);
        chatMessages.setStyle("-fx-control-inner-background: #ffffff; -fx-text-fill: #24292f; -fx-font-family: 'Consolas'; -fx-font-size: 11px; -fx-border-color: #cfd6dc;");
        VBox.setVgrow(chatMessages, Priority.ALWAYS);

        chatInput.setPromptText("Enter directive for Triplet...");
        chatInput.setOnAction(e -> sendChatDirective());

        Button sendBtn = new Button("Send Directive");
        sendBtn.setMaxWidth(Double.MAX_VALUE);
        sendBtn.setOnAction(e -> sendChatDirective());

        chatSidebar.getChildren().addAll(chatTitle, chatMessages, chatInput, sendBtn);

        // Main Content VBox layout
        VBox mainContent = new VBox(10);
        mainContent.setPadding(new Insets(10, 0, 10, 10));
        VBox.setVgrow(tabPane, Priority.ALWAYS);
        statusLabel.setStyle("-fx-text-fill: #10b981; -fx-font-weight: bold;");
        mainContent.getChildren().addAll(tabPane, consolePane, statusLabel);

        // SplitPane container joining main content and sidebar
        SplitPane splitPane = new SplitPane();
        splitPane.getItems().addAll(mainContent, chatSidebar);
        splitPane.setDividerPositions(0.78); // Chat sidebar gets ~22% width

        VBox layout = new VBox(0);
        VBox.setVgrow(splitPane, Priority.ALWAYS);
        layout.getChildren().addAll(menuBar, splitPane);

        Scene scene = new Scene(layout, 1420, 880);
        stage.setScene(scene);
        stage.show();

        // Register process cleanup shutdown hook
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.out.println("[SHUTDOWN] Terminating embedded processes...");
            for (Process p : SPAWNED_PROCESSES) {
                try { p.destroy(); } catch (Exception e) {}
            }
        }));

        // Central Hierarchical Heartbeat Tick Tree (Step 162)
        new Thread(() -> {
            Random rand = new Random();
            long tickCount = 0;
            while (true) {
                try {
                    tickCount++;
                    final long currentTick = tickCount;

                    // --- 5-Second Tick (Telemetry, Probes & Traceroute) ---
                    if (currentTick % 5 == 0) {
                        boolean isManifoldLive = probe(MANIFOLD_URL + "/");
                        boolean isLabLive = probe(LAB_SUITE_URL + "/health");
                        boolean isNotesLive = probe(DEV_SUITE_URL + "/api/notes");
                        boolean isOtgBridgeLive = probe(OTG_GAN_URL + "/");
                        boolean isHouseLive = probe(HOUSE_INF_URL + "/health");
                        
                        // Run database traceroute recording
                        runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\karoo_recorder.py", "");
                        
                        // Fetch actual database metrics in background thread (no UI stutters!)
                        int openTodos = getRealOpenTodosCount();
                        int filesCount = getRealKnowledgeCount();
                        int proposalsCount = getRealProposalsCount();
                        
                        Platform.runLater(() -> {
                            statusLabel.setText(String.format(
                                "Tick: %d | Servers: Manifold [%s] | Training [%s] | Notes [%s] | GAN Bridge [%s] | House [%s]",
                                currentTick,
                                isManifoldLive ? "LIVE" : "DOWN",
                                isLabLive ? "LIVE" : "DOWN",
                                isNotesLive ? "LIVE" : "DOWN",
                                isOtgBridgeLive ? "LIVE" : "DOWN",
                                isHouseLive ? "LIVE" : "DOWN"
                            ));

                            // Update telemetry chart series with actual telemetry
                            telemetrySampleIndex++;
                            latencySeries.getData().add(new XYChart.Data<>(telemetrySampleIndex, openTodos));
                            dbQueueSeries.getData().add(new XYChart.Data<>(telemetrySampleIndex, filesCount));
                            resonanceSeries.getData().add(new XYChart.Data<>(telemetrySampleIndex, proposalsCount));
                        });

                        loadDependencyPlanAndDbHealth();
                        loadGovernanceTelemetry();
                    }


                    // --- 120-Second Tick (Cloudflare Atomic Time Sync) ---
                    if (currentTick % 120 == 0) {
                        runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\cloudflared_time_sync.py", "");
                    }

                    // --- 300-Second Tick (Central Orchestrator Planning Run) ---
                    if (currentTick % 300 == 0) {
                        runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\viper_orchestrator.py", "");
                    }

                    Thread.sleep(1000);
                } catch (Exception e) {}
            }
        }, "VIPER-Heartbeat-Tick-Tree").start();
    }

    private BorderPane createWebContainer(String url) {
        BorderPane pane = new BorderPane();

        WebView webView = new WebView();
        WebEngine webEngine = webView.getEngine();
        
        // Navigation toolbar
        HBox toolbar = new HBox(12);
        toolbar.setPadding(new Insets(6, 12, 6, 12));
        toolbar.setAlignment(Pos.CENTER_LEFT);
        toolbar.setStyle("-fx-background-color: #f6f8fa; -fx-border-color: #cfd6dc; -fx-border-width: 0 0 1 0;");

        Label statusLbl = new Label("Connecting: " + url);
        statusLbl.setStyle("-fx-text-fill: #1f2328; -fx-font-weight: bold; -fx-font-size: 11px;");

        Button reloadBtn = new Button("Refresh Page");
        reloadBtn.setOnAction(e -> {
            statusLbl.setText("Reloading...");
            webEngine.load(url);
        });

        // Track load state
        webEngine.getLoadWorker().stateProperty().addListener((obs, oldState, newState) -> {
            if (newState == javafx.concurrent.Worker.State.SUCCEEDED) {
                statusLbl.setText("Connected: " + url);
                statusLbl.setStyle("-fx-text-fill: #10b981; -fx-font-weight: bold;");
                try {
                    String cssInject = "var style = document.createElement('style');" +
                        "style.innerHTML = 'body { background-color: #f6f8fa !important; background: #f6f8fa !important; color: #24292f !important; font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Helvetica, Arial, sans-serif !important; margin: 15px !important; } " +
                        "h1, h2, h3, h4, h5, h6 { color: #24292f !important; } " +
                        "button { background-color: #f3f4f6 !important; border: 1px solid #cfd6dc !important; border-radius: 6px !important; color: #24292f !important; padding: 6px 12px !important; font-family: \"Consolas\", monospace !important; font-size: 11px !important; } " +
                        "input, textarea { background-color: #ffffff !important; color: #24292f !important; border: 1px solid #cfd6dc !important; border-radius: 6px !important; padding: 6px !important; } " +
                        "canvas { filter: invert(0) !important; } " +
                        "::-webkit-scrollbar { width: 6px !important; height: 6px !important; } " +
                        "::-webkit-scrollbar-track { background: #f1f1f1 !important; } " +
                        "::-webkit-scrollbar-thumb { background: #cfd6dc !important; border-radius: 3px !important; } " +
                        "#ui-panel, #chat-window, #terminal-window, .card, .panel { background: #ffffff !important; border: 1px solid #cfd6dc !important; box-shadow: none !important; color: #24292f !important; border-radius: 8px !important; }';" +
                        "document.head.appendChild(style);";
                    webEngine.executeScript(cssInject);
                } catch (Exception ex) {
                    System.err.println("Style injection error: " + ex.getMessage());
                }
            } else if (newState == javafx.concurrent.Worker.State.FAILED) {
                statusLbl.setText("Connection Failed: " + url + " (Click Refresh)");
                statusLbl.setStyle("-fx-text-fill: #ef4444; -fx-font-weight: bold;");
            }
        });

        toolbar.getChildren().addAll(reloadBtn, statusLbl);
        pane.setTop(toolbar);
        pane.setCenter(webView);

        // Load page with 1.5s delay to ensure local background server booted
        new Thread(() -> {
            try { Thread.sleep(1500); } catch(Exception ex) {}
            Platform.runLater(() -> webEngine.load(url));
        }).start();

        return pane;
    }

    // ─── Tab 1: RISC Manifold WebUI ──────────────────────────────────────────
    private Tab createManifoldTab() {
        Tab tab = new Tab("RISC Manifold");
        tab.setClosable(false);
        tab.setContent(createWebContainer(MANIFOLD_URL));
        return tab;
    }

    // ─── Tab 2: Training SDK WebUI ──────────────────────────────────────────
    private Tab createTrainingTab() {
        Tab tab = new Tab("Training SDK");
        tab.setClosable(false);
        tab.setContent(createWebContainer(LAB_SUITE_URL));
        return tab;
    }

    // ─── Tab 3: Omniscient SDK WebUI ──────────────────────────────────────────
    private Tab createOmniscientTab() {
        Tab tab = new Tab("Omniscient SDK");
        tab.setClosable(false);
        tab.setContent(createWebContainer(DEV_SUITE_URL));
        return tab;
    }

    // ─── Tab 5: System Health (3D + Telemetry LineCharts) ───────────────────
    private Tab createSystemHealthTab() {
        Tab tab = new Tab("System Health");
        tab.setClosable(false);

        HBox mainLayout = new HBox(15);
        mainLayout.setPadding(new Insets(15));

        // LEFT Pane: 3D Visualization within StackPane (Supports Dynamic Resizing!)
        Group group3d = new Group();
        Random rand = new Random();
        for (int i = 0; i < 180; i++) {
            Sphere sphere = new Sphere(0.4 + rand.nextDouble() * 0.3);
            double phi = Math.acos(-1.0 + (2.0 * i) / 180.0);
            double theta = Math.sqrt(180.0 * Math.PI) * phi;
            double r = 12.0 + rand.nextDouble() * 1.5;
            sphere.setTranslateX(r * Math.cos(theta) * Math.sin(phi));
            sphere.setTranslateY(r * Math.sin(theta) * Math.sin(phi));
            sphere.setTranslateZ(r * Math.cos(phi));

            PhongMaterial material = new PhongMaterial();
            boolean isNeutral = rand.nextBoolean();
            if (isNeutral) {
                material.setDiffuseColor(Color.web("#38bdf8"));
                material.setSpecularColor(Color.web("#7dd3fc"));
            } else {
                material.setDiffuseColor(Color.web("#8b0000"));
                material.setSpecularColor(Color.web("#ef4444"));
            }
            sphere.setMaterial(material);
            group3d.getChildren().add(sphere);
        }

        // Central Karoo Nucleus
        for (int i = 0; i < 24; i++) {
            Sphere node = new Sphere(0.4);
            double angle = (i / 24.0) * Math.PI * 2;
            node.setTranslateX(Math.cos(angle) * 4.0);
            node.setTranslateY(Math.sin(angle) * 4.0);
            node.setTranslateZ(Math.sin(angle * 2.0) * 1.5);
            PhongMaterial karooMat = new PhongMaterial();
            karooMat.setDiffuseColor(Color.web("#facc15"));
            karooMat.setSpecularColor(Color.YELLOW);
            node.setMaterial(karooMat);
            group3d.getChildren().add(node);
        }

        // Orbiting Mesh Nodes
        Sphere aegisNode = new Sphere(1.1);
        PhongMaterial aegisMat = new PhongMaterial();
        aegisMat.setDiffuseColor(Color.web("#7bd389"));
        aegisMat.setSpecularColor(Color.WHITE);
        aegisNode.setMaterial(aegisMat);
        aegisNode.setTranslateX(18);
        group3d.getChildren().add(aegisNode);

        Sphere bruteNode = new Sphere(0.9);
        PhongMaterial bruteMat = new PhongMaterial();
        bruteMat.setDiffuseColor(Color.web("#d2a8ff"));
        bruteMat.setSpecularColor(Color.WHITE);
        bruteNode.setMaterial(bruteMat);
        bruteNode.setTranslateX(-18);
        group3d.getChildren().add(bruteNode);

        SubScene subScene = new SubScene(group3d, 460, 400, true, SceneAntialiasing.BALANCED);
        subScene.setFill(Color.web("#f6f8fa"));
        PerspectiveCamera camera = new PerspectiveCamera(true);
        camera.setNearClip(0.1);
        camera.setFarClip(1000.0);
        camera.setTranslateZ(-38);
        subScene.setCamera(camera);

        // Native Y-Axis spin
        javafx.animation.RotateTransition rotate = new javafx.animation.RotateTransition(javafx.util.Duration.seconds(25), group3d);
        rotate.setAxis(javafx.scene.transform.Rotate.Y_AXIS);
        rotate.setByAngle(360);
        rotate.setCycleCount(javafx.animation.Animation.INDEFINITE);
        rotate.setInterpolator(javafx.animation.Interpolator.LINEAR);
        rotate.play();

        // Orbit calculation thread
        new Thread(() -> {
            double angle = 0;
            while (true) {
                final double a = angle;
                Platform.runLater(() -> {
                    aegisNode.setTranslateX(Math.cos(a) * 18);
                    aegisNode.setTranslateZ(Math.sin(a) * 18);

                    bruteNode.setTranslateX(Math.cos(a + Math.PI) * 18);
                    bruteNode.setTranslateZ(Math.sin(a + Math.PI) * 18);
                });
                angle += 0.02;
                try { Thread.sleep(30); } catch (Exception e) {}
            }
        }, "Mesh-Orbit-Thread-2").start();

        // AnchorPane container to safely resize the SubScene via listeners (preventing layout loop)
        AnchorPane sceneContainer = new AnchorPane(subScene);
        sceneContainer.setPrefWidth(460);
        sceneContainer.setStyle("-fx-background-color: #f6f8fa; -fx-border-color: #cfd6dc; -fx-border-radius: 8px; -fx-background-radius: 8px;");
        
        // Set subScene to unmanaged to prevent its size changes from feeding back into the parent layout bounds
        subScene.setManaged(false);
        
        sceneContainer.widthProperty().addListener((obs, oldVal, newVal) -> {
            subScene.setWidth(newVal.doubleValue());
        });
        sceneContainer.heightProperty().addListener((obs, oldVal, newVal) -> {
            subScene.setHeight(newVal.doubleValue());
        });

        // RIGHT Pane: Telemetry Metrics & Charts
        VBox rightPane = new VBox(10);
        HBox.setHgrow(rightPane, Priority.ALWAYS);
        rightPane.setPadding(new Insets(10));
        rightPane.setStyle("-fx-background-color: #f6f8fa; -fx-border-color: #cfd6dc; -fx-border-radius: 8px; -fx-background-radius: 8px;");

        Label metricsTitle = new Label("Ecosystem Multivariable Latency & Queue Telemetry");
        metricsTitle.setStyle("-fx-text-fill: #24292f; -fx-font-size: 13px; -fx-font-weight: bold;");

        NumberAxis xAxis = new NumberAxis();
        xAxis.setLabel("Epoch Sample Index");
        NumberAxis yAxis = new NumberAxis();
        yAxis.setLabel("Metric Value");

        LineChart<Number, Number> chart = new LineChart<>(xAxis, yAxis);
        chart.setTitle("Real-Time Telemetry Monitor");

        latencySeries.setName("Open TODO Tasks");
        dbQueueSeries.setName("Knowledge Base Files");
        resonanceSeries.setName("Governance Proposals Mined");

        chart.getData().addAll(latencySeries, dbQueueSeries, resonanceSeries);
        rightPane.getChildren().addAll(metricsTitle, chart);

        mainLayout.getChildren().addAll(sceneContainer, rightPane);
        tab.setContent(mainLayout);
        return tab;
    }

    // ─── Tab 6: Dependency & DB Health Status Dashboard ──────────────────────
    private Tab createOtgStatusTab() {
        Tab tab = new Tab("OTG & Token Status");
        tab.setClosable(false);

        HBox layout = new HBox(15);
        layout.setPadding(new Insets(20));

        // LEFT Pane: Dependency status list
        VBox leftPane = new VBox(15);
        leftPane.setPrefWidth(320);

        // Sub-panel 1: Dependency
        VBox depBox = new VBox(12);
        depBox.setPadding(new Insets(15));
        depBox.setStyle("-fx-background-color: #f6f8fa; -fx-border-color: #cfd6dc; -fx-border-radius: 8px;");
        Label depTitle = new Label("Ecosystem Dependency Status");
        depTitle.setStyle("-fx-text-fill: #24292f; -fx-font-size: 13px; -fx-font-weight: bold;");
        depCurrentVer.setStyle("-fx-font-size: 11px; -fx-text-fill: #1f2328;");
        depLatestVer.setStyle("-fx-font-size: 11px; -fx-text-fill: #1f2328;");
        depStatusText.setStyle("-fx-font-size: 12px; -fx-font-weight: bold;");
        HBox buttonRow = new HBox(8);
        Button checkBtn = new Button("Scan Dependencies");
        checkBtn.setOnAction(e -> {
            logOutput.appendText("\n[DEP] Triggering Dependency update scan...\n");
            runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\automated_dependency_updates.py", "");
        });
        Button syncOtgBtn = new Button("Sync OTG / USB");
        syncOtgBtn.setOnAction(e -> {
            logOutput.appendText("\n[OTG] Triggering E2E USB OTG Synchronization...\n");
            runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\otg_usb_transfer.py", "");
        });
        buttonRow.getChildren().addAll(checkBtn, syncOtgBtn);
        depBox.getChildren().addAll(depTitle, depCurrentVer, depLatestVer, depStatusText, buttonRow);

        // Sub-panel 2: DB Health
        VBox dbBox = new VBox(10);
        dbBox.setPadding(new Insets(12));
        dbBox.setStyle("-fx-background-color: #f6f8fa; -fx-border-color: #cfd6dc; -fx-border-radius: 8px;");
        Label dbTitle = new Label("SQLite Database Metadata Stats");
        dbTitle.setStyle("-fx-text-fill: #24292f; -fx-font-size: 11px; -fx-font-weight: bold;");
        dbHealthOutput.setEditable(false);
        dbHealthOutput.setPrefHeight(110);
        dbHealthOutput.setStyle("-fx-control-inner-background: #ffffff; -fx-text-fill: #1f2328; -fx-font-family: 'Consolas'; -fx-border-color: #cfd6dc;");
        dbBox.getChildren().addAll(dbTitle, dbHealthOutput);

        // Sub-panel 3: LLM Inference Manager
        VBox llmBox = new VBox(6);
        llmBox.setPadding(new Insets(12));
        llmBox.setStyle("-fx-background-color: #f6f8fa; -fx-border-color: #cfd6dc; -fx-border-radius: 8px;");
        
        Label llmTitle = new Label("LLM Inference Registry Controller");
        llmTitle.setStyle("-fx-text-fill: #24292f; -fx-font-size: 11px; -fx-font-weight: bold;");

        HBox rRow = new HBox(6);
        Label roleLbl = new Label("Role:");
        roleLbl.setPrefWidth(35);
        roleLbl.setStyle("-fx-font-size: 10px; -fx-text-fill: #57606a;");
        TextField roleField = new TextField("chat");
        roleField.setStyle("-fx-font-size: 10px;");
        rRow.getChildren().addAll(roleLbl, roleField);

        HBox pRow = new HBox(6);
        Label pathLbl = new Label("Model:");
        pathLbl.setPrefWidth(35);
        pathLbl.setStyle("-fx-font-size: 10px; -fx-text-fill: #57606a;");
        TextField pathField = new TextField("C:\\Users\\viper\\Aegis_Agents\\vendor\\models\\gemma-2-2b-it-abliterated-Q8_0.gguf");
        pathField.setStyle("-fx-font-size: 9px;");
        HBox.setHgrow(pathField, Priority.ALWAYS);
        pRow.getChildren().addAll(pathLbl, pathField);

        HBox lRow = new HBox(6);
        Label loraLbl = new Label("LoRA:");
        loraLbl.setPrefWidth(35);
        loraLbl.setStyle("-fx-font-size: 10px; -fx-text-fill: #57606a;");
        TextField loraField = new TextField("");
        loraField.setStyle("-fx-font-size: 9px;");
        HBox.setHgrow(loraField, Priority.ALWAYS);
        lRow.getChildren().addAll(loraLbl, loraField);

        Button deployBtn = new Button("Deploy Model Configuration");
        deployBtn.setMaxWidth(Double.MAX_VALUE);
        deployBtn.setStyle("-fx-font-size: 10px;");
        deployBtn.setOnAction(e -> {
            String role = roleField.getText().trim();
            String model = pathField.getText().trim();
            String lora = loraField.getText().trim();
            if (role.isEmpty() || model.isEmpty()) {
                logOutput.appendText("[SYS] Invalid model registry parameters.\n");
                return;
            }
            new Thread(() -> updateModelRegistry(role, model, lora)).start();
        });

        llmBox.getChildren().addAll(llmTitle, rRow, pRow, lRow, deployBtn);

        leftPane.getChildren().addAll(depBox, dbBox, llmBox);

        // RIGHT Pane: Staged Prompt Injections & Sprite Team Chat
        VBox rightPane = new VBox(15);
        HBox.setHgrow(rightPane, Priority.ALWAYS);
        rightPane.setPadding(new Insets(15));
        rightPane.setStyle("-fx-background-color: #f6f8fa; -fx-border-color: #cfd6dc; -fx-border-radius: 8px;");

        Label injectionTitle = new Label("Staged Prompt Injections & Context (Machine 1 / Aegis)");
        injectionTitle.setStyle("-fx-text-fill: #24292f; -fx-font-size: 11px; -fx-font-weight: bold;");

        promptInjectionsOutput.setEditable(false);
        promptInjectionsOutput.setWrapText(true);
        promptInjectionsOutput.setPrefHeight(180);
        promptInjectionsOutput.setStyle("-fx-control-inner-background: #ffffff; -fx-text-fill: #0969da; -fx-font-family: 'Consolas'; -fx-border-color: #cfd6dc;");
        promptInjectionsOutput.setText("Harvester daemon scanning stage...");

        // Sprite Chat Sub-Panel (E2E Sprite Team Integration!)
        VBox spriteChatBox = new VBox(8);
        VBox.setVgrow(spriteChatBox, Priority.ALWAYS);
        spriteChatBox.setPadding(new Insets(10));
        spriteChatBox.setStyle("-fx-background-color: #ffffff; -fx-border-color: #cfd6dc; -fx-border-radius: 8px;");

        Label spriteChatTitle = new Label("Sprite Team AI Chat Console (Port 18285)");
        spriteChatTitle.setStyle("-fx-text-fill: #0969da; -fx-font-weight: bold; -fx-font-size: 11px;");

        spriteChatArea.setEditable(false);
        spriteChatArea.setWrapText(true);
        spriteChatArea.setStyle("-fx-control-inner-background: #ffffff; -fx-text-fill: #24292f; -fx-font-family: 'Consolas'; -fx-font-size: 11px;");
        VBox.setVgrow(spriteChatArea, Priority.ALWAYS);

        spriteChatInput.setPromptText("Enter task directive for Sprite Overseer...");
        spriteChatInput.setOnAction(e -> sendSpriteChatDirective());

        Button sendSpriteBtn = new Button("Dispatch Directive");
        sendSpriteBtn.setMaxWidth(Double.MAX_VALUE);
        sendSpriteBtn.setStyle("-fx-font-size: 10px;");
        sendSpriteBtn.setOnAction(e -> sendSpriteChatDirective());

        spriteChatBox.getChildren().addAll(spriteChatTitle, spriteChatArea, spriteChatInput, sendSpriteBtn);

        rightPane.getChildren().addAll(injectionTitle, promptInjectionsOutput, spriteChatBox);

        layout.getChildren().addAll(leftPane, rightPane);
        tab.setContent(layout);
        return tab;
    }

    private void loadDependencyPlanAndDbHealth() {
        try {
            // Load dependency status
            Path planPath = Paths.get("C:\\Users\\viper\\VIPER_JAVA_RISC\\java_notes_suite\\data\\dependency_update_plan.json");
            if (Files.exists(planPath)) {
                String content = Files.readString(planPath, StandardCharsets.UTF_8);
                String cur = extractJSONValue(content, "current_version");
                String lat = extractJSONValue(content, "latest_version");
                boolean needs = content.contains("\"needs_update\": true");
                
                Platform.runLater(() -> {
                    depCurrentVer.setText("Current Version: " + cur);
                    depLatestVer.setText("Latest Version: " + lat);
                    depStatusText.setText(needs ? "STATUS: Update Recommended" : "STATUS: Up to Date");
                    depStatusText.setStyle(needs ? "-fx-text-fill: #ffa657;" : "-fx-text-fill: #7bd389;");
                });
            }

            // Load DB telemetry stats & prompt injections
            Path stagePath = Paths.get("C:\\Users\\viper\\VIPER_JAVA_RISC\\java_notes_suite\\data\\prompt_injection_stage.json");
            if (Files.exists(stagePath)) {
                String content = Files.readString(stagePath, StandardCharsets.UTF_8);
                // Extract database_telemetry
                int dbIdx = content.indexOf("\"database_telemetry\"");
                if (dbIdx != -1) {
                    int endIdx = content.indexOf("}", dbIdx);
                    int nextBrace = content.indexOf("}", endIdx + 1);
                    if (nextBrace != -1) endIdx = nextBrace;
                    String sub = content.substring(dbIdx, endIdx + 1);
                    Platform.runLater(() -> dbHealthOutput.setText(sub.replace("\"", "").replace(",", "").replace("{", "").replace("}", "").trim()));
                }
                
                // Extract prompt_injections
                int injIdx = content.indexOf("\"prompt_injections\"");
                if (injIdx != -1) {
                    int endInjIdx = content.indexOf("]", injIdx);
                    String injSub = content.substring(injIdx, endInjIdx + 1);
                    Platform.runLater(() -> promptInjectionsOutput.setText(injSub.replace("\"", "").replace(",", "").replace("[", "").replace("]", "").trim()));
                }
            }
        } catch (Exception e) {}
    }

    // ─── Tab 5: TELEMETRY & MULTI-VARIABLES ─────────────────────────────────
    private Tab createTelemetryTab() {
        Tab tab = new Tab("VIPER Telemetry");
        tab.setClosable(false);

        VBox layout = new VBox(15);
        layout.setPadding(new Insets(20));

        Label title = new Label("Ecosystem Multivariable Latency & Queue Telemetry");
        title.setStyle("-fx-text-fill: #a8c7fa; -fx-font-size: 14px; -fx-font-weight: bold;");

        NumberAxis xAxis = new NumberAxis();
        xAxis.setLabel("Epoch Sample Index");
        NumberAxis yAxis = new NumberAxis();
        yAxis.setLabel("Metric Value");

        LineChart<Number, Number> chart = new LineChart<>(xAxis, yAxis);
        chart.setTitle("Real-Time Telemetry Monitor");

        latencySeries.setName("House Inference Latency (ms)");
        dbQueueSeries.setName("DB Transaction Queue (Tasks)");
        resonanceSeries.setName("OTG Resonance Frequency (Hz)");
        
        // Load initial dummy benchmark data
        Random rand = new Random();
        for (int i = 1; i <= 15; i++) {
            latencySeries.getData().add(new XYChart.Data<>(i, 110 + rand.nextInt(90)));
            dbQueueSeries.getData().add(new XYChart.Data<>(i, rand.nextInt(6)));
            resonanceSeries.getData().add(new XYChart.Data<>(i, 10 + rand.nextInt(4)));
        }

        chart.getData().addAll(latencySeries, dbQueueSeries, resonanceSeries);
        layout.getChildren().addAll(title, chart);

        tab.setContent(layout);
        return tab;
    }

    // ─── Local Process Runner Helper ────────────────────────────────────────
    private void runLocalScript(String scriptPath, String arg) {
        new Thread(() -> {
            try {
                ProcessBuilder pb = new ProcessBuilder("C:\\Users\\viper\\AppData\\Local\\Programs\\Python\\Python311\\python.exe", scriptPath);
                if (arg != null && !arg.isEmpty()) {
                    pb.command().add(arg);
                }
                pb.redirectErrorStream(true);
                Process p = pb.start();
                BufferedReader reader = new BufferedReader(
                        new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8));
                String line;
                while ((line = reader.readLine()) != null) {
                    final String l = line;
                    Platform.runLater(() -> logOutput.appendText(l + "\n"));
                }
                p.waitFor();
                
                // Refresh relevant UI sections dynamically upon execution completion
                if (scriptPath.contains("automated_dependency_updates.py") || scriptPath.contains("otg_usb_transfer.py")) {
                    Platform.runLater(this::loadDependencyPlanAndDbHealth);
                } else if (scriptPath.contains("karoo_governor.py") || scriptPath.contains("viper_orchestrator.py") || scriptPath.contains("karoo_epoch_upgrade.py") || scriptPath.contains("karoo_recorder.py")) {
                    Platform.runLater(this::loadGovernanceTelemetry);
                }
            } catch (Exception e) {
                Platform.runLater(() -> logOutput.appendText("Script error: " + e.getMessage() + "\n"));
            }
        }).start();
    }

    // ─── HTTP Utilities ─────────────────────────────────────────────────────
    private static boolean probe(String urlStr) {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(urlStr))
                    .timeout(Duration.ofSeconds(1))
                    .GET()
                    .build();
            return HTTP.send(request, HttpResponse.BodyHandlers.ofString()).statusCode() == 200;
        } catch (Exception e) {
            return false;
        }
    }

    private static boolean isPortBound(int port) {
        try (java.net.Socket s = new java.net.Socket()) {
            s.connect(new java.net.InetSocketAddress("127.0.0.1", port), 200);
            return true;
        } catch (Exception e) {
            return false;
        }
    }

    private static String get(String urlStr) {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(urlStr))
                    .timeout(Duration.ofSeconds(3))
                    .GET()
                    .build();
            return HTTP.send(request, HttpResponse.BodyHandlers.ofString()).body();
        } catch (Exception e) {
            return "GET_ERROR: " + e.getMessage();
        }
    }

    private static String post(String urlStr, String jsonBody) {
        try {
            HttpRequest request = HttpRequest.newBuilder(URI.create(urlStr))
                    .timeout(Duration.ofSeconds(3))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(jsonBody))
                    .build();
            return HTTP.send(request, HttpResponse.BodyHandlers.ofString()).body();
        } catch (Exception e) {
            return "POST_ERROR: " + e.getMessage();
        }
    }

    private void triggerRollbacks() {
        logOutput.appendText("\n[SYS] Fetching Rollback Snapshots from server...\n");
        new Thread(() -> {
            String rawResponse = get(MANIFOLD_URL + "/api/backups");
            List<String> backupFiles = new ArrayList<>();
            try {
                if (rawResponse.contains("\"backups\"")) {
                    int start = rawResponse.indexOf("[") + 1;
                    int end = rawResponse.indexOf("]");
                    if (start > 0 && end > start) {
                        String listStr = rawResponse.substring(start, end);
                        for (String item : listStr.split(",")) {
                            String cleaned = item.replace("\"", "").replace("[", "").replace("]", "").trim();
                            if (!cleaned.isEmpty()) {
                                backupFiles.add(cleaned);
                            }
                        }
                    }
                }
            } catch (Exception ex) {}

            Platform.runLater(() -> {
                if (backupFiles.isEmpty()) {
                    Alert alert = new Alert(Alert.AlertType.WARNING);
                    alert.setTitle("System Rollbacks");
                    alert.setHeaderText("No Rollback Snapshots Found");
                    alert.setContentText("Check backend service is running on port 8085.");
                    alert.showAndWait();
                    return;
                }

                ChoiceDialog<String> dialog = new ChoiceDialog<>(backupFiles.get(0), backupFiles);
                dialog.setTitle("System Rollbacks");
                dialog.setHeaderText("Trigger Emergency System Rollback");
                dialog.setContentText("Select snapshot to restore local_knowledge.db:");

                java.util.Optional<String> result = dialog.showAndWait();
                if (result.isPresent()) {
                    String selectedBackup = result.get();
                    logOutput.appendText("[SYS] Restoring snapshot: " + selectedBackup + "...\n");
                    new Thread(() -> {
                        String postRes = post(MANIFOLD_URL + "/api/rollback", "{\"filename\":\"" + selectedBackup + "\"}");
                        Platform.runLater(() -> {
                            logOutput.appendText("[SYS] Rollback response: " + postRes + "\n");
                            loadDependencyPlanAndDbHealth();
                        });
                    }).start();
                }
            });
        }).start();
    }

    private void sendChatDirective() {
        String msg = chatInput.getText().strip();
        if (msg.isEmpty()) return;
        chatInput.clear();
        chatMessages.appendText("USER: " + msg + "\n");

        new Thread(() -> {
            String rawJson = post(MANIFOLD_URL + "/chat", "{\"message\":\"" + msg + "\"}");
            String cleanedResponse = rawJson;
            if (rawJson.contains("\"response\"")) {
                int start = rawJson.indexOf("\"response\"") + 10;
                int valStart = rawJson.indexOf("\"", start) + 1;
                int valEnd = rawJson.lastIndexOf("\"");
                if (valStart != -1 && valEnd != -1 && valEnd > valStart) {
                    cleanedResponse = rawJson.substring(valStart, valEnd)
                                             .replace("\\n", "\n")
                                             .replace("\\\"", "\"");
                }
            }
            final String text = cleanedResponse;
            Platform.runLater(() -> chatMessages.appendText("TRIPLET: " + text + "\n\n"));
        }).start();
    }

    private VBox createControlCard(String title, String desc, String lbl1, String val1, String lbl2, String val2, String btnTxt, Runnable action) {
        VBox card = new VBox(8);
        card.setPadding(new Insets(12));
        card.setStyle("-fx-background-color: #f6f8fa; -fx-border-color: #cfd6dc; -fx-border-radius: 8px;");

        Label tLabel = new Label(title);
        tLabel.setStyle("-fx-font-weight: bold; -fx-text-fill: #a8c7fa;");
        Label dLabel = new Label(desc);
        dLabel.setStyle("-fx-font-size: 10px; -fx-text-fill: #8b949e;");

        Label l1 = new Label(lbl1);
        TextField f1 = new TextField(val1);
        Label l2 = new Label(lbl2);
        TextField f2 = new TextField(val2);

        Button btn = new Button(btnTxt);
        btn.setOnAction(e -> new Thread(action).start());

        card.getChildren().addAll(tLabel, dLabel, l1, f1, l2, f2, btn);
        return card;
    }

    private String extractJSONValue(String json, String key) {
        int idx = json.indexOf("\"" + key + "\"");
        if (idx == -1) return "unknown";
        int start = json.indexOf(":", idx) + 1;
        int end = json.indexOf(",", start);
        if (end == -1) end = json.indexOf("}", start);
        return json.substring(start, end).replace("\"", "").replace(":", "").trim();
    }

    private void install3DTooltip(Node node, String text) {
        Tooltip tooltip = new Tooltip(text);
        node.setCursor(Cursor.HAND);
        node.setOnMouseEntered(e -> {
            tooltip.show(node, e.getScreenX() + 12, e.getScreenY() + 12);
        });
        node.setOnMouseExited(e -> {
            tooltip.hide();
        });
    }

    private Tab createGovernanceTab() {
        Tab tab = new Tab("Karoo Governance");
        tab.setClosable(false);

        HBox layout = new HBox(15);
        layout.setPadding(new Insets(20));

        // LEFT: Health reports, PoW, & Traceroute Path Logs
        VBox leftPane = new VBox(15);
        leftPane.setPrefWidth(480);

        // Panel 1: Health Reports
        VBox healthBox = new VBox(8);
        healthBox.setPadding(new Insets(12));
        healthBox.setStyle("-fx-background-color: #f6f8fa; -fx-border-color: #cfd6dc; -fx-border-radius: 8px;");
        Label healthTitle = new Label("Latest Karoo Health Sweep Summary");
        healthTitle.setStyle("-fx-text-fill: #24292f; -fx-font-size: 11px; -fx-font-weight: bold;");
        govHealthOutput.setEditable(false);
        govHealthOutput.setPrefHeight(110);
        govHealthOutput.setStyle("-fx-control-inner-background: #ffffff; -fx-text-fill: #1f2328; -fx-font-family: 'Consolas';");
        healthBox.getChildren().addAll(healthTitle, govHealthOutput);

        // Panel 2: PoW blocks mined
        VBox powBox = new VBox(8);
        powBox.setPadding(new Insets(12));
        powBox.setStyle("-fx-background-color: #f6f8fa; -fx-border-color: #cfd6dc; -fx-border-radius: 8px;");
        Label powTitle = new Label("Active Karoo Proof-of-Work (PoW) Blocks");
        powTitle.setStyle("-fx-text-fill: #24292f; -fx-font-size: 11px; -fx-font-weight: bold;");
        govPowOutput.setEditable(false);
        govPowOutput.setPrefHeight(110);
        govPowOutput.setStyle("-fx-control-inner-background: #ffffff; -fx-text-fill: #1f2328; -fx-font-family: 'Consolas';");
        powBox.getChildren().addAll(powTitle, govPowOutput);

        // Panel 3: Traceroute Path Logs (New Data Path Visualization!)
        VBox traceBox = new VBox(8);
        traceBox.setPadding(new Insets(12));
        traceBox.setStyle("-fx-background-color: #f6f8fa; -fx-border-color: #cfd6dc; -fx-border-radius: 8px;");
        Label traceTitle = new Label("Traceroute Status & Database Size Snapshots");
        traceTitle.setStyle("-fx-text-fill: #24292f; -fx-font-size: 11px; -fx-font-weight: bold;");
        govTraceOutput.setEditable(false);
        govTraceOutput.setPrefHeight(110);
        govTraceOutput.setStyle("-fx-control-inner-background: #ffffff; -fx-text-fill: #24292f; -fx-font-family: 'Consolas';");
        traceBox.getChildren().addAll(traceTitle, govTraceOutput);

        leftPane.getChildren().addAll(healthBox, powBox, traceBox);

        // RIGHT: Proposals accept/reject actions
        VBox rightPane = new VBox(10);
        HBox.setHgrow(rightPane, Priority.ALWAYS);
        rightPane.setPadding(new Insets(15));
        rightPane.setStyle("-fx-background-color: #f6f8fa; -fx-border-color: #cfd6dc; -fx-border-radius: 8px;");

        Label proposalsTitle = new Label("Pending Karoo Strategic Proposals");
        proposalsTitle.setStyle("-fx-text-fill: #24292f; -fx-font-size: 13px; -fx-font-weight: bold;");

        ScrollPane scrollPane = new ScrollPane(pendingProposalsContainer);
        scrollPane.setFitToWidth(true);
        scrollPane.setPrefHeight(360);
        scrollPane.setStyle("-fx-background-color: transparent; -fx-background: #ffffff; -fx-border-color: #cfd6dc; -fx-border-radius: 6px;");
        VBox.setVgrow(scrollPane, Priority.ALWAYS);

        HBox actionBox = new HBox(12);
        Button acceptBtn = new Button("Accept & Execute Proposals");
        acceptBtn.setOnAction(e -> {
            logOutput.appendText("\n[GOV] Accepting and deploying all proposals via Orchestrator...\n");
            runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\viper_orchestrator.py", "");
        });
        Button sweepBtn = new Button("Run Governance Sweep");
        sweepBtn.setOnAction(e -> {
            logOutput.appendText("\n[GOV] Requesting manual Karoo sweep scan...\n");
            runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\karoo_governor.py", "");
        });
        actionBox.getChildren().addAll(acceptBtn, sweepBtn);

        rightPane.getChildren().addAll(proposalsTitle, scrollPane, actionBox);

        layout.getChildren().addAll(leftPane, rightPane);
        tab.setContent(layout);
        return tab;
    }

    private void updateProposalStatus(String proposalId, String newStatus) {
        String dbUrl = "jdbc:sqlite:C:/Users/viper/VIPER_JAVA_RISC/java_notes_suite/data/graph.db";
        try (java.sql.Connection conn = java.sql.DriverManager.getConnection(dbUrl);
             java.sql.PreparedStatement pstmt = conn.prepareStatement("UPDATE karoo_proposals SET status=? WHERE proposal_id=?")) {
            pstmt.setString(1, newStatus);
            pstmt.setString(2, proposalId);
            pstmt.executeUpdate();
        } catch (Exception e) {
            System.err.println("Failed to update proposal status: " + e.getMessage());
        }
    }

    private int getRealOpenTodosCount() {
        String dbUrl = "jdbc:sqlite:C:/Users/viper/VIPER_JAVA_RISC/java_notes_suite/data/gemini_bridge.db";
        try (java.sql.Connection conn = java.sql.DriverManager.getConnection(dbUrl);
             java.sql.Statement stmt = conn.createStatement();
             java.sql.ResultSet rs = stmt.executeQuery("SELECT COUNT(*) FROM GLOBAL_TODO_QUEUE WHERE status='open'")) {
            if (rs.next()) {
                return rs.getInt(1);
            }
        } catch (Exception e) {}
        return 0;
    }

    private int getRealKnowledgeCount() {
        String dbUrl = "jdbc:sqlite:C:/Users/viper/VIPER_JAVA_RISC/java_notes_suite/data/local_knowledge.db";
        try (java.sql.Connection conn = java.sql.DriverManager.getConnection(dbUrl);
             java.sql.Statement stmt = conn.createStatement();
             java.sql.ResultSet rs = stmt.executeQuery("SELECT COUNT(*) FROM local_files")) {
            if (rs.next()) {
                return rs.getInt(1);
            }
        } catch (Exception e) {}
        return 0;
    }

    private int getRealProposalsCount() {
        String dbUrl = "jdbc:sqlite:C:/Users/viper/VIPER_JAVA_RISC/java_notes_suite/data/graph.db";
        try (java.sql.Connection conn = java.sql.DriverManager.getConnection(dbUrl);
             java.sql.Statement stmt = conn.createStatement();
             java.sql.ResultSet rs = stmt.executeQuery("SELECT COUNT(*) FROM karoo_proposals")) {
            if (rs.next()) {
                return rs.getInt(1);
            }
        } catch (Exception e) {}
        return 0;
    }

    private void loadGovernanceTelemetry() {
        String dbUrl = "jdbc:sqlite:C:/Users/viper/VIPER_JAVA_RISC/java_notes_suite/data/graph.db";
        try (java.sql.Connection conn = java.sql.DriverManager.getConnection(dbUrl)) {
            // 1. Get health reports
            try (java.sql.Statement stmt = conn.createStatement();
                 java.sql.ResultSet rs = stmt.executeQuery("SELECT timestamp, summary, risk_level FROM karoo_health_reports ORDER BY report_id DESC LIMIT 3")) {
                StringBuilder sb = new StringBuilder();
                while (rs.next()) {
                    sb.append(String.format("[%s] Risk: %s\nSummary: %s\n\n",
                        rs.getString("timestamp"), rs.getString("risk_level").toUpperCase(), rs.getString("summary")));
                }
                final String text = sb.toString();
                Platform.runLater(() -> govHealthOutput.setText(text.isEmpty() ? "No health reports found." : text));
            }
            
            // 2. Get active proposals
            List<VBox> proposalCards = new ArrayList<>();
            try (java.sql.Statement stmt = conn.createStatement();
                 java.sql.ResultSet rs = stmt.executeQuery("SELECT proposal_id, category, description, remediation_script, priority FROM karoo_proposals WHERE status='pending' LIMIT 6")) {
                while (rs.next()) {
                    String id = rs.getString("proposal_id");
                    String cat = rs.getString("category");
                    String desc = rs.getString("description");
                    String script = rs.getString("remediation_script");
                    int priority = rs.getInt("priority");
                    
                    VBox card = new VBox(6);
                    card.setPadding(new Insets(10));
                    card.setStyle("-fx-background-color: #ffffff; -fx-border-color: #cfd6dc; -fx-border-radius: 6px; -fx-background-radius: 6px;");
                    
                    Label titleLbl = new Label(String.format("[%s] %s (Priority: %d)", id, cat.toUpperCase(), priority));
                    titleLbl.setStyle("-fx-text-fill: #0969da; -fx-font-weight: bold; -fx-font-size: 11px;");
                    
                    Label descLbl = new Label(desc);
                    descLbl.setWrapText(true);
                    descLbl.setStyle("-fx-font-size: 10px; -fx-text-fill: #24292f;");
                    
                    HBox actionRow = new HBox(8);
                    Button accBtn = new Button("Accept");
                    accBtn.setStyle("-fx-background-color: #10b981; -fx-text-fill: white; -fx-font-weight: bold;");
                    accBtn.setOnAction(e -> {
                        updateProposalStatus(id, "accepted");
                        logOutput.appendText("\n[GOV] Proposal " + id + " ACCEPTED. Triggering execution plan...\n");
                        runLocalScript("C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\karoo_epoch_upgrade.py", "");
                        loadGovernanceTelemetry();
                    });
                    
                    Button rejBtn = new Button("Reject");
                    rejBtn.setStyle("-fx-background-color: #ef4444; -fx-text-fill: white; -fx-font-weight: bold;");
                    rejBtn.setOnAction(e -> {
                        updateProposalStatus(id, "rejected");
                        logOutput.appendText("\n[GOV] Proposal " + id + " REJECTED.\n");
                        loadGovernanceTelemetry();
                    });
                    
                    actionRow.getChildren().addAll(accBtn, rejBtn);
                    card.getChildren().addAll(titleLbl, descLbl, actionRow);
                    proposalCards.add(card);
                }
            }
            Platform.runLater(() -> {
                pendingProposalsContainer.getChildren().clear();
                if (proposalCards.isEmpty()) {
                    Label noneLbl = new Label("No pending proposals found.");
                    noneLbl.setStyle("-fx-text-fill: #57606a; -fx-font-style: italic;");
                    pendingProposalsContainer.getChildren().add(noneLbl);
                } else {
                    pendingProposalsContainer.getChildren().addAll(proposalCards);
                }
            });

            // 3. Get PoW blocks
            try (java.sql.Statement stmt = conn.createStatement();
                 java.sql.ResultSet rs = stmt.executeQuery("SELECT block_id, hash, timestamp FROM karoo_pow_blocks ORDER BY timestamp DESC LIMIT 3")) {
                StringBuilder sb = new StringBuilder();
                while (rs.next()) {
                    sb.append(String.format("Block: %s\nHash: %s\nMined: %s\n\n",
                        rs.getString("block_id"), rs.getString("hash"), rs.getString("timestamp")));
                }
                final String text = sb.toString();
                Platform.runLater(() -> govPowOutput.setText(text.isEmpty() ? "No PoW blocks mined." : text));
            }

            // 4. Get Traceroute logs
            try (java.sql.Statement stmt = conn.createStatement();
                 java.sql.ResultSet rs = stmt.executeQuery("SELECT timestamp, status, details FROM karoo_traceroute ORDER BY trace_id DESC LIMIT 2")) {
                StringBuilder sb = new StringBuilder();
                while (rs.next()) {
                    sb.append(String.format("[%s] Path Status: %s\nSnapshots: %s\n\n",
                        rs.getString("timestamp"), rs.getString("status"), rs.getString("details").replace("{", "").replace("}", "").replace("\"", "").replace("db_snapshots:", "").replace("script_resolution:", "").trim()));
                }
                final String text = sb.toString();
                Platform.runLater(() -> govTraceOutput.setText(text.isEmpty() ? "No traceroute records found." : text));
            }
        } catch (Exception e) {}
    }

    private static void ensureServersRunning() {
        // Manifold Server (8085)
        if (!isPortBound(8085)) {
            new Thread(() -> {
                try {
                    Class.forName("org.sqlite.JDBC");
                    OmniNetworkManifold.main(new String[0]);
                } catch (Exception e) {
                    System.err.println("Failed starting OmniNetworkManifold: " + e.getMessage());
                }
            }, "OmniNetworkManifold-Thread").start();
        }

        // Lab Server (18181)
        if (!isPortBound(18181)) {
            new Thread(() -> {
                try {
                    ViperLabSuiteServer.main(new String[0]);
                } catch (Exception e) {
                    System.err.println("Failed starting ViperLabSuiteServer: " + e.getMessage());
                }
            }, "ViperLabSuiteServer-Thread").start();
        }

        // Notes Server (8091)
        if (!isPortBound(8091)) {
            new Thread(() -> {
                try {
                    ViperNotesServer.main(new String[0]);
                } catch (Exception e) {
                    System.err.println("Failed starting ViperNotesServer: " + e.getMessage());
                }
            }, "ViperNotesServer-Thread").start();
        }

        // --- Start Python Headless Services (Step 167 Integration) ---
        
        // 1. OTG GAN Bridge (18082)
        if (!isPortBound(18082)) {
            new Thread(() -> {
                try {
                    ProcessBuilder pb = new ProcessBuilder(
                        "C:\\Users\\viper\\AppData\\Local\\Programs\\Python\\Python311\\python.exe", 
                        "C:\\Users\\viper\\VIPER_JAVA_RISC\\otg_gan_bridge.py"
                    );
                    Process p = pb.start();
                    SPAWNED_PROCESSES.add(p);
                    System.out.println("[EMBEDDED] Started otg_gan_bridge.py");
                } catch (Exception e) {
                    System.err.println("Failed starting otg_gan_bridge.py: " + e.getMessage());
                }
            }, "Embedded-Otg-Bridge").start();
        }

        // 2. House Inference Server (11435)
        if (!isPortBound(11435)) {
            new Thread(() -> {
                try {
                    ProcessBuilder pb = new ProcessBuilder(
                        "C:\\Users\\viper\\AppData\\Local\\Programs\\Python\\Python311\\python.exe", 
                        "C:\\Users\\viper\\house_inference_engine.py"
                    );
                    Process p = pb.start();
                    SPAWNED_PROCESSES.add(p);
                    System.out.println("[EMBEDDED] Started house_inference_engine.py");
                } catch (Exception e) {
                    System.err.println("Failed starting house_inference_engine.py: " + e.getMessage());
                }
            }, "Embedded-House-Inference").start();
        }

        // 3. Cognitive Injector Daemon (Running loop in background)
        new Thread(() -> {
            try {
                ProcessBuilder pb = new ProcessBuilder(
                    "C:\\Users\\viper\\AppData\\Local\\Programs\\Python\\Python311\\python.exe", 
                    "C:\\Users\\viper\\VIPER_JAVA_RISC\\tools\\viper_cognitive_injector.py",
                    "--loop"
                );
                Process p = pb.start();
                SPAWNED_PROCESSES.add(p);
                System.out.println("[EMBEDDED] Started viper_cognitive_injector.py loop");
            } catch (Exception e) {
                System.err.println("Failed starting viper_cognitive_injector.py: " + e.getMessage());
            }
        }, "Embedded-Cognitive-Injector").start();
    }

    private void sendSpriteChatDirective() {
        String msg = spriteChatInput.getText().strip();
        if (msg.isEmpty()) return;
        spriteChatInput.clear();
        spriteChatArea.appendText("USER: " + msg + "\n");

        new Thread(() -> {
            String rawJson = post("http://127.0.0.1:18285/chat", "{\"message\":\"" + msg + "\"}");
            String cleanedResponse = rawJson;
            String thought = "";
            String route = "";
            
            try {
                if (rawJson.contains("\"response\"")) {
                    int start = rawJson.indexOf("\"response\"") + 10;
                    int valStart = rawJson.indexOf("\"", start) + 1;
                    int valEnd = rawJson.indexOf("\"", valStart);
                    if (valStart > 0 && valEnd > valStart) {
                        cleanedResponse = rawJson.substring(valStart, valEnd).replace("\\n", "\n").replace("\\\"", "\"");
                    }
                }
                if (rawJson.contains("\"thought\"")) {
                    int start = rawJson.indexOf("\"thought\"") + 9;
                    int valStart = rawJson.indexOf("\"", start) + 1;
                    int valEnd = rawJson.indexOf("\"", valStart);
                    if (valStart > 0 && valEnd > valStart) {
                        thought = rawJson.substring(valStart, valEnd);
                    }
                }
                if (rawJson.contains("\"route\"")) {
                    int start = rawJson.indexOf("\"route\"") + 7;
                    int valStart = rawJson.indexOf("[", start);
                    int valEnd = rawJson.indexOf("]", valStart);
                    if (valStart != -1 && valEnd > valStart) {
                        route = rawJson.substring(valStart, valEnd + 1).replace("\"", "");
                    }
                }
            } catch (Exception ex) {}
            
            final String text = cleanedResponse;
            final String th = thought;
            final String rt = route;
            
            Platform.runLater(() -> {
                if (!th.isEmpty()) {
                    spriteChatArea.appendText("OVERSEER THOUGHT: " + th + "\n");
                }
                if (!rt.isEmpty()) {
                    spriteChatArea.appendText("DISPATCH ROUTE: " + rt + "\n");
                }
                spriteChatArea.appendText("RESPONSE: " + text + "\n\n");
            });
        }).start();
    }

    private void updateModelRegistry(String role, String modelPath, String loraPath) {
        String dbUrl = "jdbc:sqlite:C:/Users/viper/VIPER_JAVA_RISC/java_notes_suite/data/graph.db";
        try (java.sql.Connection conn = java.sql.DriverManager.getConnection(dbUrl)) {
            // Guarantee table exists in case sweep hasn't run
            try (java.sql.Statement stmt = conn.createStatement()) {
                stmt.execute("CREATE TABLE IF NOT EXISTS inference_model_registry (sprite_role TEXT PRIMARY KEY, file_path TEXT, lora_path TEXT, status TEXT)");
            }
            
            // Set other entries for this role to inactive
            try (java.sql.PreparedStatement ps = conn.prepareStatement(
                    "UPDATE inference_model_registry SET status='inactive' WHERE sprite_role=?")) {
                ps.setString(1, role);
                ps.executeUpdate();
            }
            
            // Insert or replace new active entry
            try (java.sql.PreparedStatement ps = conn.prepareStatement(
                    "INSERT OR REPLACE INTO inference_model_registry (sprite_role, file_path, lora_path, status) VALUES (?, ?, ?, 'active')")) {
                ps.setString(1, role);
                ps.setString(2, modelPath);
                ps.setString(3, loraPath);
                ps.executeUpdate();
            }
            
            Platform.runLater(() -> logOutput.appendText(String.format(
                "[REGISTRY] Model configuration deployed to registry for role [%s]: %s (LoRA: %s)\n",
                role, new java.io.File(modelPath).getName(), loraPath.isEmpty() ? "none" : new java.io.File(loraPath).getName()
            )));
        } catch (Exception e) {
            Platform.runLater(() -> logOutput.appendText("[REGISTRY ERROR] Failed to update model registry: " + e.getMessage() + "\n"));
        }
    }

    public static void main(String[] args) {
        ensureServersRunning();
        launch(args);
    }
}
