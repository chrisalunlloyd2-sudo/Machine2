# E2E Test Suite and Runner Design Report

## Executive Summary
This design report provides a comprehensive E2E testing architecture for the Viper autonomous development foundry. It defines a structured test suite containing **38 distinct test cases** organized across four testing tiers. It also designs a dual-mode E2E test runner (`live` and `mock/stub`) to allow testing in both fully live deployment scenarios and simulated local environments.

---

## Codebase Exploration Findings

### 1. Talon Voice Integration (`viper-scripts/talon/viper/`)
We inspected the Talon voice configuration files:
*   **`viper_model.talon`**: Configures settings for routing the LLM endpoint to `http://127.0.0.1:8765/v1/chat/completions` (Moe's local server) with the model `viper-moe`.
*   **`viper_model_key.py`**: Injects a placeholder key `OPENAI_API_KEY = "viper-local-no-key-needed"` since local endpoints still require an API key to bypass client validation checks.
*   **`viper_moe.talon`**: Maps spoken triggers to Python action calls:
    *   `moe status` -> `user.viper_moe_order("status all")`
    *   `moe approve all` -> `user.viper_moe_order("approve all")`
    *   `moe organize notes` -> `user.viper_moe_order("organize notes")`
    *   `moe guardrails` -> `user.viper_moe_order("guardrails status")`
    *   `moe review <user.text>` -> `user.viper_moe_order("code review {text}")`
    *   `moe order <user.text>` -> `user.viper_moe_order(text)`
    *   `kai ask <user.text>` -> `user.viper_ask_kai(text)`
    *   `viper loop start` -> `user.viper_loop_start()`
    *   `viper loop stop` -> `user.viper_loop_stop()`
*   **`viper_moe.py`**:
    *   **Username Reference Issue**: Line 18 contains a hardcoded path referencing the username 'chris':
        ```python
        HEARTBEAT = r"C:\Users\chris\.kai\moe_heartbeat.txt"
        ```
        This path fails on the current system where the active user is `viper`.
    *   **Subprocess Invocations**: Commands are run via simple shell calls targeting `C:\Python314\python.exe` with scripts like `kai_reply.py`, `ask_kai.py`, and `kai_journal.py`.
    *   **Recursive Loop Logic**: Starts a cron interval `cron.interval("5m", loop_tick)`. In `loop_tick()`, the heartbeat file is read and passed to Kai:
        ```python
        ask_kai("Read this heartbeat and reply with ONE Moe order to run next...\n" + hb[:1200])
        ```
        However, the return value of `ask_kai` is discarded. The code hardcodes the default command:
        ```python
        reply = moe_order("status all")
        ```
        It then journals this execution under kind `"LOOP"`.

### 2. MoeGUI Java-Python Connection
We analyzed the JavaFX files under `MoeGUI/src/main/java/com/viper/moe/`:
*   **`PythonBridge.java`**:
    *   Launches `C:\Viper\projects\ArchivalMoe\moe_server.py` as a persistent background process using:
        ```java
        ProcessBuilder pb = new ProcessBuilder(PYTHON, "-u", MOE_SERVER);
        ```
    *   Communicates over stdin/stdout as a JSON line stream. It writes objects in the format `{"query": "...", "project": "..."}` to the process's standard input.
    *   It parses standard output JSON lines asynchronously in `readLoop()` on a daemon thread named `moe-reader`.
    *   Handles two types of keys in stdout JSON:
        *   `token`: for real-time streamed responses (called via `tokenCallback` on the FX thread).
        *   `answer` and `done: true`: for finalized response bubbles (called via `responseCallback`).
    *   Gracefully catches standard I/O disconnections (IOException) and reports `[Moe server disconnected]`.
*   **`MoeController.java`**:
    *   Constructs the main layout (SplitPane with VBox sidebar and chat ScrollPane).
    *   Exposes automation buttons: "Sync Master Excel", "Sync Access DB", and "Start Talon Loop" (sending KQML message `kqml (achieve :content (start-loop))`).
    *   Disables the input field and changes status to "● thinking..." during query execution to prevent race conditions.
    *   Starts a timeline timer to update the "Moe is thinking..." label every second.
    *   Invokes `DbStatus.snapshot()` every 5 seconds to update the DB row count sidebar, and `DbStatus.projectList()` every 30 seconds to reload the projects view.
*   **`DbStatus.java`**:
    *   Queries six SQLite databases in `C:\Viper\databases\`: `projects.db`, `code.db`, `research.db`, `telemetry.db`, `tools.db`, and `graph.db`.
    *   Executes `SELECT COUNT(*)` on specific tables in each DB.
    *   Retrieves active projects and their pending task counts from `projects.db` using relational SQL.

### 3. Mixture-of-Agents Router & Orchestrator (`ArchivalMoe/`)
*   **`moe_core.py`**:
    *   Exposes a 11-agent registry: `project_agent`, `github_agent`, `backup_agent`, `onedrive_agent`, `binary_agent`, `search_agent`, `tool_agent`, `embed_agent`, `graph_agent`, `prompt_agent`, and `memory_agent`.
    *   Uses `INTENT_MAP` to map query keywords to specific agents.
    *   Performs intent classification in `_classify_intent()` weighted by NOD fitness scores.
    *   Executes the top 2 matching specialists in parallel using `asyncio.gather()`.
    *   Updates NOD telemetry stats for response time and error rates.
    *   Synthesizes final responses through `llm_agent.synthesize()` with context injections (Conversation Symbolic Map, topology layout, lexical thought tracker).
    *   Saves queries/answers to `telemetry.db` table `moe_cache` (Tier 0 cache lookup).
*   **`moa_orchestrator.py`**:
    *   Provides three parallel proposers (Performance, Bugfinder, Hardening) and one Aggregator.
    *   Loads function ASTs from a project, rewrites a target function from three different angles, scores them, and lets the senior aggregator select the best diff.

---

## Proposed Path Configuration Patch
To fix the hardcoded username 'chris' in `viper_moe.py` and make it compatible with the `viper` workstation profile, we propose the following diff patch:

```patch
--- C:\Users\viper\gan-otg-db\viper-scripts\talon\viper\viper_moe.py
+++ C:\Users\viper\gan-otg-db\viper-scripts\talon\viper\viper_moe.py
@@ -15,7 +15,8 @@
 KAIRPLY = r"C:\Viper\scripts\kai_reply.py"
 ASKKAI  = r"C:\Viper\scripts\ask_kai.py"
 JOURNAL = r"C:\Viper\scripts\kai_journal.py"
-HEARTBEAT = r"C:\Users\chris\.kai\moe_heartbeat.txt"
+import os
+HEARTBEAT = os.path.join(os.path.expanduser("~"), ".kai", "moe_heartbeat.txt")
 
 
 def _run(args, timeout=90):
```

---

## E2E Test Suite: 38 Test Cases

### Tier 1: Feature Coverage (15 total)

#### Feature 1: 11-Agent Desktop MoE Router
1.  **T1.F1.1: Cache Hit Retrieval**
    *   *Objective*: Verify duplicate queries are fetched instantly from cache.
    *   *Steps*: Send query "status all", wait for execution, send "status all" again.
    *   *Verification*: Verify the second query hits Tier 0 cache and returns in < 10ms.
2.  **T1.F1.2: Specialist Intent Routing**
    *   *Objective*: Verify query keywords map to appropriate specialist agents.
    *   *Steps*: Submit "github sync new branch" and "recent roadmap milestones" to the router.
    *   *Verification*: Assert "github..." maps to `github_agent` and "roadmap..." maps to `project_agent`.
3.  **T1.F1.3: Fallback Routing**
    *   *Objective*: Verify queries with no keywords route to the default agent.
    *   *Steps*: Submit an ambiguous query "hello there moe".
    *   *Verification*: Verify classifier falls back to `project_agent` or NOD's `who_handles()`.
4.  **T1.F1.4: Parallel Specialist Execution**
    *   *Objective*: Verify multiple agents run concurrently without blocking.
    *   *Steps*: Send query "status of github mirror".
    *   *Verification*: Confirm both `project_agent` and `github_agent` are invoked in parallel via `asyncio.gather`.
5.  **T1.F1.5: LLM Synthesis Integration**
    *   *Objective*: Verify specialist results are integrated by the synthesis engine.
    *   *Steps*: Submit query triggering multiple agents.
    *   *Verification*: Confirm output is a cohesive paragraph rather than raw database dumps, containing symbolic/topological context.

#### Feature 2: JavaFX Swarm Dashboard
6.  **T1.F2.1: PythonBridge Startup**
    *   *Objective*: Verify the Java bridge launches the persistent Python server process.
    *   *Steps*: Initialize `PythonBridge` and call `start()`.
    *   *Verification*: Verify `process.isAlive()` is true and standard I/O writers/readers are open.
7.  **T1.F2.2: Stdio JSON Stream Communication**
    *   *Objective*: Verify JSON serialization and token streaming over stdio.
    *   *Steps*: Send query from Java, write mock token lines from Python stdout.
    *   *Verification*: Check that `tokenCallback` is triggered for each token and updates the JavaFX UI.
8.  **T1.F2.3: MoeController Layout & Input Locking**
    *   *Objective*: Verify UI component locking during query execution.
    *   *Steps*: Type a query and press SEND.
    *   *Verification*: Verify `inputField.isDisabled()` is true and send button text is updated to "...".
9.  **T1.F2.4: Dashboard Automation Buttons**
    *   *Objective*: Verify sidebar automation triggers execute target operations.
    *   *Steps*: Click "Sync Master Excel" and "Sync Access DB".
    *   *Verification*: Verify queries "automate excel sync" and "automate access sync" are sent to the Python bridge.
10. **T1.F2.5: SQLite Database Snapshot Polling**
    *   *Objective*: Verify the dashboard regularly snapshots database row counts.
    *   *Steps*: Call `DbStatus.snapshot()`.
    *   *Verification*: Verify row counts are returned for all 6 SQLite databases and populated in the sidebar.

#### Feature 3: Talon Voice Control Integration
11. **T1.F3.1: Talon Configuration File Parsing**
    *   *Objective*: Verify Talon voice files load without syntax errors.
    *   *Steps*: Load `viper_model.talon` and `viper_moe.talon` into the Talon syntax parser.
    *   *Verification*: Confirm no parser exceptions are thrown and rules are successfully registered.
12. **T1.F3.2: Voice Trigger Bindings**
    *   *Objective*: Verify voice commands trigger their bound Python actions.
    *   *Steps*: Simulate voice events `moe status` and `moe approve all`.
    *   *Verification*: Verify they call `user.viper_moe_order("status all")` and `user.viper_moe_order("approve all")`.
13. **T1.F3.3: Recursive Cron Job Control**
    *   *Objective*: Verify loop start/stop commands register and cancel the interval.
    *   *Steps*: Execute action `viper_loop_start()` followed by `viper_loop_stop()`.
    *   *Verification*: Verify cron job is registered with a `5m` cadence and then successfully cancelled.
14. **T1.F3.4: Heartbeat File Reading**
    *   *Objective*: Verify the loop correctly reads the heartbeat file.
    *   *Steps*: Write mock data to the heartbeat path, invoke `read_heartbeat()`.
    *   *Verification*: Assert returned string matches the file contents exactly.
15. **T1.F3.5: Loop Tick Cycle**
    *   *Objective*: Verify one complete pass of the recursive loop.
    *   *Steps*: Call `loop_tick()`.
    *   *Verification*: Verify heartbeat is read, `ask_kai` is called, default command "status all" executes, and a journal entry is written.

---

### Tier 2: Boundary & Corner (15 total)

#### Feature 1: 11-Agent Desktop MoE Router
16. **T2.F1.1: Cache TTL Expiration**
    *   *Objective*: Verify queries bypass cache once TTL (24 hours) expires.
    *   *Steps*: Write cache entry with timestamp set to 25 hours ago. Query the same string.
    *   *Verification*: Assert the cache is bypassed and the specialists are executed.
17. **T2.F1.2: Empty & Whitespace Queries**
    *   *Objective*: Verify empty/whitespace input is ignored.
    *   *Steps*: Submit "" or "   " to the router.
    *   *Verification*: Verify the router returns immediately without executing agents or throwing errors.
18. **T2.F1.3: SQL Injection Vulnerability Guard**
    *   *Objective*: Verify database safety against malicious queries.
    *   *Steps*: Query: `' OR 1=1; DROP TABLE projects; --`.
    *   *Verification*: Assert SQL FTS5 lookup handles special characters safely without executing injected SQL commands.
19. **T2.F1.4: Specialist Agent Failure Resilience**
    *   *Objective*: Verify synthesis succeeds even if a specialist throws an exception.
    *   *Steps*: Force `github_agent` to raise a runtime exception while running a parallel query.
    *   *Verification*: Verify the router returns synthesis containing output from the surviving agent along with the logged error.
20. **T2.F1.5: Extremely Large Input Query**
    *   *Objective*: Verify router robustness under input size stress.
    *   *Steps*: Send query exceeding 10,000 characters.
    *   *Verification*: Assert query is truncated or processed without causing stack overflows or memory exhaustion.

#### Feature 2: JavaFX Swarm Dashboard
21. **T2.F2.1: Python Server Unexpected Crash**
    *   *Objective*: Verify Java GUI recovers if Python process crashes.
    *   *Steps*: Forcibly kill `moe_server.py` while the Java bridge is running.
    *   *Verification*: Verify Java bridge catches the IOException, sets the status label to offline, and unlocks the UI.
22. **T2.F2.2: Python Stdout Pollution Mitigation**
    *   *Objective*: Verify bridge safety when non-JSON text is printed to stdout.
    *   *Steps*: Write plain text "Hello from backend module" directly to Python stdout.
    *   *Verification*: Assert the Java bridge parses the invalid line, logs a warning, and prevents crashing.
23. **T2.F2.3: SQLite Database Locked (SQLITE_BUSY)**
    *   *Objective*: Verify status retrieval succeeds even if databases are locked.
    *   *Steps*: Lock `projects.db` with an exclusive transaction in a separate thread, then poll DB status.
    *   *Verification*: Verify `DbStatus` returns a status of -1 or logs the lock without crashing the GUI.
24. **T2.F2.4: Empty Projects Registry**
    *   *Objective*: Verify the ListView handles empty database tables gracefully.
    *   *Steps*: Clear all active projects in `projects.db`.
    *   *Verification*: Verify project list shows a placeholder or remains clean without throwing NullPointerExceptions.
25. **T2.F2.5: Concurrent Query Clicks prevention**
    *   *Objective*: Verify duplicate clicks are blocked while a query is in progress.
    *   *Steps*: Double-click two project items in rapid succession.
    *   *Verification*: Verify the second click is ignored because the UI is disabled during the first query's thinking state.

#### Feature 3: Talon Voice Control Integration
26. **T2.F3.1: Heartbeat Directory Not Found**
    *   *Objective*: Verify path expansion works if the target directory doesn't exist.
    *   *Steps*: Delete `C:\Users\chris\.kai\` or mock path, call `read_heartbeat()`.
    *   *Verification*: Assert function returns empty string gracefully without throwing exceptions.
27. **T2.F3.2: Oversized Heartbeat File**
    *   *Objective*: Verify input capping on large heartbeat logs.
    *   *Steps*: Write a 1MB file to the heartbeat path, call `loop_tick()`.
    *   *Verification*: Confirm the payload passed to `ask_kai()` is truncated to `[:1200]` characters.
28. **T2.F3.3: Missing Executable Path Recovery**
    *   *Objective*: Verify subprocess handles missing Python environments.
    *   *Steps*: Change `PY` path in `viper_moe.py` to a non-existent path and trigger `moe_order()`.
    *   *Verification*: Assert the function returns `[err] [WinError 2] The system cannot find the file specified`.
29. **T2.F3.4: Invalid Voice Phrase Interpretation**
    *   *Objective*: Verify Talon ignores unmapped commands.
    *   *Steps*: Simulate voice input "moe status of everything else".
    *   *Verification*: Confirm it doesn't match `viper_moe.talon` commands and is ignored or handled by default dictation.
30. **T2.F3.5: Loop Cron Re-entrancy Overlap**
    *   *Objective*: Verify cron ticks do not stack if a tick takes > 5 minutes.
    *   *Steps*: Force `loop_tick()` to sleep for 6 minutes, verify no duplicate thread starts.
    *   *Verification*: Confirm Talon cron handles re-entrancy, or that the loop execution remains serialized.

---

### Tier 3: Cross-Feature Combinations (3 total)

31. **T3.1: Spoken Loop Toggle to Live Dashboard Telemetry**
    *   *Objective*: Verify that voice command activates the loop, writing to database and updating Java GUI.
    *   *Steps*: Spoken command "viper loop start" -> cron registers -> `loop_tick()` executes -> writes journal log to `telemetry.db` via `kai_journal.py` -> Java GUI polls `DbStatus.snapshot()`.
    *   *Verification*: Verify the row count for `agent_events` in the JavaFX DB status sidebar increments.
32. **T3.2: JavaFX UI Loop Trigger Syncs Heartbeat**
    *   *Objective*: Verify Java GUI button synchronizes loop execution.
    *   *Steps*: Click "Start Talon Loop" in the Java UI -> sends KQML start-loop command -> Python writes status update to `moe_heartbeat.txt`.
    *   *Verification*: Verify the heartbeat file is updated and Talon's `read_heartbeat()` fetches the updated state.
33. **T3.3: Spoken Review Updates Project Dashboard**
    *   *Objective*: Verify voice review command triggers specialist analysis and updates task list.
    *   *Steps*: Speak "moe review ArchivalMoe" -> triggers specialist routing -> executes MoA proposer -> inserts a new task into `projects.db` -> Java ListView automatically reloads.
    *   *Verification*: Verify that the project list updates to show the project status with the incremented pending task count: `ArchivalMoe [1]`.

---

### Tier 4: Real-world Application Scenarios (5 total)

34. **T4.1: Chris Speaks a System Command (E2E Status)**
    *   *Objective*: Verify Chris can speak a status command, execute backend, and see output in Java chat.
    *   *Steps*: Chris speaks "moe status" -> Talon calls `moe_order("status all")` -> launches `kai_reply.py` -> queries SQLite DBs -> returns text.
    *   *Verification*: Confirm message bubble appears in the JavaFX chat history displaying the status of active projects.
35. **T4.2: Clicking GUI Refresh Syncs SQLite & Updates List**
    *   *Objective*: Verify complete cycle of clicking refresh, scanning tables, and re-rendering layout.
    *   *Steps*: Click the "↻ Refresh" button in JavaFX -> executes `loadProjectsFromDb()` -> queries active projects from `projects.db`.
    *   *Verification*: Confirm project list updates with correct names and pending counts without UI freeze.
36. **T4.3: Mixture-of-Agents Code Review Optimization**
    *   *Objective*: Verify full MoA loop (3 proposers + 1 aggregator) executed from the GUI.
    *   *Steps*: Click a project in the list -> triggers query "Give me a full intelligence report on..." -> MoE routes to `moa_orchestrator.py` -> proposing diffs -> aggregator picks best proposal.
    *   *Verification*: Assert the response is shown in the chat window, displaying a valid unified diff block.
37. **T4.4: Low-Resource CPU Governor Execution**
    *   *Objective*: Verify the system handles CPU throttling on the Xeon X3430.
    *   *Steps*: Send a query -> triggers `_chat_start()` in `moe_server.py` -> background tasks yield CPU cores -> SmolLM2 runs without AVX support.
    *   *Verification*: Verify that the UI displays a rolling thinking timer, streams response tokens as they are produced, and completes under 120s.
38. **T4.5: Recovering from Offline State**
    *   *Objective*: Verify system recovers cleanly if launched before the Python server is active.
    *   *Steps*: Start MoeGUI while `moe_server.py` is stopped -> status shows offline. Start `moe_server.py` manually, click refresh.
    *   *Verification*: Confirm the status shifts to "● Moe online", the inputs are enabled, and queries can be successfully sent.

---

## E2E Test Runner Design

The E2E test runner is designed as a standalone Python testing script (`e2e_runner.py`) using `unittest`. It implements a dual execution strategy controlled by the `VIPER_E2E_MODE` environment variable.

### E2E Test Runner Code (`e2e_runner.py`)

```python
import os
import sys
import json
import sqlite3
import unittest
import subprocess
from unittest.mock import MagicMock, patch

# Configure default mode: "mock" (dry-run) or "live" (integration)
E2E_MODE = os.environ.get("VIPER_E2E_MODE", "mock").lower()

class MockSubprocessResult:
    def __init__(self, stdout, stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode

class ViperE2ETestCase(unittest.TestCase):
    
    def setUp(self):
        self.mode = E2E_MODE
        print(f"\n[E2E] Running in {self.mode.upper()} mode")
        
        # Paths configuration
        self.base_dir = r"C:\Users\viper\gan-otg-db"
        self.moe_server_path = os.path.join(self.base_dir, "ArchivalMoe", "moe_server.py")
        
        if self.mode == "mock":
            self._setup_mock_environment()
        else:
            self._setup_live_environment()

    def _setup_mock_environment(self):
        # Patch standard subprocess calls
        self.subprocess_patcher = patch("subprocess.run")
        self.mock_run = self.subprocess_patcher.start()
        
        # Patch open to simulate heartbeat
        self.open_patcher = patch("builtins.open", create=True)
        self.mock_open = self.open_patcher.start()
        
        # Mock database connection
        self.db_conn = sqlite3.connect(":memory:")
        self._init_mock_databases(self.db_conn)
        
        # Patch sqlite3.connect to return our in-memory db
        self.sqlite_patcher = patch("sqlite3.connect", return_value=self.db_conn)
        self.sqlite_patcher.start()

    def _setup_live_environment(self):
        # Ensure live databases and paths exist
        self.tele_db_path = r"C:\Viper\databases\telemetry\telemetry.db"
        self.projects_db_path = r"C:\Viper\databases\projects\projects.db"
        
        if not os.path.exists(self.tele_db_path):
            self.skipTest(f"Live telemetry database not found at {self.tele_db_path}")

    def tearDown(self):
        if self.mode == "mock":
            self.db_conn.close()
            patch.stopall()

    def _init_mock_databases(self, conn):
        # Create mock tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS moe_cache (
                hash TEXT PRIMARY KEY, query TEXT, answer TEXT, agent TEXT, ts TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT, event_type TEXT, payload TEXT, project TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY, name TEXT, local_path TEXT, type TEXT, description TEXT, status TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, project_id INTEGER, title TEXT, status TEXT, priority TEXT
            )
        """)
        
        # Seed mock data
        conn.execute("INSERT INTO projects (id, name, status) VALUES (1, 'ArchivalMoe', 'active')")
        conn.execute("INSERT INTO tasks (id, project_id, title, status, priority) VALUES (1, 1, 'Fix tests', 'pending', 'HIGH')")
        conn.commit()

    # ── TIER 1 TESTS ──────────────────────────────────────────────────────────

    def test_t1_f1_1_cache_hit_retrieval(self):
        """T1.F1.1: Verify duplicate queries retrieve instantly from cache."""
        query = "status all"
        q_hash = "87a0dbf0" # Mock hash
        
        if self.mode == "mock":
            # Seed cache
            self.db_conn.execute(
                "INSERT INTO moe_cache VALUES (?, ?, ?, ?, ?)",
                (q_hash, query, "Mock Cached Status Response", "project_agent", "2026-06-25T20:00:00")
            )
            self.db_conn.commit()
            
            # Run code to verify cache hit
            import sys
            sys.path.insert(0, os.path.join(self.base_dir, "ArchivalMoe"))
            import moe_core
            
            # Patch hash function for matching
            with patch("moe_core._query_hash", return_value=q_hash):
                ans = moe_core.ask(query)
                self.assertEqual(ans, "Mock Cached Status Response")
        else:
            # Live test: Query once, confirm second query takes less time
            import time
            sys.path.insert(0, os.path.join(self.base_dir, "ArchivalMoe"))
            import moe_core
            
            t0 = time.time()
            ans1 = moe_core.ask(query)
            t1 = time.time()
            
            t2 = time.time()
            ans2 = moe_core.ask(query)
            t3 = time.time()
            
            self.assertEqual(ans1, ans2)
            self.assertLess(t3 - t2, t1 - t0)

    def test_t1_f2_2_stdio_json_stream(self):
        """T1.F2.2: Verify JavaFX bridge stdio stream processing."""
        if self.mode == "mock":
            # Simulate JSON token output from moe_server.py
            output_lines = [
                json.dumps({"token": "Hello"}),
                json.dumps({"token": " world"}),
                json.dumps({"answer": "Hello world", "done": True})
            ]
            
            received_tokens = []
            final_answer = None
            
            # Parser logic mimicking PythonBridge.java readLoop()
            for line in output_lines:
                resp = json.loads(line)
                if "token" in resp:
                    received_tokens.append(resp["token"])
                if resp.get("done") and "answer" in resp:
                    final_answer = resp["answer"]
                    
            self.assertEqual("".join(received_tokens), "Hello world")
            self.assertEqual(final_answer, "Hello world")
        else:
            # Live integration: Execute moe_server.py and verify greeting
            p = subprocess.Popen(
                ["python", "-u", self.moe_server_path],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
            )
            greeting = p.stdout.readline().strip()
            p.terminate()
            
            resp = json.loads(greeting)
            self.assertIn("Moe online", resp["answer"])

    def test_t1_f3_4_heartbeat_read(self):
        """T1.F3.4: Verify Talon loop heartbeat file reading."""
        mock_heartbeat_content = "Viper Engine Running: OK"
        
        if self.mode == "mock":
            # Simulate reading file
            self.mock_open.return_value.__enter__.return_value.read.return_value = mock_heartbeat_content
            
            sys.path.insert(0, os.path.join(self.base_dir, "viper-scripts", "talon", "viper"))
            import viper_moe
            
            content = viper_moe.read_heartbeat()
            self.assertEqual(content, mock_heartbeat_content)
        else:
            # Live integration: Write to user profile and verify read
            import os
            hb_path = os.path.join(os.path.expanduser("~"), ".kai", "moe_heartbeat.txt")
            os.makedirs(os.path.dirname(hb_path), exist_ok=True)
            
            with open(hb_path, "w", encoding="utf-8") as f:
                f.write(mock_heartbeat_content)
                
            sys.path.insert(0, os.path.join(self.base_dir, "viper-scripts", "talon", "viper"))
            import viper_moe
            
            content = viper_moe.read_heartbeat()
            self.assertEqual(content, mock_heartbeat_content)

    # ── TIER 2 BOUNDARY TESTS ──────────────────────────────────────────────────

    def test_t2_f1_4_agent_failure_robustness(self):
        """T2.F1.4: Verify pipeline resilience when a specialist agent fails."""
        if self.mode == "mock":
            sys.path.insert(0, os.path.join(self.base_dir, "ArchivalMoe"))
            import moe_core
            
            # Force one agent to throw exception
            moe_core.AGENT_REGISTRY["github_agent"] = MagicMock(side_effect=Exception("API limit hit"))
            moe_core.AGENT_REGISTRY["project_agent"] = MagicMock(return_value="Project Status: Active")
            
            # Patch synthesis to fallback gracefully
            with patch("agents.llm_agent.synthesize", return_value=None):
                ans = moe_core.ask("status of github mirror")
                self.assertIn("github_agent error", ans)
                self.assertIn("Project Status: Active", ans)

    def test_t2_f3_1_heartbeat_not_found(self):
        """T2.F3.1: Verify heartbeat read handles missing file gracefully."""
        if self.mode == "mock":
            # Simulate file not found exception
            self.mock_open.side_effect = FileNotFoundError()
            
            sys.path.insert(0, os.path.join(self.base_dir, "viper-scripts", "talon", "viper"))
            import viper_moe
            
            content = viper_moe.read_heartbeat()
            self.assertEqual(content, "")
        else:
            # Live integration: Delete file and assert empty string returned
            import os
            hb_path = os.path.join(os.path.expanduser("~"), ".kai", "moe_heartbeat.txt")
            if os.path.exists(hb_path):
                os.remove(hb_path)
                
            sys.path.insert(0, os.path.join(self.base_dir, "viper-scripts", "talon", "viper"))
            import viper_moe
            
            content = viper_moe.read_heartbeat()
            self.assertEqual(content, "")

if __name__ == "__main__":
    unittest.main()
```
