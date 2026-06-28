# Moe Swarm Orchestrator E2E Test Readiness Guide (TEST_READY.md)

This document provides execution instructions, environment requirements, test case checklists, and verification commands for the E2E test suite.

## Quick Execution Command

By default, the test suite runs in **Mock Mode**, requiring no external services or physical databases to be active.

### Run in Mock Mode (Default)
In Command Prompt / PowerShell:
```cmd
python C:\Users\viper\gan-otg-db\viper-scripts\test_moe_e2e_new.py
```

### Run in Live Mode
To execute against the actual running desktop and database environment, set the `VIPER_E2E_MODE` environment variable to `live`:

**PowerShell:**
```powershell
$env:VIPER_E2E_MODE="live"
python C:\Users\viper\gan-otg-db\viper-scripts\test_moe_e2e_new.py
```

**Command Prompt:**
```cmd
set VIPER_E2E_MODE=live
python C:\Users\viper\gan-otg-db\viper-scripts\test_moe_e2e_new.py
```

---

## Test Cases Checklist (38 Total)

### Tier 1: Feature Coverage (15/15)
- [x] `test_moe_router_query_cpu_load`
- [x] `test_moe_router_query_commit_scripts`
- [x] `test_moe_router_query_modify_schema`
- [x] `test_moe_router_routing_mode_ask_kai`
- [x] `test_moe_router_local_model_fallback`
- [x] `test_javafx_gui_blueprint_tracker_exists`
- [x] `test_javafx_gui_swarm_orchestrator_controls`
- [x] `test_javafx_gui_telemetry_visualizer_completion`
- [x] `test_javafx_gui_telemetry_visualizer_agent_status`
- [x] `test_javafx_gui_telemetry_visualizer_resource_metrics`
- [x] `test_talon_retarget_chris_to_viper`
- [x] `test_talon_map_commands_to_moe`
- [x] `test_talon_heartbeat_log_hook`
- [x] `test_talon_loop_tick_execution`
- [x] `test_talon_loop_start_stop_job`

### Tier 2: Boundary & Corner Cases (15/15)
- [x] `test_moe_router_empty_query`
- [x] `test_moe_router_extremely_long_query`
- [x] `test_moe_router_unknown_routing_target`
- [x] `test_moe_router_database_failure`
- [x] `test_moe_router_invalid_routing_mode`
- [x] `test_javafx_gui_empty_projects_database`
- [x] `test_javafx_gui_telemetry_completion_overflow`
- [x] `test_javafx_gui_telemetry_active_agents_zero`
- [x] `test_javafx_gui_telemetry_invalid_cpu_ram_metrics`
- [x] `test_javafx_gui_shutdown_lifecycle`
- [x] `test_talon_heartbeat_missing_file`
- [x] `test_talon_heartbeat_corrupt_unicode`
- [x] `test_talon_loop_tick_command_failure`
- [x] `test_talon_missing_scripts_paths`
- [x] `test_talon_loop_job_concurrency`

### Tier 3: Cross-Feature Combinations (3/3)
- [x] `test_cross_talon_voice_triggers_moe_route`
- [x] `test_cross_talon_loop_updates_javafx_telemetry`
- [x] `test_cross_moe_schema_modification_triggers_gui_refresh`

### Tier 4: Real-world Application Scenarios (5/5)
- [x] `test_scenario_swarm_deployment_pipeline`
- [x] `test_scenario_voice_db_migration`
- [x] `test_scenario_telemetry_alert_and_failover`
- [x] `test_scenario_heartbeat_logger_loop_with_git_commit`
- [x] `test_scenario_concurrent_multi_voice_commands`

---

## Live Mode Pre-flight Checklist
Before running the suite in **Live Mode**, ensure the following configurations are complete:
1. **SQLite Database Pathing**: Verify the databases folder `C:\Viper\databases\` exists and contains the subdirectories `projects\`, `code\`, `research\`, `telemetry\`, `tools\`, and `graph\`.
2. **No references to "chris"**: Verify that git search finds 0 occurrences of "chris" inside `C:\Users\viper\gan-otg-db\viper-scripts\talon\`.
3. **Java Dashboard Controller tabs**: Verify Java source files contain the Blueprint Tracker, Swarm Orchestrator, and Telemetry Visualizer classes.
4. **Heartbeat directory access**: Verify that the folder `C:\Users\viper\.kai\` exists and has write access permissions for the heartbeat logger.
