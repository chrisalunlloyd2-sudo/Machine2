package com.viper.moe;

import javafx.application.Platform;
import javafx.geometry.Insets;
import javafx.geometry.Orientation;
import javafx.scene.Parent;
import javafx.scene.control.*;
import javafx.scene.layout.*;
import javafx.scene.text.Font;
import javafx.scene.text.FontWeight;

import java.sql.*;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * Viper Notes — OneNote-style notebook panel.
 * Left: notebook list + toolbar. Centre: note list for selected notebook.
 * Right: full content viewer.
 * DB: NOTES_DB (separate SQLite, auto-created).
 * ingestConversation(title, content) — called by MoeController ship-to-notes button.
 */
public class ViperNotesController {

    static final String NOTES_DB = "C:\\Viper\\databases\\sophia\\notes.db";

    private final ListView<String>      notebookList  = new ListView<>();
    private final TableView<NoteItem>   noteTable     = new TableView<>();
    private final TextArea              viewer        = new TextArea();
    private final TextField             searchField   = new TextField();
    private final Label                 statusLabel   = new Label("Ready");
    private int currentNotebookId = -1;

    record NoteItem(int id, int notebookId, String title, String createdAt) {}

    public Parent buildLayout() {
        ensureSchema();

        // ── LEFT: notebook list ───────────────────────────────────────────
        Label nbHeader = sectionHeader("NOTEBOOKS");
        notebookList.setPrefWidth(170);
        notebookList.getStyleClass().add("sidebar-list");

        Button newNbBtn = toolBtn("+ NB", "#003300", "#00ff41");
        newNbBtn.setMaxWidth(Double.MAX_VALUE);
        newNbBtn.setOnAction(e -> newNotebook());

        VBox leftPane = new VBox(6, nbHeader, notebookList, newNbBtn);
        leftPane.setPadding(new Insets(8));
        leftPane.setPrefWidth(180);
        leftPane.getStyleClass().add("sidebar");

        notebookList.getSelectionModel().selectedItemProperty().addListener(
            (obs, old, nb) -> {
                if (nb != null) loadNotes(getNotebookId(nb));
            });

        // ── CENTRE: note list ─────────────────────────────────────────────
        TableColumn<NoteItem, String> titleCol = new TableColumn<>("TITLE");
        titleCol.setCellValueFactory(c ->
            new javafx.beans.property.SimpleStringProperty(c.getValue().title()));
        titleCol.setPrefWidth(220);

        TableColumn<NoteItem, String> tsCol = new TableColumn<>("WHEN");
        tsCol.setCellValueFactory(c -> {
            String ts = c.getValue().createdAt();
            return new javafx.beans.property.SimpleStringProperty(
                ts != null && ts.length() > 16 ? ts.substring(0, 16) : (ts != null ? ts : ""));
        });
        tsCol.setPrefWidth(90);

        noteTable.getColumns().addAll(titleCol, tsCol);
        noteTable.setColumnResizePolicy(TableView.CONSTRAINED_RESIZE_POLICY_FLEX_LAST_COLUMN);
        noteTable.setStyle("-fx-background-color:#050a05; -fx-border-color:#00ff41; -fx-border-width:1;");
        noteTable.setPlaceholder(new Label("Select a notebook or create a new note"));

        noteTable.getSelectionModel().selectedItemProperty().addListener(
            (obs, old, item) -> { if (item != null) loadNoteContent(item.id()); });

        Button newNoteBtn  = toolBtn("+ NOTE",  "#001a33", "#00cfff");
        Button delBtn      = toolBtn("DELETE",  "#330000", "#ff4444");
        Button searchBtn   = toolBtn("SEARCH",  "#1a1a00", "#ffff44");
        searchField.setPromptText("Search notes...");
        searchField.setStyle("-fx-background-color:#0a0a0a; -fx-text-fill:#ccffcc; " +
            "-fx-border-color:#333; -fx-font-size:10px;");
        HBox.setHgrow(searchField, Priority.ALWAYS);

        newNoteBtn.setOnAction(e -> newNote());
        delBtn.setOnAction(e -> deleteSelected());
        searchBtn.setOnAction(e -> searchNotes());
        searchField.setOnAction(e -> searchNotes());

        HBox noteToolBar = new HBox(4, newNoteBtn, delBtn, searchField, searchBtn);
        noteToolBar.setPadding(new Insets(4));
        VBox.setVgrow(noteTable, Priority.ALWAYS);
        VBox centrePane = new VBox(4, noteToolBar, noteTable);
        centrePane.setPadding(new Insets(4));
        centrePane.setPrefWidth(330);

        // ── RIGHT: content viewer ─────────────────────────────────────────
        viewer.setEditable(false);
        viewer.setWrapText(true);
        viewer.setStyle("-fx-control-inner-background:#050a05; -fx-text-fill:#c8ffd8; " +
            "-fx-font-family:Consolas; -fx-font-size:12;");
        VBox.setVgrow(viewer, Priority.ALWAYS);

        statusLabel.setStyle("-fx-text-fill:#555; -fx-font-size:10;");
        VBox rightPane = new VBox(4, sectionHeader("NOTE CONTENT"), viewer, statusLabel);
        rightPane.setPadding(new Insets(8));

        SplitPane split = new SplitPane(leftPane, centrePane, rightPane);
        split.setOrientation(Orientation.HORIZONTAL);
        split.setDividerPositions(0.15, 0.42);
        split.setStyle("-fx-background-color:#050a05;");

        loadNotebooks();
        return split;
    }

    private Connection open() throws SQLException {
        try { Class.forName("org.sqlite.JDBC"); } catch (ClassNotFoundException ignored) {}
        return DriverManager.getConnection(
            "jdbc:sqlite:" + NOTES_DB + "?busy_timeout=5000&journal_mode=WAL");
    }

    private void ensureSchema() {
        Thread.ofVirtual().start(() -> {
            try (Connection con = open()) {
                con.createStatement().executeUpdate(
                    "CREATE TABLE IF NOT EXISTS notebooks (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                    "name TEXT UNIQUE NOT NULL, " +
                    "created_at TEXT DEFAULT (datetime('now')))");
                con.createStatement().executeUpdate(
                    "CREATE TABLE IF NOT EXISTS notes (" +
                    "id INTEGER PRIMARY KEY AUTOINCREMENT, " +
                    "notebook_id INTEGER REFERENCES notebooks(id) ON DELETE CASCADE, " +
                    "title TEXT NOT NULL DEFAULT 'Untitled', " +
                    "content TEXT DEFAULT '', " +
                    "tags TEXT DEFAULT '', " +
                    "created_at TEXT DEFAULT (datetime('now')), " +
                    "updated_at TEXT DEFAULT (datetime('now')))");
                con.createStatement().executeUpdate(
                    "INSERT OR IGNORE INTO notebooks (name) VALUES ('General'), ('AEGIS'), ('Chats')");
            } catch (Exception e) {
                Platform.runLater(() -> statusLabel.setText("DB error: " + e.getMessage()));
            }
        });
    }

    private void loadNotebooks() {
        Thread.ofVirtual().start(() -> {
            List<String> names = new ArrayList<>();
            try (Connection con = open()) {
                var rs = con.createStatement().executeQuery(
                    "SELECT name FROM notebooks ORDER BY name");
                while (rs.next()) names.add(rs.getString(1));
            } catch (Exception e) {
                names.add("Error: " + e.getMessage());
            }
            Platform.runLater(() -> {
                notebookList.getItems().setAll(names);
                if (!names.isEmpty() && notebookList.getSelectionModel().isEmpty())
                    notebookList.getSelectionModel().select(0);
            });
        });
    }

    private int getNotebookId(String name) {
        try (Connection con = open()) {
            var rs = con.createStatement().executeQuery(
                "SELECT id FROM notebooks WHERE name='" + name.replace("'", "''") + "'");
            if (rs.next()) { currentNotebookId = rs.getInt(1); return currentNotebookId; }
        } catch (Exception ignored) {}
        return -1;
    }

    private void loadNotes(int notebookId) {
        currentNotebookId = notebookId;
        Thread.ofVirtual().start(() -> {
            List<NoteItem> rows = new ArrayList<>();
            try (Connection con = open()) {
                var rs = con.createStatement().executeQuery(
                    "SELECT id, notebook_id, title, created_at FROM notes " +
                    "WHERE notebook_id=" + notebookId + " ORDER BY id DESC LIMIT 200");
                while (rs.next())
                    rows.add(new NoteItem(rs.getInt(1), rs.getInt(2),
                                          rs.getString(3), rs.getString(4)));
            } catch (Exception e) {
                rows.add(new NoteItem(-1, -1, "Error: " + e.getMessage(), ""));
            }
            Platform.runLater(() -> {
                noteTable.getItems().setAll(rows);
                statusLabel.setText(rows.size() + " notes");
            });
        });
    }

    private void loadNoteContent(int noteId) {
        Thread.ofVirtual().start(() -> {
            try (Connection con = open()) {
                var rs = con.createStatement().executeQuery(
                    "SELECT content FROM notes WHERE id=" + noteId);
                String content = rs.next() ? rs.getString(1) : "";
                Platform.runLater(() -> viewer.setText(content != null ? content : ""));
            } catch (Exception e) {
                Platform.runLater(() -> viewer.setText("Error: " + e.getMessage()));
            }
        });
    }

    private void searchNotes() {
        String q = searchField.getText().trim();
        if (q.isBlank()) { if (currentNotebookId >= 0) loadNotes(currentNotebookId); return; }
        Thread.ofVirtual().start(() -> {
            List<NoteItem> rows = new ArrayList<>();
            try (Connection con = open()) {
                String like = "%" + q.replace("'", "''") + "%";
                var rs = con.createStatement().executeQuery(
                    "SELECT id, notebook_id, title, created_at FROM notes " +
                    "WHERE title LIKE '" + like + "' OR content LIKE '" + like + "' " +
                    "ORDER BY id DESC LIMIT 100");
                while (rs.next())
                    rows.add(new NoteItem(rs.getInt(1), rs.getInt(2),
                                          rs.getString(3), rs.getString(4)));
            } catch (Exception e) {
                rows.add(new NoteItem(-1, -1, "Search error: " + e.getMessage(), ""));
            }
            Platform.runLater(() -> {
                noteTable.getItems().setAll(rows);
                statusLabel.setText("Search: " + rows.size() + " results for \"" + q + "\"");
            });
        });
    }

    private void newNotebook() {
        TextInputDialog dlg = new TextInputDialog("New Notebook");
        dlg.setTitle("New Notebook"); dlg.setHeaderText("Notebook name:");
        dlg.getDialogPane().setStyle("-fx-background-color:#050a05;");
        Optional<String> r = dlg.showAndWait();
        r.filter(s -> !s.isBlank()).ifPresent(name -> {
            Thread.ofVirtual().start(() -> {
                try (Connection con = open()) {
                    con.createStatement().executeUpdate(
                        "INSERT OR IGNORE INTO notebooks (name) VALUES ('" +
                        name.replace("'", "''") + "')");
                } catch (Exception e) {
                    Platform.runLater(() -> statusLabel.setText("Error: " + e.getMessage()));
                }
                Platform.runLater(this::loadNotebooks);
            });
        });
    }

    private void newNote() {
        if (currentNotebookId < 0) { statusLabel.setText("Select a notebook first"); return; }
        TextInputDialog dlg = new TextInputDialog("New Note");
        dlg.setTitle("New Note"); dlg.setHeaderText("Note title:");
        dlg.getDialogPane().setStyle("-fx-background-color:#050a05;");
        Optional<String> r = dlg.showAndWait();
        r.filter(s -> !s.isBlank()).ifPresent(title -> {
            Thread.ofVirtual().start(() -> {
                try (Connection con = open()) {
                    con.createStatement().executeUpdate(
                        "INSERT INTO notes (notebook_id, title) VALUES (" +
                        currentNotebookId + ", '" + title.replace("'", "''") + "')");
                } catch (Exception e) {
                    Platform.runLater(() -> statusLabel.setText("Error: " + e.getMessage()));
                }
                Platform.runLater(() -> loadNotes(currentNotebookId));
            });
        });
    }

    private void deleteSelected() {
        NoteItem sel = noteTable.getSelectionModel().getSelectedItem();
        if (sel == null) return;
        Alert dlg = new Alert(Alert.AlertType.CONFIRMATION,
            "Delete \"" + sel.title() + "\"?", ButtonType.YES, ButtonType.NO);
        dlg.getDialogPane().setStyle("-fx-background-color:#050a05;");
        dlg.showAndWait().ifPresent(bt -> {
            if (bt == ButtonType.YES) {
                Thread.ofVirtual().start(() -> {
                    try (Connection con = open()) {
                        con.createStatement().executeUpdate(
                            "DELETE FROM notes WHERE id=" + sel.id());
                    } catch (Exception e) {
                        Platform.runLater(() -> statusLabel.setText("Error: " + e.getMessage()));
                    }
                    Platform.runLater(() -> {
                        viewer.clear();
                        loadNotes(currentNotebookId);
                    });
                });
            }
        });
    }

    /** Called by MoeController ship-to-notes button: saves a chat exchange as a note in "Chats". */
    public void ingestConversation(String title, String content) {
        Thread.ofVirtual().start(() -> {
            try (Connection con = open()) {
                con.createStatement().executeUpdate(
                    "INSERT OR IGNORE INTO notebooks (name) VALUES ('Chats')");
                var rs = con.createStatement().executeQuery(
                    "SELECT id FROM notebooks WHERE name='Chats'");
                if (!rs.next()) return;
                int nbId = rs.getInt(1);
                String safeTitle   = (title   != null ? title   : "Chat").replace("'", "''");
                String safeContent = (content != null ? content : "").replace("'", "''");
                con.createStatement().executeUpdate(
                    "INSERT INTO notes (notebook_id, title, content) VALUES (" +
                    nbId + ", '" + safeTitle + "', '" + safeContent + "')");
                Platform.runLater(() -> {
                    statusLabel.setText("Saved to Chats notebook");
                    if (currentNotebookId == nbId) loadNotes(nbId);
                });
            } catch (Exception e) {
                Platform.runLater(() -> statusLabel.setText("Ingest error: " + e.getMessage()));
            }
        });
    }

    public void shutdown() {}

    private Label sectionHeader(String text) {
        Label l = new Label(text);
        l.setFont(Font.font("Consolas", FontWeight.BOLD, 10));
        l.setStyle("-fx-text-fill:#00cfff;");
        return l;
    }

    private Button toolBtn(String text, String bg, String fg) {
        Button b = new Button(text);
        b.setStyle(String.format(
            "-fx-background-color:%s; -fx-text-fill:%s; -fx-border-color:%s; " +
            "-fx-border-radius:2; -fx-background-radius:2; -fx-padding:3 8; " +
            "-fx-font-size:9px; -fx-cursor:hand;", bg, fg, fg));
        return b;
    }
}
