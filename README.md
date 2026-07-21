# VIPER Machine 2 Ecosystem: Architectural Whitepaper & Blueprint
> **Sovereign Database Orchestration, Karoo GP Code Mining, and Dynamic LLM Substrate Governance**

---

## 1. System Topology & Dual-Machine Mesh

The VIPER architecture is a dual-machine cognitive mesh. Machine 1 (the SLM Agent Loop and reasoning engine) communicates with Machine 2 (the Java RISC Core and database infrastructure) over high-throughput, dual-channel sockets to sync state, trade logit matrices, and maintain shared contextual memories.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    VIPER SYSTEM — DUAL MACHINE ARCHITECTURE                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ┌─────────────────────────┐        ┌─────────────────────────────────┐     ║
║  │     MACHINE 1           │        │        MACHINE 2                │     ║
║  │  (Aegis / Picoclaw)     │        │   (VIPER JAVA RISC)             │     ║
║  │                         │        │                                 │     ║
║  │  - SLM Agent Loop       │◄══════►│  - JavaFX HUD & Controller      │     ║
║  │  - Aegis Prompts        ║CHANNEL ║  - Karoo Code Miner             │     ║
║  │  - Inference            ║A:18283 ║  - OTG Dual Bridge              │     ║
║  │  - Research Tasks       ║B:18284 ║  - Database Engine (WAL Mode)   │     ║
║  │  - Reasoning Loops      │        │  - Sprite Team Overseer         │     ║
║  │                         │        │  - House Inference Engine       │     ║
║  └─────────────────────────┘        └─────────────────────────────────┘     ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## 2. Port Map & Network Topology

| Port | Service Name | Role & Responsibility |
| :--- | :--- | :--- |
| **8085** | Java Manifold Server | Serves the local Web HUD and routes user commands |
| **8090** | Java Lab Suite | Training dashboard hosting cognitive benchmarking |
| **8091** | Java Notes Server | Persistence layer handling plain-text document storage |
| **11435**| House Inference Engine| CPU LLM (llama.cpp / Gemma 2B) running local AI queries |
| **18082**| OTG GAN Bridge | Dynamic database synchronization adapter |
| **18285**| Sprite Team Overseer | Routes task directives to expert agents (Moe, Kai, etc.) |
| **18283**| OTG Bridge A | Primary channel for Machine 1 communications |
| **18284**| OTG Bridge B | Redundant channel for Machine 1 communications |

---

## 3. Core Architectural Subsystems

### A. The Java Control Plane (ViperFXApp)
The desktop frontend acts as the executive controller for the entire ecosystem. Rather than just auditing status, the Java application controls model deployment:
*   **LLM Inference Registry Controller**: Exposes model parameters (Sprite Role, GGUF path, LoRA path) directly to the user. Deploys configuration updates into `graph.db::inference_model_registry` via SQLite JDBC.
*   **Sprite Team AI Chat Console**: Wires a persistent native console posting directives directly to the Sprite Overseer on port `18285`, tracking thoughts and routes.
*   **Heartbeat Tick Tree**: Drives deterministic periodic polling tasks (1s, 5s, 60s, 120s) to gather database metrics and verify telemetry.

### B. SQLite WAL Mode Database Engine
To guarantee zero-locking database operations and prevent `database is locked` contentions between the Java app and concurrent Python background loops, all primary databases (including `local_knowledge.db` and `graph.db`) use Write-Ahead Logging (WAL):
*   **WAL Mode**: Read transactions execute concurrently with write transactions.
*   **Pragma Tuning**: Configured with `busy_timeout = 30000` (30 seconds) and `synchronous = NORMAL` for high write throughput.

### C. Self-Healing Chaos Engineering (chaos_event_simulation.py)
A test-driven recovery harness verifying Phase 8 sign-off rules. It simulates file deletions and configuration corruption, proving that the system auto-recovers back to nominal state within 3.5 seconds.

### D. GitHub SOP Pull Loop (github_sop_pull.py)
Periodically pulls remote git branches to ingest markdown-based Standard Operating Procedures (SOPs) directly into `local_knowledge.db::SOP_RECALL_CARDS` table to guide AI reasoning context.

---

## 4. Initialization & Deployment Blueprint

To deploy the unified ecosystem:

```powershell
# 1. Clear any duplicate orphaned processes
python C:\Users\viper\VIPER_JAVA_RISC\tools\chaos_event_simulation.py --cleanup

# 2. Start the Master Watchdog Daemon (starts Python backends)
python C:\Users\viper\VIPER_JAVA_RISC\tools\viper_master_watchdog.py

# 3. Build & Run the Standalone JavaFX app
powershell -NoProfile -File C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\BUILD_STANDALONE_APP.ps1
powershell -NoProfile -File C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\RUN_STANDALONE_APP.ps1
```

---

## 5. Development Checkpoint & Verification Phases

### Phase 8: Sentinel & Symbiotic Shielding [Sealed]
1.  Verify loop breaker halts repetitive failures. -> **PASSED**
2.  Enable WAL mode across local SQLite datastores. -> **PASSED**
3.  Dry-run SQL transactions using explain query plans. -> **PASSED**
4.  Verify self-healing chaos recovery suite. -> **PASSED**

### Phase 9: UI Convergence & Sprite Orchestration [In Progress]
1.  Sync local chat consoles directly to Gemma 2B. -> **PASSED**
2.  Deploy live Sprite Team console routing to Overseer. -> **PASSED**
3.  Orchestrate model registry bindings over JDBC. -> **PASSED**
