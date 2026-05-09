# VIPER RISC LAB (Java Edition)

## Architecture Overview
This is the **HOUSE OPTION** environment. It is a strictly **FULL JAVA ONLY** backend, serving a 3D vector database visualizer (Three.js).

### Features
1. **3D Vector Visual:** Real-time visualization of the topological matrix and RGB Singlets.
2. **Recursive Rolling Responses:** Polling endpoints serving perfect info lookups.
3. **RISC API:** Endpoint for SHA-256 packet export/deport (`/api/risc/export`, `/api/risc/deport`).
4. **Blockchain Publisher:** Simulates appending the `SUCCESS_DB` to a SHA-256 cryptographic ledger (`/api/blockchain/publish`).
5. **Loihi Twinning:** Tracks neuron growth (`/api/loihi/neurons`) as Karoo optimizes the network in the background.

## 🛡️ 101% Architecture: THE TRIPLETED MANIFOLD
This system is a self-healing, autonomous neuromorphic substrate.

### Core Components
1. **House Inference Engine (Port 11435):** Native GGUF loading via llama-cpp-python. Ollama-independent.
2. **RISC Bridge (Port 8080):** Python-Java hybrid logic connecting the SQL Manifold to the GUI.
3. **Infinite Triplet Loop:** Karoo-driven background learning and Loihi neuron stimulation.
4. **3D Manifold GUI:** Real-time visual representation of 151+ SQL data points with hover tooltips and a Karoo Orbiter.

### 🚀 Execution (The 1-Click Seal)
Simply run `START_MANIFOLD.bat` in the root directory.
- This purges zombie processes.
- Restores all backend servers.
- Synchronizes the public Cloudflare URL to OneDrive and the Desktop.
- Opens the interface in your default browser.

### 📱 Phone Sync
The public Cloudflare tunnel allows you to access your manifold on any device (including your phone) via the verified URL in `CLOUDFLARE_URL.txt`.

## Current Checkpoint: Topological Control Plane

The live GUI remains the locked visual surface. Sidecars now carry the experimental logic so the main page can stay responsive and familiar.

```text
                         +-----------------------------+
                         |  Cloud SHA-256 Logic Ledger |
                         |  ACL/KQML Uplink / Replicas |
                         +--------------+--------------+
                                        ^
                                        |
+----------------+       +-------------+--------------+       +----------------+
|  Web Manifold  | <---> |  RISC Bridge / House Model | <---> | gemini_bridge  |
|  Three.js GUI  |       |  chat + last 25 DB memory  |       | SQLite LogicDB |
+-------+--------+       +-------------+--------------+       +-------+--------+
        |                              |                              |
        | browser localStorage         | sidecar approval only         |
        v                              v                              v
  last 10 replies           +----------+-----------+       +----------+----------+
                            | Karoo Topology Loop  |       | Loihi Spike Sidecar |
                            | env maps + proposals |       | 100^3 sparse cube   |
                            +----------+-----------+       +----------+----------+
                                       |                              |
                                       v                              v
                             Approval Reports              Spike Reports / Hashes
```

### Memory and Reasoning Notes

- Browser chat keeps the last 10 user/TRIPLET replies across refresh or close via `localStorage`.
- Backend chat memory stores the last 25 user/TRIPLET exchanges in `CHAT_MEMORY` and includes them in the house model context.
- The model is prompted for a short visible `<thought>` reasoning-note when useful. This is a compact rationale surface, not proof of hidden internal chain-of-thought.

### Sidecar Inventory

- `tools/topology_sidecar.py`: checkpoints, topological chunks, Karoo approval reports, dislike repair queue, hash queue.
- `tools/performative_router.py`: FIPA/KQML-inspired `chat | performative | both` classifier.
- `tools/data_retrieval_lens_agent.py`: fast retrieval chooser and Fabric lens crafter. It classifies each ask as `chat`, `planning`, or `build`, searches local logic tables for matching source hashes, sets a token budget, logs one active lens per turn, and creates proposal-only Karoo epoch requests for planning/build.
- `tools/tiny_model_runtime.py`: real GGUF tiny-model runtime. Qwen2.5-0.5B writes the active chooser lens and rolling triplet card; SmolLM2-360M chooses the closest 50-word axiomatic DB match; H2O-Danube3 is the fallback matcher.
- `tools/logic_blockchain_shipper.py`: local port `18081` for logic-only SHA-256 shipping.
- `tools/loihi_spike_sidecar.py`: sparse 100x100x100 top-code spike experiments with Lava/Loihi backend manifesting.
- `tools/ledger_sync_readiness.py`: redundancy contracts for cloud/non-local ledger replicas and agent access.
- `tools/global_agent_network.py`: ACL/KQML agent registry, capability broadcasts, GAME_DATA, global TODOs, POE/PON, security events, and kernel evolution proposals.
- `tools/extract_global_todos.py`: mines local handoff/docs/log/DB text for TODO-like tasks and merges them into `GLOBAL_TODO_QUEUE` with random round-robin assignment.
- `tools/missed_message_relay.py`: stores unconfirmed long-running agent completions and repeats them in the next active window until confirmed.
- `agent_control_web/`: managed copy of the locked webpage for future Java SHA-256 ledger/control-plane ownership.
- `java_notes_suite/`: Java/JDK notes, dev, script index, and persistent SDK suite. It is append-only and resource-gated; it starts only when Java/JDK are present.
- `java_notes_suite/src/com/viper/notes/ViperLabSuiteServer.java`: VS Code-like Java SDK for benchmarks, service watch, user topology, predictive prefetch, persistent settings, system tests, AB tests, training logs, Loihi experiment logs, and log tails. Intended local URL: `http://127.0.0.1:18181`.
- `JAVA_SDK_PERSISTENCE_DESIGN.md`: persistence, Java SDK endpoints, Loihi/Lava sidecar contract, Fabric 15-word lens-card design, Karoo promotion gate, and test methodology.
- `AGENT_APP_DEV_PROTOCOL.md`: Karoo/app-development, announce, device-role, Loihi, and round-robin rules.
- `AGENT_SPECS.md`: heartbeat fields, install gates, and speed/stability optimization profiles.
- `RESOURCE_NETWORK_PROTOCOL.md`: public hookup, scoring, task leasing, proof, and phone/laptop/CLI scaling rules for the overnight resource network.
- `ASCII_MODIFICATION_LEDGER.md`: append-only ASCII visual log of every modification from the retrieval/lens checkpoint forward.

### Retrieval and Fabric Lens Flow

```text
messy ask
   |
   v
data_retrieval_lens_agent.py
   |-- classify: chat / planning / build
   |-- map: programming / chat / generalist Fabric layer
   |-- search: TRIPLET, RAG, TOPO, ACL, TODO, GAME_DATA, LOGIC_SOURCES
   |-- SmolLM2: closest 50-word axiomatic DB match
   |-- Qwen2.5: max-100-word active chooser lens
   |-- Qwen2.5: rolling recursive triplet control card
   |-- budget: route-specific max tokens
   v
RISC bridge /api/loibi/predict
   |-- chat: direct answer, no Karoo
   |-- planning: log Karoo epoch request, proposal-only
   |-- build: log 20-loop Karoo genetic build request, proposal-only
```

Straight chat injects a compact lens only. Full retrieval matches are stored in SQLite so local model context stays small and fast.

Tiny model defaults:

```text
VIPER_TINY_CHOOSER_MODEL=models/tiny/qwen2_5_0_5b_instruct/qwen2.5-0.5b-instruct-q4_k_m.gguf
VIPER_RETRIEVAL_MATCHER_MODEL=models/tiny/smollm2_360m_instruct/SmolLM2-360M-Instruct-Q4_K_M.gguf
VIPER_RETRIEVAL_FALLBACK_MODEL=models/tiny/h2o_danube3_500m_chat_fallback/h2o-danube3-500m-chat-Q4_K_M.gguf
```

### Epoch Upgrade Proofs

Current SDK version:

```text
0.4.0-real-tiny-chooser
```

The Java SDK now has an evidence-based upgrade proof path:

```text
POST http://127.0.0.1:18181/api/epoch-upgrade-proof
```

It reads live bridge benchmarks, house health, shipper health, shipper logs,
and topology logs, then emits high-contrast proposed-change cards with:

```text
problem
evidence
PROPOSED CHANGE
acceptance test
test result: TBD
SHA-256 proof
```

Approved pending-test epoch upgrades:

```text
EPOCH_BRIDGE_HEADROOM_REPAIR
EPOCH_SHIPPER_UPLINK_COMPAT
EPOCH_KAROO_COMPARATOR_ATTACH
EPOCH_SOVEREIGN_AGENT_CONTRACT
EPOCH_ROLLING_TRIPLET_RESTORE
EPOCH_MISSION_DIRECTIVE_ALWAYS_ON
EPOCH_LONG_RESPONSE_TAIL_STITCH
EPOCH_INFERENCE_OPTIMIZATION_STACK
EPOCH_DISTRIBUTED_RESOURCE_APP
EPOCH_AXIOMATIC_WEIGHTED_TRUTH_TABLES
EPOCH_REAL_TINY_CHOOSER
EPOCH_AXIOMATIC_RETRIEVAL_MATCHER
EPOCH_NAS_AGENT_SPINUP_SYNC
```

The local model defaults now give longer response headroom. The bridge mission
directive restores the rolling recursive triplet idea:

```text
tiny chooser -> light draft -> Karoo/action edit -> verifier edit -> tail stitch
```

Real tiny chooser path now logs:

```text
AXIOMATIC_RETRIEVAL_MATCHES
TINY_MODEL_EVENTS
ROLLING_TRIPLET_RUNS
BENCHMARK_EVENTS(component=tiny_model_runtime)
USER_WORD_STATS
USER_TOPOLOGICAL_WANTS
```

Inference optimization proposals are staged as test-gated epochs:

```text
quantization
prefix caching
prefill/decode split
Flash Attention
continuous batching
KV cache management
speculative decoding
```

Coding proposals should use axiomatic weighted truth tables:

```text
axiom | evidence | counterexample | weight | confidence | test | verdict
```

### Chat Stall Repair

Long questions were failing because the local house model path could block or crash while the webpage waited. The bridge now:

- crafts/logs a lens before model generation;
- preflights `http://localhost:11435/health`;
- caps user-facing wait time by route;
- returns a Qwen tiny fallback, then deterministic guardrails only if tiny is unavailable;
- keeps the GUI live while slow Karoo/build work remains logged.

The house sidecar was also changed to `ThreadingHTTPServer`, gained `/health`, moved to absolute DB paths, and removed Windows-hostile emoji console logs. Current note: direct tiny house generations work, but bridge prompts can still trigger a llama-cpp/Gemma sidecar crash, so the bridge health guard remains active.

The house sidecar now has an inference governor:

- route-aware prompt packing;
- serial llama access;
- retry ladder for output tokens;
- `/config` metadata;
- larger `n_ctx` with bounded input budgets;
- non-blocking build route from the bridge.

Build requests create the full dynamic lens and Karoo/webcrawl queues, then
return quickly. Chat/planning may call house synchronously with bounded prompts.

### Predictive User Topology and Benchmarks

The bridge now keeps a condensed user topology profile for chooser decisions:

```text
CHAT_MEMORY every 5 chats
  -> USER_TOPOLOGY_PROFILE
  -> compact goals/preferences/instructions
  -> predictive terms for first-words routing
```

Endpoints:

```text
GET /api/predictive/prefetch?q=<partial ask>
GET /api/user/topology
GET /api/benchmarks?limit=20
```

The system uses a visible rationale contract, not hidden chain-of-thought
exposure. The agent may show concise rationale and decision metadata while
keeping private reasoning private.

### 15-Word Lens Cards

The 15-word limit is an internal routing tool, not a user-visible reply cap.
Tiny/local chooser layers write compact cards for:

- current ask summary;
- matching database summary;
- recent prompt summary;
- reply-quality or repair trigger summary.

Those cards feed the chosen Fabric lens and the larger local model. The final
chat response keeps normal headroom, with chat/planning reply tokens raised and
build work kept proposal/async so the GUI stays live.

### Dynamic Fabric and Development SOP

The chooser now treats Fabric as a changing per-request template instead of a
static prompt. Each lens logs:

- route-specific token budget;
- database hooks;
- successful-code hooks for programming;
- webcrawl research request, if planning/build needs current context;
- noise policy for reducing crawled content before model injection.

For programming/build requests, successful local code is pulled first from:

```text
CODE_BLOCKCHAIN_DB
BLOCKCHAIN_LEDGER
LOGIC_BLOCKCHAIN_QUEUE(status=shipped)
TOPO_CANDIDATES
```

The future team SOP is documented in `AGENT_APP_DEV_PROTOCOL.md`: dynamic lens,
successful-code pull, reduced webcrawl, 12-agent passoff up to 20 rounds,
Viper compile/upload checkpoint, README writeup, and user pingback.

### Approval and Auto-Advance Rule

Karoo, Loihi, cloud CLI pairs, and global agents may map, compare, hash, propose, and report.

Auto-advance is allowed only when the measured variable passes the hard gate:

```text
success_rate >= 99.99%
AND
(speed_gain >= 10% OR resource_drop >= 10%)
```

Anything below that remains proposal-only. GUI visual changes, raw model weight mutation, security/auth bypass, destructive filesystem changes, and unapproved raw data export are always outside the auto-advance scope.

### Global Agent Network Direction

Every agent should begin with a quick look and then broadcast what it is made of and what it can do:

```text
(tell :sender <agent> :receiver all
  :content (broadcast-capabilities
    :made-of <runtime/db/model/tools>
    :can-do <actions>
    :requires poe pon approval))
```

The network treats communication as ACL/KQML first:

- `GLOBAL_AGENT_REGISTRY`: identity, endpoint, capabilities, material stack.
- `GLOBAL_ACL_MESSAGES`: all agent-to-agent messages and global broadcasts.
- `GLOBAL_TODO_QUEUE`: portable work queue any registered agent can propose to complete.
- `GAME_DATA`: shared hash-first state for logic, code snippets, security, and coordination.
- `PROOF_OF_EXECUTION` and `PROOF_OF_NETWORK`: POE/PON evidence before trust increases.
- `NETWORK_SECURITY_EVENTS`: live heuristic/algorithmic security observations.
- `KERNEL_EVOLUTION_PROPOSALS`: proposal-only kernel evolution experiments.

### Heartbeat and Resource-Fit Installs

VIPER uses a small custom heartbeat pattern inspired by common heartbeat systems rather than installing a heavy monitoring stack by default. Each agent can report:

```text
agent_id, endpoint, status
cpu cores, available RAM, free disk
available tools: python, java, node, git, rustc, cargo
resource_sha256
```

Install logic is gated:

```text
only install or assign systems the node has resources and tools for
```

The current 8-node circle is recorded in `AGENT_CIRCLE_HEARTBEAT_PLAN` with a
300-second planned interval. This is a coordination map only; actual compute
lending still requires each node to announce an endpoint and proof data.

Current install rule examples:

- `tiny_sidecar`: low-resource Python sidecars and lens/router scripts.
- `java_agent`: Java services only when Java and enough RAM/disk are present.
- `rust_builder`: Rust builders only when `rustc` and `cargo` are present.
- `heavy_model_node`: local model serving only when enough RAM/disk are free.

Commands:

```powershell
python tools/global_agent_network.py heartbeat --agent-id local_viper_control --endpoint http://127.0.0.1:8080
python tools/global_agent_network.py install-check local_viper_control tiny_sidecar
python tools/global_agent_network.py install-check local_viper_control heavy_model_node
```

The live public GUI tunnel currently points to:

```text
https://rendering-beam-openings-madrid.trycloudflare.com
```

The Java SDK suite can get its own tunnel later with:

```powershell
.\java_notes_suite\START_NOTES_SUITE.ps1
.\java_notes_suite\START_NOTES_TUNNEL.ps1
```

The persistent Java SDK/lab surface runs separately:

```powershell
.\java_notes_suite\START_LAB_SUITE.ps1
```

```text
http://127.0.0.1:18181
```
