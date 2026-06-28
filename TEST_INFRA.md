# Viper MoE Swarm Orchestrator E2E Test Infrastructure (TEST_INFRA.md)

This document describes the testing philosophy, hierarchy, execution format, and layout of the End-to-End (E2E) testing suite for the Moe Desktop Swarm Orchestrator.

## Testing Philosophy
The E2E testing suite is built with a **scientific, self-contained, and deterministic** philosophy:
1. **Zero Hardcoded Asserts**: Every test validates real state and behavior rather than hardcoding static mock outcomes.
2. **Dual Mode Flexibility**: The suite supports a decoupled execution strategy allowing full off-line simulations (Mock mode) and physical systems verification (Live mode).
3. **Four-Tier Hierarchy**: Tests are structured to test components individually, at boundaries, when combined, and under real developer operations.

## Test Hierarchy
The suite implements exactly **38 tests** structured in the following 4 tiers:

### Tier 1: Feature Coverage (15 tests total, 5 per feature)
- **Feature 1: 11-Agent Desktop MoE Router**:
  - `test_moe_router_query_cpu_load`: Verifies routing to the ResourceGovernor.
  - `test_moe_router_query_commit_scripts`: Verifies routing to the GitHubAgent.
  - `test_moe_router_query_modify_schema`: Verifies routing to the ProjectAgent.
  - `test_moe_router_routing_mode_ask_kai`: Verifies routing behaves correctly in Ask_Kai mode.
  - `test_moe_router_local_model_fallback`: Verifies local fallback models are used.
- **Feature 2: JavaFX Swarm Dashboard**:
  - `test_javafx_gui_blueprint_tracker_exists`: Verifies Blueprint Tracker tab elements.
  - `test_javafx_gui_swarm_orchestrator_controls`: Verifies Swarm Orchestrator controls.
  - `test_javafx_gui_telemetry_visualizer_completion`: Verifies task progress metrics.
  - `test_javafx_gui_telemetry_visualizer_agent_status`: Verifies active agents labels.
  - `test_javafx_gui_telemetry_visualizer_resource_metrics`: Verifies CPU/RAM metric logs.
- **Feature 3: Talon Voice Control Integration**:
  - `test_talon_retarget_chris_to_viper`: Checks that no references to "chris" exist in files.
  - `test_talon_map_commands_to_moe`: Verifies voice mappings exist in talon file.
  - `test_talon_heartbeat_log_hook`: Verifies file writes/reads to `C:\Users\viper\.kai\moe_heartbeat.txt`.
  - `test_talon_loop_tick_execution`: Verifies single tick heartbeat extraction.
  - `test_talon_loop_start_stop_job`: Verifies cron loop setup and cancellation.

### Tier 2: Boundary & Corner Cases (15 tests total, 5 per feature)
- **Feature 1: MoE Router Boundaries**:
  - `test_moe_router_empty_query`: Handles empty query input gracefully.
  - `test_moe_router_extremely_long_query`: Verifies length boundaries and truncation.
  - `test_moe_router_unknown_routing_target`: Handles queries that do not match active agents.
  - `test_moe_router_database_failure`: Verifies error propagation when sqlite connection fails.
  - `test_moe_router_invalid_routing_mode`: Handles invalid mode values.
- **Feature 2: JavaFX Dashboard Boundaries**:
  - `test_javafx_gui_empty_projects_database`: Handles 0 projects in SQLite database.
  - `test_javafx_gui_telemetry_completion_overflow`: Clamps completion metric to range [0.0, 1.0].
  - `test_javafx_gui_telemetry_active_agents_zero`: Handles zero or negative active agent counts.
  - `test_javafx_gui_telemetry_invalid_cpu_ram_metrics`: Handles non-numeric metrics cleanly.
  - `test_javafx_gui_shutdown_lifecycle`: Verifies controller cleanup timelines.
- **Feature 3: Talon Boundaries**:
  - `test_talon_heartbeat_missing_file`: Handles missing heartbeat file gracefully.
  - `test_talon_heartbeat_corrupt_unicode`: Replaces invalid UTF-8 encoding.
  - `test_talon_loop_tick_command_failure`: Continues loop tick logging on process timeouts.
  - `test_talon_missing_scripts_paths`: Propagates missing script alerts instead of crashes.
  - `test_talon_loop_job_concurrency`: Cancels existing jobs prior to re-registering interval.

### Tier 3: Cross-Feature Combinations (3 tests total)
- `test_cross_talon_voice_triggers_moe_route`: Maps Talon voice triggers directly to MoE router queries.
- `test_cross_talon_loop_updates_javafx_telemetry`: Talon loop execution generates records tracked by JavaFX dashboard.
- `test_cross_moe_schema_modification_triggers_gui_refresh`: MoE router schema execution modifies database snapshot counts.

### Tier 4: Real-world Application Scenarios (5 tests total)
- `test_scenario_swarm_deployment_pipeline`: Simulates full agent startup pipeline and completion board visualization.
- `test_scenario_voice_db_migration`: Verifies voice-triggered database migration updates the projects schema.
- `test_scenario_telemetry_alert_and_failover`: Simulates high CPU spike triggering dashboard alerts and routing failover.
- `test_scenario_heartbeat_logger_loop_with_git_commit`: Verifies background loops detecting modifications, committing them via git, and returning status to clean.
- `test_scenario_concurrent_multi_voice_commands`: Verifies sequential execution of multiple concurrent voice commands.

## Execution Modes
Execution is controlled using the `VIPER_E2E_MODE` environment variable:
- **Mock Mode (`VIPER_E2E_MODE=mock` or default)**:
  - SQLite database connections are routed to `:memory:` instances seeded with table structures and data.
  - Subprocess executions of `ask_kai.py`, `kai_reply.py`, `git`, and `gh` are intercepted to return realistic output.
  - File operations are intercepted using an in-memory virtual filesystem representing Talon scripts and Java controllers.
- **Live Mode (`VIPER_E2E_MODE=live`)**:
  - Connects to physical databases located in `C:\Viper\databases\`.
  - Runs real subprocess commands.
  - Checks live Talon files in `C:\Users\viper\gan-otg-db\viper-scripts\talon\` and Java controllers in `C:\Users\viper\gan-otg-db\MoeGUI\src\main\java\com\viper\moe\`.
  - Performs actual writes/reads of the heartbeat file at `C:\Users\viper\.kai\moe_heartbeat.txt`.

## Layout
- Test Suite Path: `C:\Users\viper\gan-otg-db\viper-scripts\test_moe_e2e_new.py`
- Test Framework: Python standard `unittest` library.
