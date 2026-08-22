package com.viper.moe;

import java.sql.*;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Reads live row counts and project data from Viper SQLite databases. */
public class DbStatus {

    static {
        try { Class.forName("org.sqlite.JDBC"); } catch (ClassNotFoundException ignored) {}
    }

    static final String PROJ_DB = "C:\\Viper\\databases\\projects\\projects.db";

    private static final Map<String, String[]> DBS = new LinkedHashMap<>() {{
        put("projects", new String[]{PROJ_DB, "projects", "tasks"});
        put("code",     new String[]{"C:\\Viper\\databases\\code\\code.db",         "code_artifacts"});
        put("research", new String[]{"C:\\Viper\\databases\\research\\research.db",  "research_entries"});
        put("telemetry",new String[]{"C:\\Viper\\databases\\telemetry\\telemetry.db","agent_events"});
        put("tools",    new String[]{"C:\\Viper\\databases\\tools\\tools.db",        "tools"});
        put("graph",    new String[]{"C:\\Viper\\databases\\graph\\graph.db",        "entities"});
    }};

    // ── DB snapshot (row counts) ───────────────────────────────────────────────
    public static Map<String, Map<String, Long>> snapshot() {
        Map<String, Map<String, Long>> result = new LinkedHashMap<>();
        for (var entry : DBS.entrySet()) {
            String   name   = entry.getKey();
            String[] info   = entry.getValue();
            String   path   = info[0];
            Map<String, Long> counts = new LinkedHashMap<>();
            try (Connection con = DriverManager.getConnection("jdbc:sqlite:" + path)) {
                for (int i = 1; i < info.length; i++) {
                    String table = info[i];
                    try (Statement st = con.createStatement();
                         ResultSet rs = st.executeQuery("SELECT COUNT(*) FROM " + table)) {
                        counts.put(table, rs.next() ? rs.getLong(1) : 0L);
                    } catch (Exception e) {
                        counts.put(table, -1L);
                    }
                }
            } catch (Exception e) {
                counts.put("error", -1L);
            }
            result.put(name, counts);
        }
        return result;
    }

    // ── Project list with pending task counts ──────────────────────────────────
    public record ProjectItem(String name, int pendingTasks) {
        @Override
        public String toString() {
            return pendingTasks > 0
                ? name + "  [" + pendingTasks + "]"
                : name;
        }
    }

    public static List<ProjectItem> projectList() {
        List<ProjectItem> result = new ArrayList<>();
        String sql =
            "SELECT p.name, COUNT(t.id) AS cnt " +
            "FROM projects p " +
            "LEFT JOIN tasks t ON t.project_id = p.id AND t.status = 'pending' " +
            "WHERE p.status = 'active' " +
            "GROUP BY p.id " +
            "ORDER BY cnt DESC, p.name ASC " +
            "LIMIT 30";
        try (Connection con = DriverManager.getConnection("jdbc:sqlite:" + PROJ_DB);
             Statement  st  = con.createStatement();
             ResultSet  rs  = st.executeQuery(sql)) {
            while (rs.next()) {
                result.add(new ProjectItem(rs.getString(1), rs.getInt(2)));
            }
        } catch (Exception e) {
            result.add(new ProjectItem("DB error: " + e.getMessage(), 0));
        }
        return result;
    }
}
