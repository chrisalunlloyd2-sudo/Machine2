# Milestone M2: R1 Strategy & Codebase Analysis Report
**Target Component**: `desktop_moe_orchestrator.py`
**Date**: 2026-06-26

## 1. Orchestrator Location and Context
`desktop_moe_orchestrator.py` must be created at the root of the project:
*   **Path**: `C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py` (or `C:\Viper\projects\desktop_moe_orchestrator.py` via directory junction).
*   **Context**: It acts as the central interface between the **MoeGUI Dashboard** (communicating via JSON stream over stdin/stdout) and the **11 specialist agents** located or supported by scripts in `viper-scripts/`.

---

## 2. Specialist Agent Mapping
The 11 specialist agents are mapped to existing files, databases, and design patterns in the codebase as follows:

| Agent Name | Primary Responsibility | Existing Codebase References | Integration & Action Pattern |
| :--- | :--- | :--- | :--- |
| **`systems_info_agent`** | Queries telemetry (CPU/RAM, CPU clock speed) and logs metrics. | `viper-scripts/resource_governor.py`<br>`viper-scripts/cpu_clock.py`<br>`viper-scripts/cpu_governor.py` | Call `resource_governor.snapshot()` and query `telemetry.db` (`resource_governor` table). |
| **`file_management_agent`** | Encrypted sandboxing, naming convention compliance, and file shredding. | `viper-scripts/encrypted_sandbox.py`<br>`viper-scripts/file-registry.py`<br>`viper-scripts/see.py` | Wrap edit paths with `EncryptedSandbox`. Run naming compliance checks using `file-registry.py` logic. |
| **`database_query_agent`** | Queries sqlite databases for projects, research, code, and catalog. | `nmct_db_manager.py`<br>`viper-scripts/db_governance_loop.py`<br>`viper-scripts/db_perf.py` | Execute standard SQLite queries against `projects.db`, `research.db`, `code.db`, or `nmct_code.db` through `nmct_db_manager`. |
| **`schema_migration_agent`** | Executes DDL/DML schema modifications and updates tables safely. | `nmct_db_manager.py`<br>`viper-scripts/export-schemas.py` | Run table updates. **Constraint:** Must read/verify `SOP-000` compliance first (Never drop/truncate or do destructive changes). |
| **`com_excel_agent`** | Automates Excel/Access sync operations via COM or headless fallback. | `viper-scripts/excel_access_automation.py` | Call `sync_db_to_excel` or `query_access_db` using `win32com.client` (with headless pandas fallback). |
| **`git_sync_agent`** | Monitors git status, automates staging, commits, and pushes. | `viper-scripts/git_diff_ai.py`<br>`viper-scripts/github-auth-device.py` | Check `git status` via subprocess. Run `git_diff_ai.summarize()` / `commit()` to produce local model-driven commit messages. |
| **`voice_integration_agent`** | Syncs Talon profiles and writes voice heartbeat logs. | `viper-scripts/mic_ring.py`<br>`viper-scripts/talon/viper/viper_moe.py` | Monitor/write heartbeat strings to `C:\Users\viper\.kai\moe_heartbeat.txt`. Sync Talon directories. |
| **`aider_bridge_agent`** | Manages pending aider plans and triggers approval pipeline. | `viper-scripts/approve_aider_plan.py` | Scan `aider_bridge/pending/*.md`. Run `approve_and_run(plan_path)` to apply plans via Aider CLI simulation or direct execution. |
| **`search_research_agent`** | Runs local FTS5 research matching and crawler queries. | `viper-scripts/search-code.py`<br>`ArchivalMoe/crawler/playwright_crawler.py` | Execute `playwright_crawler.search_and_crawl(query)` and query the FTS5 table `research_fts` in `research.db`. |
| **`memory_episodic_agent`** | Manages info tree nodes and logs transaction events. | `viper-scripts/memory.py`<br>`viper-scripts/kai_journal.py` | Append transactions using `kai_journal.append()`. Update the `information_trees` table in `nmct_code.db`. |
| **`policy_enforcement_agent`** | Enforces SOP (SOP-000, 001, 002) compliance and DePIN gate leashing. | `viper-scripts/depin_gate.py`<br>`viper-scripts/config/policies/` | Intercept operations using `depin_gate.gate(sender, receiver, content)`. Ensure resource clamping is verified. |

---

## 3. Query Dispatcher and Model Routing Design
To achieve high-efficiency and fail-safe operation on a resource-constrained Xeon box, the dispatcher uses a **three-tier routing architecture**:

### Tier 1: Deterministic Keyword/Regex Classifier (Instant, 0 CPU Cost)
Before invoking any model, the query string is pre-processed and compared against key terms to instantly route required test queries:
*   `"show CPU load"` or `"telemetry"` $\rightarrow$ **`systems_info_agent`**
*   `"commit modified scripts"` or `"git commit"` or `"git push"` $\rightarrow$ **`git_sync_agent`**
*   `"modify projects schema"` or `"migration"` or `"add column"` $\rightarrow$ **`schema_migration_agent`**

### Tier 2: Local Model Classifier Fallback (Low Latency, Local CPU)
If no keyword matches, the dispatcher calls the local model:
*   **API Endpoint**: `http://127.0.0.1:11434/api/generate` (Ollama) or local server `http://localhost:8765/v1/chat/completions` (`viper_llm_server.py`).
*   **Model**: `qwen2.5-coder:0.5b` (lightweight, mmapped) or `SmolLM2-360M`.
*   **Prompt**:
    ```text
    You are the Router agent. Classify the user query into exactly ONE of these specialist agents:
    - systems_info_agent: queries CPU/RAM and telemetry
    - file_management_agent: manages sandbox, files, shredding
    - database_query_agent: queries databases
    - schema_migration_agent: modifies database tables
    - com_excel_agent: Excel/Access automation
    - git_sync_agent: git commits, status, push
    - voice_integration_agent: Talon voice profiles, heartbeat logs
    - aider_bridge_agent: aider plan approvals
    - search_research_agent: web search, FTS5 matching, web crawlers
    - memory_episodic_agent: logging journal events and info tree nodes
    - policy_enforcement_agent: enforces SOP compliance and DePIN gating

    User Query: "{query}"

    Reply with ONLY the exact name of the selected agent. No explanation.
    ```

### Tier 3: Ask_Kai / Parental Routing (High Accuracy, Shared CPU)
If the local model server is offline, returns an error, or if `resource_governor.overloaded()` is true, the dispatcher calls:
*   `ask_kai.py` (via `kqml_bridge.send_to_kai`) to delegate the classification task to the parent Kai agent. It waits for the reply via conversation history or bridge output.

---

## 4. Orchestrator Implementation Strategy and Structure
The `desktop_moe_orchestrator.py` should follow a modular structure, maintaining a non-blocking stdin reader loop to integrate with JavaFX MoeGUI.

### Detailed Design Sketch
```python
# C:\Users\viper\gan-otg-db\desktop_moe_orchestrator.py
import sys
import os
import json
import traceback

# Insert script directories
sys.path.append(os.path.join(os.path.dirname(__file__), "viper-scripts"))

import resource_governor
import depin_gate
import blueprint_orchestrator

# Import agents / mock stubs
# Each agent exposes a main run function: run(query, project_context)
# ...

def get_telemetry_payload():
    """Fetches real-time telemetry and blueprint tracker state."""
    telemetry = resource_governor.snapshot()
    # Parse completed percentage from blueprint_orchestrator or local status
    phases = blueprint_orchestrator.evaluate_blueprint_status()
    completed_steps = sum(1 for p in phases for s in p["steps"] if s["status"] == "completed")
    total_steps = sum(len(p["steps"]) for p in phases)
    pct = round((completed_steps / total_steps) * 100, 1) if total_steps > 0 else 0.0
    return {
        "telemetry": {
            "cpu": telemetry.get("cpu", 50.0),
            "ram": telemetry.get("ram", 60.0)
        },
        "blueprint": {
            "completed_pct": pct
        }
    }

def dispatch_query(query, project):
    """Tiered dispatch logic to select agent and execute."""
    query_clean = query.strip().lower()
    
    # Tier 1: Deterministic Keyword Routing
    if any(k in query_clean for k in ["cpu load", "cpu percent", "ram usage", "telemetry"]):
        agent_name = "systems_info_agent"
    elif any(k in query_clean for k in ["commit modified scripts", "git commit", "git push"]):
        agent_name = "git_sync_agent"
    elif any(k in query_clean for k in ["modify projects schema", "schema migration", "add column"]):
        agent_name = "schema_migration_agent"
    else:
        # Tier 2: Local Model Classifier Fallback
        # (calls qwen2.5-coder:0.5b to classify)
        agent_name = run_local_model_classifier(query)
        
        # Tier 3: Ask_Kai / Parental Routing Fallback
        if not agent_name or agent_name == "error":
            agent_name = run_ask_kai_classifier(query)
            
    # Fallback to general database/search if classification fails
    if not agent_name:
        agent_name = "database_query_agent"
        
    # Policy and DePIN Leash Check via policy_enforcement_agent
    g = depin_gate.gate("orchestrator", agent_name, query)
    if not g["allowed"]:
        return f"Blocked by DePIN Gate: {g.get('reason', 'Telemetry limits exceeded.')}"
        
    # Execute selected specialist agent
    return execute_specialist(agent_name, query, project)

def main_loop():
    """Main stdin/stdout JSON lines listener loop for MoeGUI."""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            
            data = json.loads(line.strip())
            
            if data.get("telemetry_request"):
                # GUI telemetry ping
                payload = get_telemetry_payload()
                print(json.dumps(payload), flush=True)
                
            elif "query" in data:
                query = data["query"]
                project = data.get("project", "")
                
                # Run dispatcher
                answer = dispatch_query(query, project)
                
                # Write final output packet
                print(json.dumps({"answer": answer, "done": True}), flush=True)
                
        except Exception as e:
            err = {"answer": f"Orchestrator error: {str(e)}\n{traceback.format_exc()}", "done": True}
            print(json.dumps(err), flush=True)

if __name__ == "__main__":
    main_loop()
```

---

## 5. Verification Plan
*   **Validation Command**: Execute a test script to check standard inputs/outputs:
    ```powershell
    # Test telemetry response
    echo '{"telemetry_request": true}' | python desktop_moe_orchestrator.py
    
    # Test routing to systems_info_agent
    echo '{"query": "show CPU load", "project": ""}' | python desktop_moe_orchestrator.py
    
    # Test routing to git_sync_agent
    echo '{"query": "commit modified scripts", "project": ""}' | python desktop_moe_orchestrator.py
    
    # Test routing to schema_migration_agent
    echo '{"query": "modify projects schema", "project": ""}' | python desktop_moe_orchestrator.py
    ```
*   **Success Metric**: Each response must output a single JSON line containing the expected telemetry keys or `{"answer": "...", "done": true}` mapping to the correct agent output without hangs.
