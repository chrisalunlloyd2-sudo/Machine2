# Scope: QA Verification

## Architecture
- MoeGUI: JavaFX application built with Maven.
- Moe Swarm Orchestrator: Python E2E test suite (tests/e2e_runner.py).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | MoeGUI Compile | Compile and package MoeGUI using mvn clean package | None | PLANNED |
| 2 | E2E Execution | Run the Python E2E test suite e2e_runner.py | None | PLANNED |
| 3 | Forensic Audit | Verify integrity and verify no hardcoding or dummy implementations | M1, M2 | PLANNED |
