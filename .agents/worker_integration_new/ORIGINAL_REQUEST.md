## 2026-06-26T20:21:01-06:00

You are the Worker (teamwork_preview_worker) for the integration and verification phase.
Your working directory is C:\Users\viper\gan-otg-db\.agents\worker_integration_new\.

Your tasks are:
1. Inspect and update `C:\Users\viper\gan-otg-db\MoeGUI\src\main\java\com\viper\moe\PythonBridge.java`:
   - Re-route MOE_SERVER path from `C:\\Viper\\projects\\ArchivalMoe\\desktop_moe_orchestrator.py` to `C:\\Users\\viper\\gan-otg-db\\desktop_moe_orchestrator.py`.
   - Re-route PYTHON path to use the system Python interpreter `C:\\Python314\\python.exe`.
2. Inspect and update `C:\Users\viper\gan-otg-db\viper-scripts\talon\viper\viper_moe.py`:
   - Change `ORCHESTRATOR` path to `C:\\Users\\viper\\gan-otg-db\\desktop_moe_orchestrator.py`.
   - Ensure the python runtime used is `C:\\Python314\\python.exe` or sys.executable as appropriate.
3. Clean up path references to `chris` across all files in `C:\Users\viper\gan-otg-db\viper-scripts\`:
   - Re-target all hardcoded `chris` paths (like `C:\Users\chris` or `C:/Users/chris` or `C:\\Users\\chris` or `C:\\\\Users\\\\chris`) to `C:\Users\viper` (or equivalent slashes/backslashes).
   - In particular, look at `moe_mcp_server.py`, `prefetch.py`, `heartbeat_responder.py`, `moe-report.py`, `viper_llm_server.py`, `wrappers.py`, and any other scripts in `viper-scripts/`.
4. Verify the E2E test suite by executing the tests in Mock Mode:
   - Run the command: `C:\Python314\python.exe C:\Users\viper\gan-otg-db\viper-scripts\test_moe_e2e_new.py`
   - Capture the output and verify that all 38/38 tests pass cleanly.
5. Write your findings, list of modified files, and the output of the test run to `C:\Users\viper\gan-otg-db\.agents\worker_integration_new\handoff.md`.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
