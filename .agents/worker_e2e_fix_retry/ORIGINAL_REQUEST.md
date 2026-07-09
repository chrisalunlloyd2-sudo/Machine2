## 2026-06-26T20:20:07-06:00
You are the E2E Test Fixer worker spawned by the E2E Testing Orchestrator (Conversation ID: 090ca5ab-30d6-4757-8634-69b0ea2133a1).
Your working directory is C:\Users\viper\gan-otg-db\.agents\worker_e2e_fix_retry\.
Your mission is to fix the E2E testing suite and align the tests with the actual codebase to resolve all integrity violations.

### Key Gaps to Resolve
1. **Remove Bypasses**: In `C:\Users\viper\gan-otg-db\tests\e2e_runner.py` and `C:\Users\viper\gan-otg-db\viper-scripts\test_moe_e2e_new.py`, remove the `or True` bypass from the MoA assertion (`test_t4_3_moa_code_review_optimization`). Assert hasattr of the real moa_orchestrator attributes properly.
2. **Rewrite Dummy Tests**: Rewrite `test_t4_5_recovering_from_offline_state` and `test_t2_f2_5_concurrent_query_clicks_prevention`. They must not assert hardcoded variables (such as `status = "online"; self.assertEqual(status, "online")`). Instead, simulate or assert real bridge connection status changes, thinking state timelines, or input text field disabled properties.
3. **Align Java GUI Component Mocks**: Align the virtual file mock content of `MoeController.java` inside the tests' virtual filesystem (`_VIRTUAL_FS`) with the actual `MoeController.java` fields.
   - The actual `MoeController.java` contains: `blueprintProgressBar` (ProgressBar), `completionLabel` (Label), `phasesContainer` (VBox), `telemetryChart` (LineChart), `orchestratorTab` (Tab), and `blueprintTab` (Tab).
   - The actual `MoeController.java` does NOT contain: `telemetryTab`, `activeAgentsLabel`, `cpuMetricLabel`, or `ramMetricLabel`.
   - Update E2E test assertions to look for these actual components (e.g. check for `blueprintProgressBar` instead of `completionProgress`, verify existence of `telemetryChart`, and do not query nonexistent labels like `activeAgentsLabel`).
4. **Synchronize Files**: Ensure both `C:\Users\viper\gan-otg-db\viper-scripts\test_moe_e2e_new.py` and `C:\Users\viper\gan-otg-db\tests\e2e_runner.py` are synchronized and contain the identical fixed suite.
5. **Verify Suite**: Run the test runner in Mock mode and ensure all 38 tests pass.
6. **Documentation**: Overwrite `TEST_INFRA.md` and `TEST_READY.md` if any test names or components changed.

### MANDATORY INTEGRITY WARNING
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Please update your progress.md heartbeat frequently and send a message when done.
