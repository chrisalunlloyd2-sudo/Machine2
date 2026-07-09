# Handoff Report: Milestone M2: R1 (desktop_moe_orchestrator.py) Implementation Strategy

This handoff report is prepared by Explorer 2 (teamwork_preview_explorer) for the implementer agent. It details observations, logic chain, caveats, conclusion, verification method, and remaining work.

---

## 1. Observation
The following key elements were directly observed in the codebase:
1.  **SOP-000 (Never Delete)**:
    *   Path: `C:\Users\viper\gan-otg-db\viper-scripts\SOP_NEVER_DELETE.md`
    *   Verbatim Rule: `"On the Viper host, NOTHING is ever deleted, overwritten destructively, or replaced. Only ADD, MERGE, and IMPROVE."`
    *   Path: `C:\Users\viper\gan-otg-db\viper-scripts\config\policies\SOP-000.md`
    *   Verbatim Rule: `"All scripts must keep original headers and structure. Never do destructive updates or truncates of existing files."`
2.  **SOP-001 (Resource Clamping)**:
    *   Path: `C:\Users\viper\gan-otg-db\viper-scripts\config\policies\SOP-001.md`
    *   Verbatim Rule: `"All background operations must use resource_governor and clamp processor math to 1 CPU core to keep the Xeon server responsive."`
3.  **SOP-002 (OTG Handshake Protocol)**:
    *   Path: `C:\Users\viper\gan-otg-db\viper-scripts\config\policies\SOP-002.md`
    *   Verbatim Rule: `"All inter-node transactions must write a handshake and verify coordinating keys in K:\ before reading/executing requests."`
4.  **SOP-003 (Viper GitHub OAuth Device Flow)**:
    *   Path: `C:\Users\viper\gan-otg-db\viper-scripts\github-auth-device.py`
    *   Verbatim Header: `"Viper GitHub OAuth Device Flow — SOP-003 implementation."`
5.  **Telemetry-based DePIN Gate**:
    *   Path: `C:\Users\viper\gan-otg-db\viper-scripts\depin_gate.py`
    *   Verbatim Method:
        ```python
        def gate(sender: str, receiver: str, content: str) -> dict:
            """The DePIN gate. Returns {allowed, pressure, chain_hash|reason}."""
        ```
6.  **Database Locations & Schemas**:
    *   `db-init.py` (lines 6, 62, 131, 164) and `db-init-tools-graph.py` (lines 8, 96) and `db-init-prompts.py` (line 9) connect to databases located in `C:\Viper\databases\`:
        *   `C:\Viper\databases\projects\projects.db`
        *   `C:\Viper\databases\code\code.db`
        *   `C:\Viper\databases\research\research.db`
        *   `C:\Viper\databases\telemetry\telemetry.db`
        *   `C:\Viper\databases\prompts\prompts.db`
        *   `C:\Viper\databases\tools\tools.db`
        *   `C:\Viper\databases\graph\graph.db`
        *   `C:\Viper\databases\agents\agents.db`
    *   `nmct_db_manager.py` (line 6) connects to database:
        *   `C:\Users\viper\gan-otg-db\nmct_code.db`

---

## 2. Logic Chain
1.  **SOP-000 Compliance**: Since SOP-000 strictly forbids any destructive modifications and deletions, the `schema_migration_agent` must run DDL/DML safely. Programmatic safety requires parsing SQL to reject queries containing `DROP`, `DELETE`, or `TRUNCATE`, and backing up target database files to `C:\Viper\backups\databases\` before execution.
2.  **Specialist Access**: To avoid scattered database connections, a dedicated `database_query_agent` should be created. It must restrict operations to read-only queries (using `SELECT` and `WITH` only, and establishing read-only URI mode: `mode=ro`) to eliminate the risk of accidental modification.
3.  **Governance Inspection**: Since SOP-001, 002, 003, and DePIN Gate leashing represent distinct resource, network, authentication, and communication policies, a `policy_enforcement_agent` is needed. It can inspect CPU/RAM core affinities, check `K:\` drive heartbeats, verify active `gh` CLI credentials, and parse/validate the `depin_ledger` hash chain.
4.  **Orchestrator Coordination**: The orchestrator (`desktop_moe_orchestrator.py`) must routing incoming requests to the appropriate agent. By adopting the Mixture of Experts architecture modeled in `moe_core.py`, it can classify user intent and pass data to the target specialist.

---

## 3. Caveats
*   This investigation did not modify files, write code, or execute migrations. The recommended Python classes are design schemas.
*   Assumes `K:\` drive is mounted and writable. If not, the inter-node handshake protocol (SOP-002) will report violation.
*   Assumes python dependencies such as `psutil` are available on the Windows host.

---

## 4. Conclusion
Milestone M2: R1 should be implemented by creating a new `desktop_moe_orchestrator.py` containing three specialized experts: `schema_migration_agent`, `policy_enforcement_agent`, and `database_query_agent`. Programmatic guards will block any DDL/DML violating SOP-000, verify compliance with SOP-001 through 003, and leash communication through the DePIN gate.

---

## 5. Verification Method
The implementer can verify the strategy by:
1.  Checking that `python tests\e2e_runner.py` or the test suite command passes successfully.
2.  Writing unit tests that attempt to execute a `DELETE` query through the `schema_migration_agent` and asserting that it is blocked with a `SOP-000 Violation`.
3.  Asserting that `database_query_agent` raises an error if an `INSERT` statement is passed.
4.  Triggering high CPU load (e.g. > 85%) and confirming that DePIN gate leashing blocks or defers communication.

---

## 6. Remaining Work
The implementing agent must:
1.  Create `desktop_moe_orchestrator.py` in `C:\Users\viper\gan-otg-db\viper-scripts\`.
2.  Incorporate the specialist Python classes defined in `analysis.md` into the new script.
3.  Add unit tests in `C:\Users\viper\gan-otg-db\tests\` to cover the safe migration and read-only query checks.
