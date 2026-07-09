# Scope: E2E Testing Track for Moe Desktop Swarm Orchestrator

## Architecture
- The E2E tests operate as an opaque-box test suite.
- They invoke the `desktop_moe_orchestrator.py` CLI via `subprocess` or programmatic API.
- They inspect the `MoeGUI` Java codebase and simulate/mock the JSON communication stream over stdin/stdout.
- They verify Talon paths redirection and hook logs behavior on the filesystem (e.g. `C:\Users\viper\.kai\moe_heartbeat.txt`).
- No internal module dependencies. Only CLI entry points, stdout, filesystem logs, and JSON interface format.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Test Design & Plan | Design 38 test cases across 4 tiers covering Feature 1, Feature 2, and Feature 3 | None | DONE |
| 2 | Test Suite Implementation | Implement the 38 test cases in a python script `tests/test_moe_e2e_new.py` supporting both 'mock' and 'live' modes | M1 | IN_PROGRESS |
| 3 | Verification & Run | Run tests in mock mode, ensure all 38 pass, run Forensic Auditor, and write TEST_INFRA.md / TEST_READY.md | M2 | PLANNED |

## Interface Contracts
### `desktop_moe_orchestrator.py` ↔ Test Runner
- CLI Invocation: `python desktop_moe_orchestrator.py "<query>"`
- JSON output interface: JSON stream of status update events containing `active_agent`, `status`, `completion_percentage`, `cpu_pct`, `ram_pct`, `log_line`, `answer`.

### `MoeGUI` ↔ `desktop_moe_orchestrator.py`
- JSON stream over stdin/stdout.
- Stdin sends queries: `{"query": "...", "project": "..."}`.
- Stdout returns agent updates and final answer.

### Talon scripts ↔ `C:\Users\viper\.kai\moe_heartbeat.txt`
- Appends timestamped log line to `C:\Users\viper\.kai\moe_heartbeat.txt` whenever Talon scripts are executed/activated.
