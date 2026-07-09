## 2026-06-27T02:20:09Z
You are the Worker (teamwork_preview_worker) for Milestone M2: R1.
Your working directory is C:\Users\viper\gan-otg-db\.agents\worker_m2_gen2_retry2\.
Your task is to implement the desktop swarm orchestrator (desktop_moe_orchestrator.py) at C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py.

### Requirements:
1. Implement a structured dispatcher in desktop_moe_orchestrator.py that routes queries to the 11 specialist agents.
2. Ensure routing works correctly for:
   - "show CPU load" (routes to systems_info_agent)
   - "commit modified scripts" (routes to git_sync_agent)
   - "modify projects schema" (routes to schema_migration_agent)
3. Schema migration agent must check SOP-000 (SOP_NEVER_DELETE.md) compliance first (prohibit DROP, DELETE, TRUNCATE, or destructive alters). It must also create a backup in `C:\Viper\backups\databases` before running the DDL/DML.
4. Implement database_query_agent as a read-only query runner (blocks any write keywords).
5. Implement systems_info_agent querying system CPU/RAM load.
6. Implement policy_enforcement_agent to check compliance with SOP-000, SOP-001, SOP-002, SOP-003, and DePIN gating.
7. Use Ask_Kai or local model routing to select the correct agent. If a query doesn't match deterministic routing (Tier 1), attempt local model classification (Tier 2, e.g., calling local server at http://localhost:8765/v1/chat/completions or Ollama), and fall back to Ask_Kai (Tier 3, using ask_kai.py) or parental routing.
8. Interface with MoeGUI via JSON streams over stdin/stdout. Handle normal queries and telemetry_request pings like `{"telemetry_request": true}` to print telemetry/blueprint percentage states.

### Verification:
Create a test script or run Python checks to verify that:
- It responds to `{"telemetry_request": true}` with the telemetry JSON object.
- It routes query `{"query": "show CPU load"}` to systems_info_agent.
- It routes query `{"query": "commit modified scripts"}` to git_sync_agent.
- It routes query `{"query": "modify projects schema"}` to schema_migration_agent and checks SOP-000.

Run the newly published E2E test suite `C:\Users\viper\gan-otg-db\viper-scripts\test_moe_e2e_new.py` (in mock mode) to verify that your implementation satisfies all related test cases.

### Output:
Write a completion report to C:\Users\viper\gan-otg-db\.agents\worker_m2_gen2_retry2\handoff.md detailing the implemented code, tests run, and verification command output.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.
