package com.viper.moe;

import javafx.application.Application;
import javafx.application.Platform;
import javafx.scene.Scene;
import javafx.scene.control.Tab;
import javafx.scene.control.TabPane;
import javafx.stage.Stage;

import java.io.File;
import java.io.FileWriter;
import java.io.PrintWriter;
import java.time.Instant;

public class MoeApp extends Application {

    private static final String CRASH_LOG = "C:\\Viper\\logs\\moegui_crash.log";

    static void logCrash(String context, Throwable t) {
        try {
            new File("C:\\Viper\\logs").mkdirs();
            try (PrintWriter pw = new PrintWriter(new FileWriter(CRASH_LOG, true))) {
                pw.println("=== CRASH " + Instant.now() + " [" + context + "] ===");
                t.printStackTrace(pw);
            }
        } catch (Exception ignored) {}
        t.printStackTrace(System.err);
    }

    public static void main(String[] args) {
        Thread.setDefaultUncaughtExceptionHandler((thread, t) ->
            logCrash("thread=" + thread.getName(), t));
        launch(args);
    }

    @Override
    public void start(Stage stage) {
        MoeController         chat;
        PerformanceController perf;
        ViperNotesController  notes;
        try {
            chat  = new MoeController();
            perf  = new PerformanceController();
            notes = new ViperNotesController();
        } catch (Exception e) {
            logCrash("start-init", e);
            return;
        }

        try {
            Tab chatTab = new Tab("CHAT", chat.buildLayout());
            chatTab.setClosable(false);

            Tab notesTab = new Tab("VIPER NOTES", notes.buildLayout());
            notesTab.setClosable(false);

            Tab perfTab = new Tab("PERFORMANCE & UPDATES", perf.buildLayout());
            perfTab.setClosable(false);

            TabPane tabs = new TabPane(chatTab, notesTab, perfTab);
            tabs.getStyleClass().add("floating");

            Scene scene = new Scene(tabs, 1280, 820);
            java.net.URL css = getClass().getResource("/css/dark.css");
            if (css != null) scene.getStylesheets().add(css.toExternalForm());

            stage.setTitle("Moe  Viper Intelligence Center");
            stage.setScene(scene);
            stage.setOnCloseRequest(e -> { chat.shutdown(); notes.shutdown(); });
            stage.setAlwaysOnTop(true);
            stage.show();
            stage.toFront();
            stage.requestFocus();
            stage.setAlwaysOnTop(false);

            chat.startLiveUpdates();
            chat.setNotesController(notes);
        } catch (Exception e) {
            logCrash("start-build", e);
        }
    }
}
