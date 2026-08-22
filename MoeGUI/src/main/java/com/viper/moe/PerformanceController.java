package com.viper.moe;

import javafx.animation.KeyFrame;
import javafx.animation.Timeline;
import javafx.application.Platform;
import javafx.beans.property.SimpleStringProperty;
import javafx.geometry.Insets;
import javafx.scene.Parent;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import javafx.scene.text.Font;
import javafx.scene.text.FontWeight;
import javafx.util.Duration;

import java.sql.*;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * Performance & Updates tab.
 * Shows all proposals (pending/approved/implemented/declined) with status filter.
 * Reads directly from SQLite — no Python bridge needed for display.
 * Action buttons write back via SQLite.
 */
public class PerformanceController {

    static final String TELE_DB = "C:\\Viper\\databases\\telemetry\\telemetry.db";
    static final String PROJ_DB = "C:\\Viper\\databases\\projects\\projects.db";

    /**
     * Open a SQLite connection with busy_timeout + WAL applied via the JDBC URL.
     * The old code ran `PRAGMA journal_mode=WAL` through createStatement().execute(...)
     * without closing the statement — PRAGMA returns a row, so that left an open cursor
     * and the next auto-commit failed with
     * "cannot commit transaction - SQL statements in progress". Setting the pragmas as
     * URL parameters lets the driver apply them at init (no dangling cursor, no need to
     * `requires` the sqlite module) and makes every connection wait up to 5s for a lock.
     */
    private static Connection open(String db) throws SQLException {
        return DriverManager.getConnection(
            "jdbc:sqlite:" + db + "?busy_timeout=5000&journal_mode=WAL");
    }

    public record UpdateRow(int id, String hashId, String project, String agent,
                            String summary, String diffType, double score,
                            String createdAt, String status) {}

    public record RagRow(String ts, String query, double totalS, String stages) {}
    public record PedagogyRow(String ts, String category, String insight, String severity) {}
    public record HeroRow(int step, double loss, String ts) {}
    public record FeedRow(String ts, String agent, String kind, String message,
                          String status, int confirmed) {}
    public record NoteRow(String ts, String machine, String category, String title, String source,
                          String content) {}

    private final Label                     machineInfo   = new Label("Loading...");
    private final VBox                      agentBox      = new VBox(3);
    private final TableView<UpdateRow>      updatesTable  = new TableView<>();
    private final Label                     pendingCount  = new Label("Pending: ?");
    private final ComboBox<String>          statusFilter  = new ComboBox<>();
    private final TableView<RagRow>         ragTable      = new TableView<>();
    private final TableView<PedagogyRow>    pedagogyTable = new TableView<>();
    private final TableView<HeroRow>        heroTable     = new TableView<>();
    private final TextArea                  gitArea       = new TextArea();
    private final Label                     errorLabel    = new Label("");
    private final TableView<FeedRow>        feedTable      = new TableView<>();
    private final TableView<NoteRow>        notesTable     = new TableView<>();
    private final Label                     guardrailLabel = new Label("guardrails: loading...");
    private final Button                    dryRunBtn      = new Button();
    private final Button                    autonomyBtn    = new Button();
    private final Button                    autoPushBtn    = new Button();
    private final Button                    pauseBtn       = new Button();
    private Timeline                        autoRefresh;

    public Parent buildLayout() {

        machineInfo.setFont(Font.font("Consolas", 10));
        machineInfo.setStyle("-fx-text-fill:#88cc99;");
        machineInfo.setWrapText(true);

        VBox machineBox = new VBox(6, sectionHeader("MACHINE METRICS"), machineInfo);
        machineBox.setPadding(new Insets(8));
        machineBox.getStyleClass().add("sidebar");
        machineBox.setPrefWidth(320);

        VBox agentPanel = new VBox(6, sectionHeader("AGENT NOD FITNESS"), agentBox);
        agentPanel.setPadding(new Insets(8));
        agentPanel.getStyleClass().add("sidebar");
        agentPanel.setPrefWidth(320);

        HBox topBar = new HBox(8, machineBox, agentPanel);
        topBar.setPadding(new Insets(4));
        topBar.setPrefHeight(160);

        // ── PROPOSED UPDATES ──────────────────────────────────────────────────
        buildUpdatesTable();
        Button refreshBtn = new Button("REFRESH");
        refreshBtn.getStyleClass().add("clear-btn");
        refreshBtn.setOnAction(e -> loadAll());

        Button autoBtn = new Button("AUTO: ON");
        autoBtn.getStyleClass().add("send-btn");
        autoBtn.setOnAction(e -> toggleAutoRefresh(autoBtn));

        Button approveAllBtn = new Button("APPROVE ALL");
        approveAllBtn.setStyle("-fx-background-color:#003300; -fx-text-fill:#00ff41; " +
            "-fx-border-color:#00ff41; -fx-border-radius:2; -fx-background-radius:2; " +
            "-fx-padding:4 10; -fx-font-size:9px; -fx-cursor:hand;");
        approveAllBtn.setOnAction(e -> approveAllPending());

        statusFilter.getItems().addAll("ALL", "pending", "approved", "verified",
                                       "implemented", "needs_fix", "declined");
        statusFilter.setValue("ALL");
        statusFilter.setStyle("-fx-background-color:#0a110a; -fx-text-fill:#00ff41; " +
            "-fx-border-color:#1a4a1a; -fx-font-size:10px;");
        statusFilter.setOnAction(e -> loadAll());

        pendingCount.setStyle("-fx-text-fill: #00ff41; -fx-font-size: 11px;");
        errorLabel.setStyle("-fx-text-fill:#ff4444; -fx-font-size:9px;");

        Region spacer = new Region();
        HBox.setHgrow(spacer, Priority.ALWAYS);
        HBox tableBar = new HBox(6,
            sectionHeader("PROPOSED UPDATES"), pendingCount, statusFilter,
            spacer, errorLabel, approveAllBtn, refreshBtn, autoBtn);
        tableBar.setAlignment(javafx.geometry.Pos.CENTER_LEFT);
        tableBar.setPadding(new Insets(4, 8, 4, 8));

        VBox.setVgrow(updatesTable, Priority.ALWAYS);
        VBox updatesPanel = new VBox(4, tableBar, updatesTable);
        updatesPanel.setPadding(new Insets(4));

        // ── RAG + Pedagogy ────────────────────────────────────────────────────
        buildRagTable();
        VBox ragPanel = new VBox(4, sectionHeader("RAG CHAIN RESULTS (last 10)"), ragTable);
        ragPanel.setPadding(new Insets(8));

        buildPedagogyTable();
        VBox pedagogyPanel = new VBox(4, sectionHeader("PEDAGOGY INSIGHTS"), pedagogyTable);
        pedagogyPanel.setPadding(new Insets(8));

        SplitPane midSplit = new SplitPane(ragPanel, pedagogyPanel);
        midSplit.setDividerPositions(0.55);
        midSplit.setPrefHeight(140);

        // ── Hero Kernel + Git ─────────────────────────────────────────────────
        buildHeroTable();
        VBox heroPanel = new VBox(4, sectionHeader("HERO KERNEL (LoRA AdamW)"), heroTable);
        heroPanel.setPadding(new Insets(8));

        gitArea.setEditable(false);
        gitArea.setStyle("-fx-control-inner-background:#050a05; -fx-text-fill:#00ff41; " +
                         "-fx-font-family:Consolas; -fx-font-size:10px;");
        gitArea.setPrefHeight(100);
        VBox gitPanel = new VBox(4, sectionHeader("GIT STATUS"), gitArea);
        gitPanel.setPadding(new Insets(8));

        SplitPane bottomSplit = new SplitPane(heroPanel, gitPanel);
        bottomSplit.setDividerPositions(0.50);
        bottomSplit.setPrefHeight(120);

        // ── GUARDRAILS bar + central AGENT UPDATES FEED ───────────────────────
        HBox guardrailBar = buildGuardrailBar();

        buildFeedTable();
        VBox feedPanel = new VBox(4,
            sectionHeader("AGENT UPDATES FEED (central — all agents report here)"), feedTable);
        feedPanel.setPadding(new Insets(8));
        feedPanel.setPrefHeight(150);
        VBox.setVgrow(feedTable, Priority.ALWAYS);

        // ── Organised into clean sub-tabs (declutter) ─────────────────────────
        // UPDATES — guardrails + proposals (the primary action surface)
        VBox updatesTab = new VBox(6, guardrailBar, updatesPanel);
        updatesTab.setPadding(new Insets(6));
        updatesTab.setStyle("-fx-background-color:#050a05;");
        VBox.setVgrow(updatesPanel, Priority.ALWAYS);

        // ACTIVITY — central agent feed, full height
        VBox activityTab = new VBox(4, feedPanel);
        activityTab.setPadding(new Insets(6));
        activityTab.setStyle("-fx-background-color:#050a05;");
        VBox.setVgrow(feedPanel, Priority.ALWAYS);

        // LEARNING — RAG + Pedagogy + Hero kernel
        VBox learningTab = new VBox(6, midSplit, bottomSplit);
        learningTab.setPadding(new Insets(6));
        learningTab.setStyle("-fx-background-color:#050a05;");
        VBox.setVgrow(midSplit, Priority.ALWAYS);
        VBox.setVgrow(bottomSplit, Priority.ALWAYS);

        // SYSTEM — machine metrics + agent fitness
        VBox systemTab = new VBox(4, topBar);
        systemTab.setPadding(new Insets(6));
        systemTab.setStyle("-fx-background-color:#050a05;");
        VBox.setVgrow(topBar, Priority.ALWAYS);

        // NOTES — auto-harvested documentation from all sources/machines
        buildNotesTable();
        VBox notesTab = new VBox(4,
            sectionHeader("NOTES (auto-harvested: docs, decisions, plans, chats, Kai)"), notesTable);
        notesTab.setPadding(new Insets(6));
        notesTab.setStyle("-fx-background-color:#050a05;");
        VBox.setVgrow(notesTable, Priority.ALWAYS);

        TabPane subTabs = new TabPane();
        subTabs.setTabClosingPolicy(TabPane.TabClosingPolicy.UNAVAILABLE);
        subTabs.getTabs().addAll(
            mkSubTab("UPDATES",  updatesTab),
            mkSubTab("ACTIVITY", activityTab),
            mkSubTab("NOTES",    notesTab),
            mkSubTab("LEARNING", learningTab),
            mkSubTab("SYSTEM",   systemTab));
        subTabs.setStyle("-fx-background-color:#050a05;");

        loadAll();
        startAutoRefresh();
        return subTabs;
    }

    private Tab mkSubTab(String title, javafx.scene.Node content) {
        Tab t = new Tab(title, content);
        t.setClosable(false);
        return t;
    }

    // ── Updates table ─────────────────────────────────────────────────────────

    private void buildUpdatesTable() {
        updatesTable.setColumnResizePolicy(TableView.CONSTRAINED_RESIZE_POLICY_FLEX_LAST_COLUMN);
        updatesTable.setStyle("-fx-background-color:#050a05; -fx-border-color:#00ff41; -fx-border-width:1;");
        updatesTable.setPlaceholder(new Label("No proposals yet — autonomous_loop is running in background"));

        TableColumn<UpdateRow, String> hashCol  = col("HASH",    70,  r -> r.hashId() != null ? r.hashId() : "");
        TableColumn<UpdateRow, String> projCol  = col("PROJECT", 100, r -> r.project() != null ? r.project() : "");
        TableColumn<UpdateRow, String> stCol    = col("STATUS",  80,  r -> r.status() != null ? r.status() : "");
        TableColumn<UpdateRow, String> typeCol  = col("TYPE",    75,  r -> r.diffType() != null ? r.diffType() : "");
        TableColumn<UpdateRow, String> scoreCol = col("SCORE",   55,  r -> String.format("%.1f", r.score()));
        TableColumn<UpdateRow, String> summaryCol = col("SUMMARY", 380, r ->
            r.summary() != null ? r.summary().replace("\n", " ") : "");
        TableColumn<UpdateRow, String> tsCol    = col("CREATED", 100,
            r -> r.createdAt() != null && r.createdAt().length() > 16
                ? r.createdAt().substring(0, 16) : (r.createdAt() != null ? r.createdAt() : ""));

        // Color-code status column
        stCol.setCellFactory(col -> new TableCell<>() {
            @Override protected void updateItem(String item, boolean empty) {
                super.updateItem(item, empty);
                if (empty || item == null) { setText(null); setStyle(""); return; }
                setText(item);
                setStyle(switch (item) {
                    case "pending"     -> "-fx-text-fill:#ffaa00;";
                    case "approved"    -> "-fx-text-fill:#00ff88;";
                    case "verified"    -> "-fx-text-fill:#00ffcc;";
                    case "implemented" -> "-fx-text-fill:#00cfff;";
                    case "needs_fix"   -> "-fx-text-fill:#ff8800;";
                    case "declined"    -> "-fx-text-fill:#ff4444;";
                    case "failed"      -> "-fx-text-fill:#ff6666;";
                    default            -> "-fx-text-fill:#aaaaaa;";
                });
            }
        });

        TableColumn<UpdateRow, Void> actionCol = new TableColumn<>("ACTION");
        actionCol.setPrefWidth(280);
        actionCol.setCellFactory(colParam -> new TableCell<>() {
            private final Button appr = btnAction("APPROVE",   "#003300", "#00ff41");
            private final Button decl = btnAction("DECLINE",   "#330000", "#ff4444");
            private final Button upgr = btnAction("IMPLEMENT", "#001a33", "#00cfff");
            private final Button cmnt = btnAction("COMMENT",   "#1a1a00", "#ffff44");
            private final HBox   box  = new HBox(3, appr, decl, upgr, cmnt);
            {
                appr.setOnAction(e -> applyStatus("approved", ""));
                decl.setOnAction(e -> applyStatus("declined", ""));
                upgr.setOnAction(e -> applyStatus("implemented", "manual via UI"));
                cmnt.setOnAction(e -> {
                    TextInputDialog dlg = new TextInputDialog();
                    dlg.setTitle("Comment"); dlg.setHeaderText("Add comment:");
                    dlg.setContentText("Comment:");
                    dlg.getDialogPane().setStyle("-fx-background-color:#050a05;");
                    Optional<String> res = dlg.showAndWait();
                    res.ifPresent(c -> applyStatus("commented", c));
                });
            }
            private void applyStatus(String status, String comment) {
                int idx = getIndex();
                if (idx < 0 || idx >= getTableView().getItems().size()) return;
                UpdateRow row = getTableView().getItems().get(idx);
                setUpdateStatus(row.id(), status, comment);
                loadAll();
            }
            @Override protected void updateItem(Void item, boolean empty) {
                super.updateItem(item, empty);
                setGraphic(empty ? null : box);
            }
        });

        updatesTable.getColumns().addAll(hashCol, projCol, stCol, typeCol, scoreCol,
                                          summaryCol, tsCol, actionCol);
    }

    private void buildRagTable() {
        ragTable.setColumnResizePolicy(TableView.CONSTRAINED_RESIZE_POLICY_FLEX_LAST_COLUMN);
        ragTable.setStyle("-fx-background-color:#050a05;");
        ragTable.setPrefHeight(110);
        ragTable.setPlaceholder(new Label("RAG probes will appear here (autonomous_loop runs every 4min)"));
        ragTable.getColumns().addAll(
            col("TIME",   75,  r -> r.ts() != null && r.ts().length() > 16 ? r.ts().substring(11, 16) : (r.ts() != null ? r.ts() : "")),
            col("QUERY",  220, r -> r.query() != null ? r.query() : ""),
            col("TOTAL",  55,  r -> r.totalS() + "s"),
            col("STAGES", 250, r -> r.stages() != null ? r.stages().replace("\"","").replace("{","").replace("}","") : "")
        );
    }

    private void buildPedagogyTable() {
        pedagogyTable.setColumnResizePolicy(TableView.CONSTRAINED_RESIZE_POLICY_FLEX_LAST_COLUMN);
        pedagogyTable.setStyle("-fx-background-color:#050a05;");
        pedagogyTable.setPrefHeight(110);
        pedagogyTable.setPlaceholder(new Label("Pedagogy insights populate every 10min (autonomous_loop)"));
        pedagogyTable.getColumns().addAll(
            col("TIME",     70,  (PedagogyRow r) -> r.ts() != null && r.ts().length() > 16 ? r.ts().substring(11, 16) : (r.ts() != null ? r.ts() : "")),
            col("CATEGORY", 90,  (PedagogyRow r) -> r.category() != null ? r.category() : ""),
            col("SEV",      45,  (PedagogyRow r) -> r.severity() != null ? r.severity() : ""),
            col("INSIGHT",  380, (PedagogyRow r) -> r.insight() != null ? r.insight() : "")
        );
    }

    private void buildHeroTable() {
        heroTable.setColumnResizePolicy(TableView.CONSTRAINED_RESIZE_POLICY_FLEX_LAST_COLUMN);
        heroTable.setStyle("-fx-background-color:#050a05;");
        heroTable.setPrefHeight(100);
        heroTable.setPlaceholder(new Label("Hero kernel trains every 60min (epoch upgrade) — 5000 steps → distil"));
        heroTable.getColumns().addAll(
            col("STEP", 80, (HeroRow r) -> String.valueOf(r.step())),
            col("LOSS", 95, (HeroRow r) -> String.format("%.5f", r.loss())),
            col("TIME", 120, (HeroRow r) -> r.ts() != null && r.ts().length() > 16 ? r.ts().substring(11, 16) : (r.ts() != null ? r.ts() : ""))
        );
    }

    // ── Data loaders ──────────────────────────────────────────────────────────

    private void loadAll() {
        Thread.ofVirtual().start(() -> {
            loadMachineMetrics();
            loadAgentMetrics();
            loadUpdates();
            loadRagResults();
            loadGitStatus();
            loadPedagogy();
            loadHeroKernel();
            loadFeed();
            loadGuardrails();
            loadNotes();
        });
    }

    private void buildNotesTable() {
        notesTable.setColumnResizePolicy(TableView.CONSTRAINED_RESIZE_POLICY_FLEX_LAST_COLUMN);
        notesTable.setStyle("-fx-background-color:#050a05; -fx-border-color:#00cfff; -fx-border-width:1;");
        notesTable.setPlaceholder(new Label("Notes auto-populate here (docs, blueprints, decisions, plans, Kai chats)"));
        TableColumn<NoteRow, String> tsCol  = col("WHEN", 80,
            r -> r.ts() != null && r.ts().length() > 16 ? r.ts().substring(5, 16) : (r.ts() != null ? r.ts() : ""));
        TableColumn<NoteRow, String> mcCol  = col("MACHINE", 100, r -> r.machine() != null ? r.machine() : "");
        TableColumn<NoteRow, String> catCol = col("CATEGORY", 90, r -> r.category() != null ? r.category() : "");
        TableColumn<NoteRow, String> ttCol  = col("TITLE", 360, r -> r.title() != null ? r.title() : "");
        TableColumn<NoteRow, String> srcCol = col("SOURCE", 220, r -> {
            String s = r.source(); if (s == null) return "";
            int i = Math.max(s.lastIndexOf('\\'), s.lastIndexOf('/'));
            return i >= 0 ? s.substring(i + 1) : s;
        });
        catCol.setCellFactory(c -> new TableCell<>() {
            @Override protected void updateItem(String item, boolean empty) {
                super.updateItem(item, empty);
                if (empty || item == null) { setText(null); setStyle(""); return; }
                setText(item);
                setStyle(switch (item) {
                    case "blueprint", "plan" -> "-fx-text-fill:#00cfff;";
                    case "sop", "context"    -> "-fx-text-fill:#00ff88;";
                    case "kai"               -> "-fx-text-fill:#ffaa00;";
                    case "readme", "doc"     -> "-fx-text-fill:#88cc99;";
                    default                  -> "-fx-text-fill:#aaaaaa;";
                });
            }
        });
        notesTable.getColumns().addAll(tsCol, mcCol, catCol, ttCol, srcCol);

        // Double-click a note row to open the full entry in a viewer.
        notesTable.setRowFactory(tv -> {
            TableRow<NoteRow> row = new TableRow<>();
            row.setOnMouseClicked(e -> {
                if (e.getClickCount() == 2 && !row.isEmpty()) {
                    openNote(row.getItem());
                }
            });
            return row;
        });
    }

    /** Open a single harvested note: full content + metadata, with an option to open the source file. */
    private void openNote(NoteRow r) {
        if (r == null) return;
        String title  = r.title()  != null ? r.title()  : "(untitled)";
        String source = r.source() != null ? r.source() : "";
        String body   = r.content() != null && !r.content().isBlank()
                ? r.content()
                : "(no harvested content for this note)\n\nSource: " + source;

        TextArea area = new TextArea(body);
        area.setEditable(false);
        area.setWrapText(true);
        area.setPrefSize(720, 520);
        area.setStyle("-fx-control-inner-background:#050a05; -fx-text-fill:#c8ffd8; "
                    + "-fx-font-family:'Consolas','monospace'; -fx-font-size:13;");

        Label meta = new Label(String.format("%s  |  machine: %s  |  category: %s  |  %s",
                title,
                r.machine()  != null ? r.machine()  : "?",
                r.category() != null ? r.category() : "?",
                r.ts()       != null ? r.ts()       : ""));
        meta.setStyle("-fx-text-fill:#00cfff; -fx-font-weight:bold;");
        Label src = new Label(source.isBlank() ? "" : "source: " + source);
        src.setStyle("-fx-text-fill:#88cc99; -fx-font-size:11;");

        VBox content = new VBox(6, meta, src, area);
        content.setPadding(new Insets(10));
        content.setStyle("-fx-background-color:#050a05;");
        VBox.setVgrow(area, Priority.ALWAYS);

        Dialog<ButtonType> dlg = new Dialog<>();
        dlg.setTitle("Note — " + title);
        dlg.setResizable(true);
        dlg.getDialogPane().setContent(content);
        dlg.getDialogPane().setStyle("-fx-background-color:#050a05;");
        ButtonType openSrc = new ButtonType("Open Source File", ButtonBar.ButtonData.LEFT);
        dlg.getDialogPane().getButtonTypes().addAll(openSrc, ButtonType.CLOSE);

        // Make the "Open Source File" button run without closing the dialog.
        final String srcPath = source;
        Button openBtn = (Button) dlg.getDialogPane().lookupButton(openSrc);
        if (openBtn != null) {
            openBtn.setDisable(srcPath.isBlank());
            openBtn.addEventFilter(javafx.event.ActionEvent.ACTION, ev -> {
                ev.consume();
                openSourceFile(srcPath);
            });
        }
        dlg.showAndWait();
    }

    /** Open a note's underlying source file in the OS default application, if it exists. */
    private void openSourceFile(String path) {
        try {
            java.io.File f = new java.io.File(path);
            if (f.exists() && java.awt.Desktop.isDesktopSupported()) {
                java.awt.Desktop.getDesktop().open(f);
            }
        } catch (Exception ignored) { }
    }

    private void loadNotes() {
        List<NoteRow> rows = new ArrayList<>();
        try (Connection con = open(TELE_DB)) {
            con.createStatement().execute(
                "CREATE TABLE IF NOT EXISTS harvested_notes (id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "hash TEXT UNIQUE, machine TEXT, source TEXT, category TEXT, title TEXT, " +
                "content TEXT, created_at TEXT)");
            try (ResultSet rs = con.createStatement().executeQuery(
                     "SELECT created_at, machine, category, title, source, content FROM harvested_notes " +
                     "ORDER BY id DESC LIMIT 80")) {
                while (rs.next()) {
                    rows.add(new NoteRow(rs.getString(1), rs.getString(2), rs.getString(3),
                                         rs.getString(4), rs.getString(5), rs.getString(6)));
                }
            }
        } catch (Exception e) {
            rows.add(new NoteRow("?", "system", "error", "harvested_notes: " + e.getMessage(), "", ""));
        }
        final List<NoteRow> fr = rows;
        Platform.runLater(() -> notesTable.getItems().setAll(fr));
    }

    private void loadMachineMetrics() {
        StringBuilder sb = new StringBuilder();
        try (Connection con = open(TELE_DB)) {
            try (ResultSet rs = con.createStatement().executeQuery(
                     "SELECT machine_id, arch, bits, has_avx, has_gpu, ram_gb, registered_at " +
                     "FROM machine_registry ORDER BY registered_at DESC LIMIT 3")) {
                while (rs.next()) {
                    sb.append(String.format("%-16s %s %sbit AVX=%s GPU=%s RAM=%sGB%n",
                        rs.getString(1), rs.getString(2), rs.getString(3),
                        rs.getString(4), rs.getString(5), rs.getString(6)));
                }
            }
        } catch (Exception e) {
            sb.append("machine_registry: ").append(e.getMessage());
        }
        final String txt = sb.length() > 0 ? sb.toString() : "No machines registered yet";
        Platform.runLater(() -> machineInfo.setText(txt));
    }

    private void loadAgentMetrics() {
        List<Label> labels = new ArrayList<>();
        try (Connection con = open(TELE_DB)) {
            try (ResultSet rs = con.createStatement().executeQuery(
                     "SELECT agent_id, COUNT(*) as calls FROM agent_events " +
                     "GROUP BY agent_id ORDER BY calls DESC LIMIT 12")) {
                while (rs.next()) {
                    String text = String.format("%-22s calls=%d", rs.getString(1), rs.getInt(2));
                    Label l = new Label(text);
                    l.setFont(Font.font("Consolas", 10));
                    l.setStyle("-fx-text-fill:#88cc99;");
                    labels.add(l);
                }
            }
        } catch (Exception e) {
            Label l = new Label("agent_events: " + e.getMessage());
            l.setStyle("-fx-text-fill:#ff6666; -fx-font-size:10px;");
            labels.add(l);
        }
        if (labels.isEmpty()) {
            Label l = new Label("No agent events yet — system starting up");
            l.setStyle("-fx-text-fill:#444; -fx-font-size:10px;");
            labels.add(l);
        }
        Platform.runLater(() -> agentBox.getChildren().setAll(labels));
    }

    private void loadUpdates() {
        List<UpdateRow> rows = new ArrayList<>();
        int pending = 0;
        String errMsg = "";
        try (Connection con = open(TELE_DB)) {
            con.createStatement().execute(
                "CREATE TABLE IF NOT EXISTS proposed_updates (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, hash_id TEXT UNIQUE, " +
                "project TEXT, agent TEXT, machine_id TEXT, summary TEXT, " +
                "code_block TEXT, diff_type TEXT DEFAULT 'improve', " +
                "status TEXT DEFAULT 'pending', comment TEXT DEFAULT '', " +
                "score REAL DEFAULT 0.0, created_at TEXT)");

            // Count pending
            try (ResultSet cr = con.createStatement().executeQuery(
                     "SELECT COUNT(*) FROM proposed_updates WHERE status='pending'")) {
                if (cr.next()) pending = cr.getInt(1);
            }

            // Build WHERE clause based on filter
            String filter = statusFilter.getValue();
            String where = (filter == null || "ALL".equals(filter))
                ? ""
                : "WHERE status='" + filter.replace("'", "") + "'";

            String sql = "SELECT id, hash_id, project, agent, summary, diff_type, " +
                "COALESCE(score,0.0), COALESCE(created_at,''), status " +
                "FROM proposed_updates " + where +
                " ORDER BY created_at DESC LIMIT 100";

            try (ResultSet rs = con.createStatement().executeQuery(sql)) {
                while (rs.next()) {
                    rows.add(new UpdateRow(
                        rs.getInt(1), rs.getString(2), rs.getString(3),
                        rs.getString(4), rs.getString(5), rs.getString(6),
                        rs.getDouble(7), rs.getString(8), rs.getString(9)));
                }
            }
        } catch (Exception e) {
            errMsg = "DB: " + e.getMessage();
            System.err.println("[PerformanceController] loadUpdates error: " + e.getMessage());
        }
        final List<UpdateRow> finalRows = rows;
        final int finalPending = pending;
        final String finalErr = errMsg;
        Platform.runLater(() -> {
            updatesTable.getItems().setAll(finalRows);
            pendingCount.setText("Pending: " + finalPending + " | Total: " + finalRows.size());
            errorLabel.setText(finalErr);
        });
    }

    private void loadRagResults() {
        List<RagRow> rows = new ArrayList<>();
        try (Connection con = open(TELE_DB)) {
            con.createStatement().execute(
                "CREATE TABLE IF NOT EXISTS rag_chain_log (" +
                "id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, query TEXT, " +
                "total_s REAL, stages TEXT, hits INTEGER DEFAULT 0)");
            try (ResultSet rs = con.createStatement().executeQuery(
                     "SELECT ts, query, total_s, COALESCE(stages,'{}') FROM rag_chain_log " +
                     "ORDER BY ts DESC LIMIT 10")) {
                while (rs.next()) {
                    rows.add(new RagRow(rs.getString(1), rs.getString(2),
                                        rs.getDouble(3), rs.getString(4)));
                }
            }
        } catch (Exception e) {
            rows.add(new RagRow("?", "rag_chain_log error: " + e.getMessage(), 0, ""));
        }
        final List<RagRow> fr = rows;
        Platform.runLater(() -> ragTable.getItems().setAll(fr));
    }

    private void loadGitStatus() {
        StringBuilder sb = new StringBuilder();
        try (Connection con = open(PROJ_DB)) {
            try (ResultSet rs = con.createStatement().executeQuery(
                     "SELECT name, git_branch, git_status FROM projects " +
                     "WHERE status='active' ORDER BY name LIMIT 20")) {
                while (rs.next()) {
                    String branch = rs.getString(2);
                    String status = rs.getString(3);
                    String snip = status != null
                        ? status.replace("\n", " ").substring(0, Math.min(40, status.length()))
                        : "";
                    sb.append(String.format("%-25s  [%s]  %s%n",
                        rs.getString(1), branch != null ? branch : "?", snip));
                }
            }
        } catch (Exception e) {
            sb.append("projects.db: ").append(e.getMessage());
        }
        final String txt = sb.toString();
        Platform.runLater(() -> gitArea.setText(txt.isEmpty() ? "No active projects" : txt));
    }

    private void loadPedagogy() {
        List<PedagogyRow> rows = new ArrayList<>();
        try (Connection con = open(TELE_DB)) {
            con.createStatement().execute(
                "CREATE TABLE IF NOT EXISTS pedagogy_log (" +
                "id INTEGER PRIMARY KEY, ts TEXT, category TEXT, " +
                "insight TEXT, metric REAL, severity TEXT DEFAULT 'info')");
            try (ResultSet rs = con.createStatement().executeQuery(
                     "SELECT ts, category, insight, COALESCE(severity,'info') FROM pedagogy_log " +
                     "ORDER BY id DESC LIMIT 15")) {
                while (rs.next()) {
                    rows.add(new PedagogyRow(rs.getString(1), rs.getString(2),
                                             rs.getString(3), rs.getString(4)));
                }
            }
        } catch (Exception e) {
            rows.add(new PedagogyRow("?", "system", "pedagogy_log: " + e.getMessage(), "error"));
        }
        final List<PedagogyRow> fr = rows;
        Platform.runLater(() -> pedagogyTable.getItems().setAll(fr));
    }

    private void loadHeroKernel() {
        List<HeroRow> rows = new ArrayList<>();
        try (Connection con = open(TELE_DB)) {
            con.createStatement().execute(
                "CREATE TABLE IF NOT EXISTS hero_training_log (" +
                "id INTEGER PRIMARY KEY, ts TEXT, step INTEGER, " +
                "loss REAL, lr REAL, sample TEXT, adapter TEXT)");
            try (ResultSet rs = con.createStatement().executeQuery(
                     "SELECT step, loss, ts FROM hero_training_log " +
                     "WHERE loss > 0 ORDER BY id DESC LIMIT 10")) {
                while (rs.next()) {
                    rows.add(new HeroRow(rs.getInt(1), rs.getDouble(2), rs.getString(3)));
                }
            }
        } catch (Exception e) {
            rows.add(new HeroRow(0, 0, "hero_training_log: " + e.getMessage()));
        }
        final List<HeroRow> fr = rows;
        Platform.runLater(() -> heroTable.getItems().setAll(fr));
    }

    // ── Central agent updates feed ──────────────────────────────────────────────

    private void buildFeedTable() {
        feedTable.setColumnResizePolicy(TableView.CONSTRAINED_RESIZE_POLICY_FLEX_LAST_COLUMN);
        feedTable.setStyle("-fx-background-color:#050a05; -fx-border-color:#00cfff; -fx-border-width:1;");
        feedTable.setPlaceholder(new Label(
            "Central feed — every agent posts here (proposals, tests, hypotheses, git, scrubs)"));

        TableColumn<FeedRow, String> okCol  = col("OK",   34, r -> r.confirmed() == 1 ? "ok" : "");
        TableColumn<FeedRow, String> tsCol  = col("TIME", 70,
            r -> r.ts() != null && r.ts().length() > 18 ? r.ts().substring(11, 19)
                 : (r.ts() != null ? r.ts() : ""));
        TableColumn<FeedRow, String> agCol  = col("AGENT", 130, r -> r.agent() != null ? r.agent() : "");
        TableColumn<FeedRow, String> kindCol = col("KIND", 95, r -> r.kind() != null ? r.kind() : "");
        TableColumn<FeedRow, String> msgCol = col("MESSAGE", 430, r -> r.message() != null ? r.message() : "");

        kindCol.setCellFactory(c -> new TableCell<>() {
            @Override protected void updateItem(String item, boolean empty) {
                super.updateItem(item, empty);
                if (empty || item == null) { setText(null); setStyle(""); return; }
                setText(item);
                setStyle(switch (item) {
                    case "test_pass", "implement", "git_confirm" -> "-fx-text-fill:#00ff88;";
                    case "test_fail", "hypothesis"               -> "-fx-text-fill:#ff8800;";
                    case "proposal", "review"                    -> "-fx-text-fill:#00cfff;";
                    case "git_push", "epoch"                     -> "-fx-text-fill:#ffaa00;";
                    case "scrub"                                 -> "-fx-text-fill:#888888;";
                    default                                      -> "-fx-text-fill:#aaaaaa;";
                });
            }
        });
        feedTable.getColumns().addAll(okCol, tsCol, agCol, kindCol, msgCol);
    }

    private void loadFeed() {
        List<FeedRow> rows = new ArrayList<>();
        try (Connection con = open(TELE_DB)) {
            con.createStatement().execute(
                "CREATE TABLE IF NOT EXISTS agent_updates (id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                "ts TEXT, agent TEXT, project TEXT, kind TEXT, message TEXT, detail TEXT, " +
                "status TEXT DEFAULT 'logged', ref TEXT, confirmed INTEGER DEFAULT 0)");
            try (ResultSet rs = con.createStatement().executeQuery(
                     "SELECT ts, agent, kind, message, COALESCE(status,''), COALESCE(confirmed,0) " +
                     "FROM agent_updates ORDER BY id DESC LIMIT 40")) {
                while (rs.next()) {
                    rows.add(new FeedRow(rs.getString(1), rs.getString(2), rs.getString(3),
                                         rs.getString(4), rs.getString(5), rs.getInt(6)));
                }
            }
        } catch (Exception e) {
            rows.add(new FeedRow("?", "system", "info", "agent_updates: " + e.getMessage(), "", 0));
        }
        final List<FeedRow> fr = rows;
        Platform.runLater(() -> feedTable.getItems().setAll(fr));
    }

    // ── Guardrails control bar ──────────────────────────────────────────────────

    private HBox buildGuardrailBar() {
        guardrailLabel.setFont(Font.font("Consolas", 10));
        guardrailLabel.setStyle("-fx-text-fill:#88cc99;");
        for (Button b : new Button[]{dryRunBtn, autonomyBtn, autoPushBtn, pauseBtn})
            b.setStyle("-fx-background-color:#0a110a; -fx-text-fill:#888; -fx-border-color:#333; " +
                       "-fx-border-radius:2; -fx-background-radius:2; -fx-padding:3 8; " +
                       "-fx-font-size:9px; -fx-cursor:hand;");
        dryRunBtn.setOnAction(e -> toggleSafety("dry_run"));
        autonomyBtn.setOnAction(e -> toggleSafety("auto_implement_enabled"));
        autoPushBtn.setOnAction(e -> toggleSafety("auto_push_enabled"));
        pauseBtn.setOnAction(e -> toggleSafety("paused"));

        HBox bar = new HBox(8, sectionHeader("GUARDRAILS"), guardrailLabel,
                            dryRunBtn, autonomyBtn, autoPushBtn, pauseBtn);
        bar.setAlignment(javafx.geometry.Pos.CENTER_LEFT);
        bar.setPadding(new Insets(5, 8, 5, 8));
        bar.setStyle("-fx-background-color:#08110a; -fx-border-color:#1a4a1a; -fx-border-width:1;");
        return bar;
    }

    private void toggleSafety(String key) {
        try (Connection con = open(TELE_DB)) {
            con.createStatement().execute(
                "CREATE TABLE IF NOT EXISTS autonomous_config " +
                "(key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)");
            String cur = "0";
            try (ResultSet rs = con.createStatement().executeQuery(
                     "SELECT value FROM autonomous_config WHERE key='" + key.replace("'", "") + "'")) {
                if (rs.next()) cur = rs.getString(1);
            }
            String next = is1(cur) ? "0" : "1";
            PreparedStatement ps = con.prepareStatement(
                "INSERT INTO autonomous_config(key,value,updated_at) VALUES(?,?,datetime('now')) " +
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at");
            ps.setString(1, key); ps.setString(2, next);
            ps.executeUpdate();
        } catch (Exception e) {
            System.err.println("[PerformanceController] toggleSafety error: " + e.getMessage());
        }
        loadGuardrails();
    }

    private void loadGuardrails() {
        java.util.Map<String, String> cfg = new java.util.HashMap<>();
        try (Connection con = open(TELE_DB)) {
            con.createStatement().execute(
                "CREATE TABLE IF NOT EXISTS autonomous_config " +
                "(key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)");
            try (ResultSet rs = con.createStatement().executeQuery(
                     "SELECT key, value FROM autonomous_config")) {
                while (rs.next()) cfg.put(rs.getString(1), rs.getString(2));
            }
        } catch (Exception e) { /* table may not exist yet */ }

        boolean dry    = is1(cfg.get("dry_run"));
        boolean impl   = is1(cfg.get("auto_implement_enabled"));
        boolean push   = is1(cfg.get("auto_push_enabled"));
        boolean paused = is1(cfg.get("paused"));
        String  conf   = cfg.getOrDefault("confidence_threshold", "0.8");
        String  mode   = paused ? "HALTED"
                       : dry    ? "propose-only (safe)"
                       : push   ? "LIVE + PUSH"
                       :          "LIVE (local commits)";
        Platform.runLater(() -> {
            setToggle(dryRunBtn,   "DRY-RUN",   dry,    "#00ff41");
            setToggle(autonomyBtn, "AUTONOMY",  impl,   "#00cfff");
            setToggle(autoPushBtn, "AUTO-PUSH", push,   "#ffaa00");
            setToggle(pauseBtn,    "PAUSE",     paused, "#ff4444");
            guardrailLabel.setText("mode: " + mode + "  |  conf>=" + conf);
        });
    }

    private boolean is1(String v) {
        return v != null && (v.equals("1") || v.equalsIgnoreCase("true") || v.equalsIgnoreCase("on"));
    }

    private void setToggle(Button b, String label, boolean on, String onColor) {
        b.setText(label + ": " + (on ? "ON" : "OFF"));
        String fg = on ? onColor : "#888888";
        String bg = on ? "#0a1a0a" : "#0a0a0a";
        b.setStyle("-fx-background-color:" + bg + "; -fx-text-fill:" + fg + "; -fx-border-color:" + fg + "; " +
                   "-fx-border-radius:2; -fx-background-radius:2; -fx-padding:3 8; " +
                   "-fx-font-size:9px; -fx-cursor:hand;");
    }

    // ── Actions ───────────────────────────────────────────────────────────────

    private void setUpdateStatus(int id, String status, String comment) {
        try (Connection con = open(TELE_DB)) {
            PreparedStatement ps = con.prepareStatement(
                "UPDATE proposed_updates SET status=?, comment=? WHERE id=?");
            ps.setString(1, status);
            ps.setString(2, comment != null ? comment : "");
            ps.setInt(3, id);
            ps.executeUpdate();
        } catch (Exception e) {
            System.err.println("[PerformanceController] setStatus error: " + e.getMessage());
        }
    }

    private void approveAllPending() {
        try (Connection con = open(TELE_DB)) {
            con.createStatement().executeUpdate(
                "UPDATE proposed_updates SET status='approved', " +
                "comment='bulk approved via Performance tab' WHERE status='pending'");
        } catch (Exception e) {
            System.err.println("[PerformanceController] approveAll error: " + e.getMessage());
        }
        loadAll();
    }

    // ── Auto-refresh ──────────────────────────────────────────────────────────

    private void startAutoRefresh() {
        autoRefresh = new Timeline(new KeyFrame(Duration.seconds(15), e -> loadAll()));
        autoRefresh.setCycleCount(Timeline.INDEFINITE);
        autoRefresh.play();
    }

    private void toggleAutoRefresh(Button btn) {
        if (autoRefresh.getStatus() == Timeline.Status.RUNNING) {
            autoRefresh.stop();
            btn.setText("AUTO: OFF");
        } else {
            autoRefresh.play();
            btn.setText("AUTO: ON");
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    private Label sectionHeader(String text) {
        Label l = new Label(text);
        l.setFont(Font.font("Consolas", FontWeight.BOLD, 10));
        l.setStyle("-fx-text-fill:#00cfff;");
        return l;
    }

    private Button btnAction(String text, String bg, String fg) {
        Button b = new Button(text);
        b.setStyle(String.format(
            "-fx-background-color:%s; -fx-text-fill:%s; -fx-border-color:%s; " +
            "-fx-border-radius:2; -fx-background-radius:2; -fx-padding:3 5; " +
            "-fx-font-size:8px; -fx-cursor:hand;", bg, fg, fg));
        return b;
    }

    private <T> TableColumn<T, String> col(String title, int width,
                                            java.util.function.Function<T, String> getter) {
        TableColumn<T, String> c = new TableColumn<>(title);
        c.setPrefWidth(width);
        c.setCellValueFactory(cell -> new SimpleStringProperty(
            getter.apply(cell.getValue())));
        return c;
    }

    public void shutdown() {
        if (autoRefresh != null) autoRefresh.stop();
    }
}
