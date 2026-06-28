import unittest
import sys
import os
import json
import sqlite3
import shutil

# Ensure path has the project root
sys.path.insert(0, r"C:\Users\viper\gan-otg-db")

import desktop_moe_orchestrator

class TestOrchestratorVerification(unittest.TestCase):

    def test_routing_show_cpu_load(self):
        """Verify routing of 'show CPU load' to systems_info_agent."""
        agent = desktop_moe_orchestrator.select_agent("show CPU load")
        self.assertEqual(agent, "systems_info_agent")
        
        ans, active_agent = desktop_moe_orchestrator.process_query("show CPU load")
        self.assertEqual(active_agent, "systems_info_agent")
        self.assertIn("ResourceGovernor", ans)

    def test_routing_commit_scripts(self):
        """Verify routing of 'commit modified scripts' to git_sync_agent."""
        agent = desktop_moe_orchestrator.select_agent("commit modified scripts")
        self.assertEqual(agent, "git_sync_agent")
        
        ans, active_agent = desktop_moe_orchestrator.process_query("commit modified scripts")
        self.assertEqual(active_agent, "git_sync_agent")
        self.assertIn("GitHubAgent", ans)

    def test_routing_modify_schema_compliant(self):
        """Verify routing of 'modify projects schema' to schema_migration_agent and safe execution."""
        agent = desktop_moe_orchestrator.select_agent("modify projects schema")
        self.assertEqual(agent, "schema_migration_agent")
        
        # Test clean compliant execution
        ans, active_agent = desktop_moe_orchestrator.process_query("modify projects schema")
        self.assertEqual(active_agent, "schema_migration_agent")
        self.assertIn("SOP-000 Compliance: PASSED", ans)
        
        # Verify that backup was created (if target projects.db exists)
        backup_dir = r"C:\Viper\backups\databases"
        if os.path.exists(backup_dir):
            files = os.listdir(backup_dir)
            backups = [f for f in files if f.startswith("projects_backup_") and f.endswith(".db")]
            self.assertTrue(len(backups) > 0, "No projects database backup files found in backup directory.")

    def test_routing_modify_schema_non_compliant(self):
        """Verify that destructive SQL operations are blocked by schema_migration_agent."""
        # Test DROP command
        ans, _ = desktop_moe_orchestrator.process_query("DROP TABLE projects;")
        self.assertIn("violates SOP-000", ans)
        self.assertIn("DROP", ans)
        
        # Test DELETE command
        ans, _ = desktop_moe_orchestrator.process_query("DELETE FROM projects WHERE id=1;")
        self.assertIn("violates SOP-000", ans)
        self.assertIn("DELETE", ans)
        
        # Test TRUNCATE command
        ans, _ = desktop_moe_orchestrator.process_query("TRUNCATE TABLE projects;")
        self.assertIn("violates SOP-000", ans)
        self.assertIn("TRUNCATE", ans)

    def test_database_query_agent_read_only(self):
        """Verify database_query_agent blocks write commands and acts read-only."""
        # Valid select should pass keyword check (even if DB error, it shouldn't say write blocked)
        ans = desktop_moe_orchestrator.database_query_agent("SELECT * FROM projects;")
        self.assertNotIn("blocked", ans.lower())
        
        # Write operations should be blocked
        ans = desktop_moe_orchestrator.database_query_agent("INSERT INTO projects (name) VALUES ('bad');")
        self.assertIn("blocked", ans)
        self.assertIn("database_query_agent is read-only", ans)

    def test_policy_enforcement_agent(self):
        """Verify policy_enforcement_agent checks all SOPs and DePIN gating."""
        ans = desktop_moe_orchestrator.policy_enforcement_agent("test query")
        self.assertIn("SOP-000", ans)
        self.assertIn("SOP-001", ans)
        self.assertIn("SOP-002", ans)
        self.assertIn("SOP-003", ans)
        self.assertIn("DePIN Gating", ans)

    def test_telemetry_request_response(self):
        """Verify telemetry_request responses."""
        t_data = desktop_moe_orchestrator.get_telemetry_data()
        self.assertIn("cpu", t_data)
        self.assertIn("ram", t_data)
        self.assertIn("completion_percentage", t_data)
        self.assertIn("active_agents", t_data)

if __name__ == "__main__":
    unittest.main()
