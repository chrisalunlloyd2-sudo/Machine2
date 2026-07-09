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
| 1 | Test Design & Infra | Define E2E testing layout, test cases, and create `TEST_INFRA.md` at project root | None | DONE |
| 2 | Tier 1 Implementation | Implement Feature Coverage tests (>=5 cases for Feature 1, Feature 2, Feature 3; total >=15 cases) | M1 | DONE |
| 3 | Tier 2 Implementation | Implement Boundary & Corner tests (>=5 cases for Feature 1, Feature 2, Feature 3; total >=15 cases) | M2 | DONE |
| 4 | Tier 3 & 4 Implementation | Implement Cross-Feature tests (>=3 cases) and Real-World Scenarios (>=5 cases) | M3 | DONE |
| 5 | Integrity Audit & TEST_READY | Verify tests run, run Forensic Auditor, and write `TEST_READY.md` | M4 | IN_PROGRESS |

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
