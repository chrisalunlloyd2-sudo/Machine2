VIPER ASCII MODIFICATION LEDGER
================================

Checkpoint begins here: 2026-05-07 user request for retrieval agent,
Fabric lens crafter, chat/planning/build routing, and long-question repair.

+----------------------+        +---------------------+        +------------------+
| messy user ask       | -----> | retrieval chooser   | -----> | one chat lens    |
| chat / plan / build  |        | db + local fabric   |        | token budget     |
+----------+-----------+        +----------+----------+        +---------+--------+
           |                               |                             |
           v                               v                             v
   straight chat path              Karoo proposal path            House response
   no Karoo mutation               slow, logged, gated            fallback safe

Modification 0001
-----------------
Intent:
  Start append-only visual ledger for every modification from this checkpoint.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Documentation only. No GUI/backend behavior change.

Modification 2026-05-09-REAL-TINY
----------------------------------
Intent:
  Promote the retrieval/chooser layer from deterministic templates to real
  local tiny GGUF models while keeping the GUI locked.

Flow:

  +--------------------+
  | USER ASK           |
  +---------+----------+
            |
            v
  +--------------------+       +----------------------+
  | DB RETRIEVAL       | ----> | SmolLM2 50w match   |
  +---------+----------+       +----------+-----------+
            |                             |
            v                             v
  +--------------------+       +----------------------+
  | Qwen active lens   | ----> | Qwen triplet card    |
  +---------+----------+       +----------+-----------+
            |                             |
            +-------------+---------------+
                          v
           Karoo proposal / House response / logs

Highlighted proposed changes:

  >>> EPOCH_REAL_TINY_CHOOSER :: Qwen writes the active lens. <<<
  >>> EPOCH_AXIOMATIC_RETRIEVAL_MATCHER :: SmolLM2 selects closest DB axiom. <<<
  >>> EPOCH_NAS_AGENT_SPINUP_SYNC :: scripts stage nodes and NAS links. <<<

Modification 0002
-----------------
Intent:
  Add a data retrieval agent and Fabric lens crafter. It classifies each ask as
  chat, planning, or build; searches local logic tables for high-probability
  matches; sets a token budget; and logs one lens per chat turn.

+-------------+     +--------------+     +--------------+
| user ask    | --> | db retrieval | --> | fabric lens  |
+------+------+     +------+-------+     +------+-------+
       |                   |                    |
       v                   v                    v
 chat / planning / build   source hashes        model context

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\data_retrieval_lens_agent.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Additive sidecar only. No GUI visual changes.

Modification 0003
-----------------
Intent:
  Wire the live chat backend to use one retrieval/Fabric lens per ask and fail
  gracefully when the local model times out on long questions.

+------------------+     +----------------+     +------------------+
| /api/loibi/predict | -> | active lens    | -> | house model call |
+---------+--------+     +--------+-------+     +--------+---------+
          |                       |                      |
          v                       v                      v
  timeout-safe response     route + token limit     logged chat memory

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Behavior:
  - chat: direct response, no Karoo.
  - planning: Karoo epoch request is logged, proposal-only.
  - build: Karoo epoch request is logged with 20-loop genetic contract,
    proposal-only unless the hard auto-advance gate is met.

Risk:
  Backend behavior change only. GUI visuals unchanged.

Modification 0004
-----------------
Intent:
  Make bridge paths absolute so the retrieval lens and locked GUI file resolve
  correctly no matter which directory starts the server.

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Stability fix. No visual changes.

Modification 0005
-----------------
Intent:
  Reduce prompt bulk for speed and local model stability. The system still
  stores/retrieves last 25 chats and DB matches, but only compact memory and a
  minimal chat lens are injected into straight chat.

+----------------+     +------------------+
| full DB search | --> | logged in SQLite |
+-------+--------+     +---------+--------+
        |                        |
        v                        v
 compact active lens      small local prompt

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\data_retrieval_lens_agent.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Speed/stability tuning. No GUI visual changes.

Modification 0006
-----------------
Intent:
  Cap user-facing model wait time so long questions return a fallback instead
  of leaving the webpage in a loading state.

+-------+----------+
| route | max wait |
+-------+----------+
| chat  | 20 sec   |
| plan  | 35 sec   |
| build | 45 sec   |
+-------+----------+

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Responsiveness fix. Slow work is still logged for proposal-side follow-up.

Modification 0007
-----------------
Intent:
  Repair the root cause of chat stalls in the house inference service. The
  service was single-threaded, so one slow generation blocked health checks and
  later chat requests. It now uses a threaded server, exposes /health, uses an
  absolute DB path, and caps prompt payload size before llama-cpp.

+----------------+       +---------------------+
| bridge request | ----> | threaded house      |
+----------------+       +----------+----------+
                              |
                              v
                       one slow call no longer
                       blocks health/chat checks

Files:
  - C:\Users\viper\house_inference_engine.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  House sidecar stability fix. GUI and Java files untouched.

Modification 0008
-----------------
Intent:
  Lower token budgets so local chat has a better chance of producing a real
  answer before the user-facing timeout.

+----------+-----------+
| route    | tokens    |
+----------+-----------+
| chat     | 160-224   |
| planning | 512-768   |
| build    | 768-1024  |
+----------+-----------+

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\data_retrieval_lens_agent.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Speed tuning. Detailed build/planning context remains logged in DB.

Modification 0009
-----------------
Intent:
  Add a fast house health precheck in the bridge. If the house model process is
  down, wedged, or refusing connections, chat immediately returns a logged lens
  fallback instead of blocking.

+---------+       +---------------+       +----------------+
| chat    | ----> | /health check | ----> | model or safe  |
| request |       | 1-2 seconds   |       | fallback       |
+---------+       +---------------+       +----------------+

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Responsiveness guard. No GUI visual changes.

Modification 0010
-----------------
Intent:
  Remove emoji startup/status prints from the house inference sidecar so Windows
  cp1252 console redirection does not crash the process before it binds port
  11435.

Files:
  - C:\Users\viper\house_inference_engine.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Logging-only stability fix. No GUI visual changes.

Modification 0011
-----------------
Intent:
  Fix indentation/import cleanup after converting house inference to threaded
  mode.

Files:
  - C:\Users\viper\house_inference_engine.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Syntax fix only.

Modification 0012
-----------------
Intent:
  Inject a smaller active memory window into the local model while preserving
  the full last-25 chat store in SQLite.

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Prompt-size stability fix. Stored memory is unchanged.

Modification 0013
-----------------
Intent:
  Avoid the llama-cpp Gemma/SWA context assertion seen during bridge prompts by
  matching the model context to 8192 and reducing active bridge prompt caps.

+-------------+---------------+
| chat prompt | 900 chars max |
| plan/build  | 1800 chars    |
| llama ctx   | 8192          |
+-------------+---------------+

Files:
  - C:\Users\viper\house_inference_engine.py
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Model stability tuning. If memory pressure appears, lower n_ctx later.

Modification 0014
-----------------
Intent:
  Document the retrieval/lens architecture, long-chat stall repair, and current
  house sidecar risk in the project docs and snapshot.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\PROJECT_SNAPSHOT_ASCII.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Documentation only.

Modification 0015
-----------------
Intent:
  Protect straight chat from llama-cpp crashes by logging the retrieval lens in
  SQLite but sending only a tiny direct-chat system prompt to the model. Karoo
  and larger lenses stay reserved for planning/build.

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Stability tradeoff: chat uses logged retrieval, not injected retrieval bulk.

Modification 0016
-----------------
Intent:
  Add the scoped cloud-agent ask rule for local agents that need outside help.
  Cloud responses are advisory and must return through proof/Karoo gates.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\RESOURCE_NETWORK_PROTOCOL.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Documentation/protocol only.

Modification 0017
-----------------
Intent:
  Add visible-rationale contract, predictive prefetch, user topology profile,
  and backend benchmark tables/endpoints. User topology updates every 5 stored
  chats as a condensed chooser reference.

+----------------+     +------------------+     +----------------+
| first 3 words  | --> | predictive route | --> | lens + benches |
+----------------+     +------------------+     +----------------+
        |                         |
        v                         v
 USER_TOPOLOGY_PROFILE     PREDICTIVE_PREFETCH_LOG

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Backend/control-plane only. Hidden chain-of-thought is not exposed; visible
  rationale is logged as the safe reasoning surface.

Modification 0018
-----------------
Intent:
  Add a separate Java Lab Suite GUI for testing, training, AB tests, quick
  settings, benchmark views, topology views, prefetch checks, and health checks.

+-------------------+        +------------------+
| Java Lab Suite    | -----> | Bridge endpoints |
| port 18181        |        | 8080 / 11435     |
+-------------------+        +------------------+

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\src\com\viper\notes\ViperLabSuiteServer.java
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\START_LAB_SUITE.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Separate suite only. Locked main GUI untouched.

Modification 0019
-----------------
Intent:
  Tune predictive prefetch so early build/fix/code words override generic
  "can you" phrasing, and seed USER_TOPOLOGY_PROFILE on read when it is empty.

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Routing/profile tuning only.

Modification 0020
-----------------
Intent:
  Make chooser token budgets generous and turn Fabric into a dynamic per-request
  template with database hooks, successful-code hooks, webcrawl research queue,
  and logical noise reduction policy.

+----------------+     +----------------------+     +----------------+
| ask            | --> | dynamic fabric       | --> | reduced model  |
| chat/plan/build|     | hooks + token budget |     | context        |
+----------------+     +----------+-----------+     +----------------+
                              |
                              v
                CODE_BLOCKCHAIN_DB / LEDGER / KAROO

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\data_retrieval_lens_agent.py
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Chooser behavior change. Planning/build can use larger contexts; chat remains
  protected by the small prompt path.

Modification 0021
-----------------
Intent:
  Document the future 12-agent rolling recursive development team SOP, GitHub
  checkpoint, README writeup, pingback, and OneDrive slow data pipeline.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\AGENT_APP_DEV_PROTOCOL.md
  - C:\Users\viper\VIPER_JAVA_RISC\RESOURCE_NETWORK_PROTOCOL.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\PROJECT_SNAPSHOT_ASCII.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  SOP/documentation only. Not self-executing.

Modification 0022
-----------------
Intent:
  Tighten successful-code retrieval so LOGIC_BLOCKCHAIN_QUEUE contributes only
  rows with status='shipped' when labeled as shipped success.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\data_retrieval_lens_agent.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Retrieval precision fix.

Modification 0023
-----------------
Intent:
  Make the house llama-cpp sidecar more robust and advanced with route-aware
  prompt packing, token budgets, serial llama access, generation retry ladder,
  health/config metadata, and richer generation meta.

+---------------+      +--------------------+      +----------------+
| bridge route  | ---> | house prompt packer| ---> | llama retry    |
| chat/plan/build|     | token-aware trim   |      | 512/256/128    |
+---------------+      +--------------------+      +----------------+

Files:
  - C:\Users\viper\house_inference_engine.py
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Inference robustness upgrade. If memory pressure appears, lower
  VIPER_HOUSE_N_CTX or route input budgets.

Modification 0024
-----------------
Intent:
  Split generous chooser token budgets from synchronous live reply budgets.
  Build/planning lenses can stay large, while immediate chat replies are capped
  so the bridge does not wait forever for long generations.

+----------------+      +----------------+
| chooser budget |      | live reply cap |
| build: 4096+   | ---> | build: 512     |
+----------------+      +----------------+

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Latency tuning. Full build detail remains in lens/DB, not in the first reply.

Modification 0025
-----------------
Intent:
  Make build routes non-blocking for the live chat. The chooser still creates
  generous dynamic Fabric lenses, successful-code pulls, Karoo epoch requests,
  and webcrawl queues, but the bridge no longer waits for a long local model
  generation before replying.

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Intentional async/proposal behavior for build requests.

Modification 0026
-----------------
Intent:
  Correct the 15-word behavior: compact 15-word cards stay internal for Fabric,
  DB summaries, and tiny prompt-engineer handoff, but visible chat replies are
  no longer clipped unless an explicit emergency flag is enabled.

+------------------+      +-------------------+
| tiny lens cards  | ---> | big local context |
| 15 words each    |      | full reply output |
+------------------+      +-------------------+

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Safer reply headroom. Internal summaries remain bounded.

Modification 0027
-----------------
Intent:
  Add additive operational tables and hooks for the notes keyword, viper laptop
  log archival queue, Karoo optimization shipment logging, dislike/cutoff repair
  loops, ACL broadcasts, and an 8-agent five-minute heartbeat circle plan.

+--------+     +--------+     +--------+     +--------+
| node 1 | --> | node 2 | --> | node 3 | --> | node 4 |
+--------+     +--------+     +--------+     +--------+
     ^                                      |
     |                                      v
+--------+     +--------+     +--------+     +--------+
| node 8 | <-- | node 7 | <-- | node 6 | <-- | node 5 |
+--------+     +--------+     +--------+     +--------+

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Queue/log only. No file deletion, no database mutation beyond additive queue
  inserts, no external shipping without an explicit shipper consuming the queue.

Modification 0028
-----------------
Intent:
  Tighten passive security sentinel fingerprinting so repeated local endpoint
  errors are collapsed by endpoint/status/source instead of logged once per
  timestamp.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\security_sentinel.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Reduces noisy repeat investigations while still recording new paths, peers,
  ports, and statuses.

Modification 0029
-----------------
Intent:
  Raise live reply headroom after cutoff testing: chat now has a larger reply
  token cap and planning may run longer before fallback. Build remains
  proposal/async so application work does not freeze the GUI.

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Longer planning calls can occupy the bridge longer; this is intentional for
  long-form asks, with build still protected by the lens queue.

Modification 0030
-----------------
Intent:
  Move notes and log-archive queueing to the front of chat request handling so
  operational broadcasts are recorded immediately even if a long planning model
  generation continues afterward.

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Notes/log hooks may queue before the final reply exists; the queue records a
  pending reply card and keeps the operational signal from being blocked.

Modification 0031
-----------------
Intent:
  Document that 15-word summaries are internal lens cards, not output caps, and
  record the 8-node heartbeat circle as a coordination map.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Documentation only.

Modification 0032
-----------------
Intent:
  Replace the basic Java lab scaffold with a persistent VS Code-like Java SDK
  surface. The suite now has Java-only endpoints for state, settings, system
  tests, AB tests, training logs, Loihi experiment logs, log tails, service
  probes, and design metadata.

+-------------------+      +--------------------------+
| Java SDK :18181   | ---> | java_notes_suite/data    |
| VS Code-like UI   |      | JSON + append JSONL      |
+-------------------+      +--------------------------+
        |
        v
+-------------------+      +--------------------------+
| service probes    | ---> | bridge / house / shipper |
+-------------------+      +--------------------------+

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\src\com\viper\notes\ViperLabSuiteServer.java
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Additive Java suite. Locked main GUI files are not edited.

Modification 0033
-----------------
Intent:
  Add a durable design document for Java SDK persistence, Loihi/Lava sidecar
  experiments, Fabric 15-word internal cards, Karoo promotion gates, and the
  scientific-method testing rule.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\JAVA_SDK_PERSISTENCE_DESIGN.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Documentation only.

Modification 0034
-----------------
Intent:
  Add visible training controls to the Java SDK UI and document the complete
  option groups: service watch, logs, settings, tests, AB, training, Loihi,
  network/agents, notes/archive, and security.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\src\com\viper\notes\ViperLabSuiteServer.java
  - C:\Users\viper\VIPER_JAVA_RISC\JAVA_SDK_PERSISTENCE_DESIGN.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Additive UI/control expansion in the separate Java SDK only.

Modification 0035
-----------------
Intent:
  Install a local project-scoped Eclipse Temurin JDK 21 runtime and update the
  Java SDK launcher to prefer it before system PATH. This lets the Java test
  suite compile/run without requiring a global Windows Java install.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\.runtime\jdk21\
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\START_LAB_SUITE.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Local runtime install only. System PATH and locked GUI files are untouched.

Modification 0036
-----------------
Intent:
  Fix the TRIPLET `PASS.` collapse. Root cause was bridge chat routing plus a
  terse chat system prompt: the raw abliterated house model produced a useful
  planning response, while the bridge chat prompt produced `PASS.`. Add
  misspelled architecture/chain terms to planning detection, strengthen the
  chat prompt against verdict-only replies, and add a thin-response repair pass
  that retries through planning when answers like `PASS.` appear.

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\data_retrieval_lens_agent.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Longer retry path only when a response is clearly too thin. No GUI changes.

Modification 0037
-----------------
Intent:
  Upgrade retrieval from loose keyword rows to a purpose-first evidence epoch
  based on RAG/Self-RAG/RAGAS-style patterns: query variants, hybrid local DB
  retrieval, source trust, route fit, compound rerank, 15-word evidence cards,
  sufficiency checks, and web snippet plans.

+---------+     +----------+     +---------+     +--------------+
| PURPOSE | --> | DB cards | --> | web snip| --> | task direction|
+---------+     +----------+     +---------+     +--------------+

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\data_retrieval_lens_agent.py
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\RAG_RETRIEVAL_UPGRADE_NOTES.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  More lens context is sent to chat. The lens is compressed and card-based to
  limit noise.

Modification 0038
-----------------
Intent:
  Merge the researched systems into the winning VIPER retrieval epoch:
  RAG explicit memory, Self-RAG adaptive retrieve/critique, RAGAS/ARES eval
  dimensions, Google GenAI DB Retrieval App's separate retrieval service/API
  pattern, and VIPER SHA/topological/Java SDK persistence.

+----------+    +------------+    +-------------+    +----------+
| classify | -> | retrieve API| -> | evidence card| -> | act/test |
+----------+    +------------+    +-------------+    +----------+

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\data_retrieval_lens_agent.py
  - C:\Users\viper\VIPER_JAVA_RISC\RAG_RETRIEVAL_UPGRADE_NOTES.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Lens logic upgrade only. Cloud/vector retrieval remains a future layer behind
  the same API shape.

Modification 0039
-----------------
Intent:
  Split tiny prompt engineering from abliterated generation. Tiny now writes a
  roughly 50-word instruction card for the active lens, while the abliterated
  local model remains uncapped for useful output. Compare/winner/merge/genetic
  upgrade language is routed toward planning instead of plain chat.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\data_retrieval_lens_agent.py
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Better routing and prompt targeting. No output cap is added to abliterated.

Modification 0040
-----------------
Intent:
  Fix repeated-ask ID collisions in the retrieval lens agent and add a quality
  guard for compare/winner prompts. The bridge now treats task echoes as failed
  compare answers and retries through the planning repair path.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\data_retrieval_lens_agent.py
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Compare/winner prompts may take longer because failed generic answers get one
  repair attempt.

Modification 0041
-----------------
Intent:
  Tighten compare/winner repair so the selected winner is the merged VIPER
  retrieval epoch, not a single vendor. The target winner is explicitly
  VIPER_GenAI_DB_Retrieval_Epoch: Google-style retrieval service/API plus
  RAG/Self-RAG/RAGAS evaluation plus VIPER DB/SHA/Karoo/Java SDK persistence.

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Compare answers are more opinionated toward the merged local architecture,
  which matches the user's requested system design.

Modification 0042
-----------------
Intent:
  Add persistent Java SDK benchmark graphs and honest recursive-training epoch
  logging. The system can now capture bridge/house/shipper latency snapshots,
  graph them, and log recursive training proposals with SHA-256 proof. It does
  not claim to mutate model weights yet.

+-------------+     +-------------+     +---------------+
| capture ms  | --> | graph trend | --> | epoch proposal |
+-------------+     +-------------+     +---------------+
        |                    |                    |
        v                    v                    v
+---------------+    +----------------+   +------------------+
| benchmark log |    | service counts |   | promotion gate   |
+---------------+    +----------------+   +------------------+

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\src\com\viper\notes\ViperLabSuiteServer.java
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\JAVA_SDK_PERSISTENCE_DESIGN.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Read/append SDK telemetry only. Main GUI remains untouched.

Modification 0043
-----------------
Intent:
  Add ASCII logic cube flows to the Java SDK persistence design. This documents
  how purpose cards, real DB retrieval, web/research cards, Karoo proposals,
  benchmark proof, SHA-256 logging, and future Loihi topology fit into one
  coordinate model.

                         z: top-code family
                              ^
                              |
                 +------------+------------+
                /|           /|           /|
               / |          / |          / |
              +------------+------------+  |
              |  |         |  |         |  |
              |  +---------|--+---------|--+--> x: code / logic coordinate
              | /          | /          | /
              |/           |/           |/
              +------------+------------+
             /
            v
  y: weight / amplitude / polarity

+----------+   +----------+   +----------+   +----------+
| purpose  |-->| retrieve |-->| lens     |-->| route    |
+----------+   +----------+   +----------+   +----------+
                                                |
                                                v
+----------+   +----------+   +----------+   +----------+
| benchmark|<--| Karoo    |<--| answer   |<--| task     |
+----------+   +----------+   +----------+   +----------+

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\JAVA_SDK_PERSISTENCE_DESIGN.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Documentation-only. No runtime or GUI changes.

Modification 0044
-----------------
Intent:
  Add an always-waiting ASCII epoch proposal queue to the Java SDK. Each queued
  epoch can target chooser, DB retrieval, Karoo, abliterated, Loihi, Lava, SOAP,
  ledger, network, or Java SDK variables. Copilot/Gemini/cloud agents are
  modeled as optional judge slots that weigh proposals, while local benchmarks
  and SHA-256 proof remain the promotion authority.

+------------+   +------------+   +------------+   +-------------+
| subsystem  |-->| quick var  |-->| judge slot |-->| ascii cube  |
+------------+   +------------+   +------------+   +-------------+
       |                                                   |
       v                                                   v
+------------+   +------------+   +------------+   +-------------+
| wait queue |-->| benchmark  |-->| compare    |-->| promote/no  |
+------------+   +------------+   +------------+   +-------------+

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\src\com\viper\notes\ViperLabSuiteServer.java
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\JAVA_SDK_PERSISTENCE_DESIGN.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Append-only proposal queue. External judge hooks are placeholders until a
  real API connector/token is configured.

Modification 0045
-----------------
Intent:
  Add standalone Java desktop packaging and an APK-ready Android skeleton for
  the same VIPER SDK control surface. The desktop app starts or reuses the Java
  SDK server and provides quick controls. The APK skeleton is a themed WebView
  shell that can point at phone, LAN, Cloudflare, or tunnel SDK endpoints.

+--------------+     +----------------+     +-------------------+
| desktop jar  | --> | SDK server      | --> | logs / benchmarks |
+--------------+     +----------------+     +-------------------+
        |
        v
+--------------+     +----------------+     +-------------------+
| APK shell    | --> | SDK URL         | --> | same control API  |
+--------------+     +----------------+     +-------------------+

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\src\com\viper\notes\ViperLabSuiteApp.java
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\BUILD_STANDALONE_APP.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\RUN_STANDALONE_APP.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\android_apk_skeleton\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\android_apk_skeleton\settings.gradle
  - C:\Users\viper\VIPER_JAVA_RISC\android_apk_skeleton\build.gradle
  - C:\Users\viper\VIPER_JAVA_RISC\android_apk_skeleton\app\build.gradle
  - C:\Users\viper\VIPER_JAVA_RISC\android_apk_skeleton\app\src\main\AndroidManifest.xml
  - C:\Users\viper\VIPER_JAVA_RISC\android_apk_skeleton\app\src\main\java\com\viper\sdk\MainActivity.java
  - C:\Users\viper\VIPER_JAVA_RISC\android_apk_skeleton\app\src\main\res\values\styles.xml
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\JAVA_SDK_PERSISTENCE_DESIGN.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  APK is a skeleton, not a compiled artifact yet. Android backend embedding is a
  later phase; current APK shell connects to an SDK endpoint.

Modification 0046
-----------------
Intent:
  Add visible versioning and VS Code-like proposed-change diagrams to ASCII
  epoch upgrades. Epoch proposals now show SDK version, highlighted subsystem,
  quick-edit variable, judge slot, and the before/proposal/benchmark flow.

+----------------+     +----------------+     +----------------+
| SDK version    | --> | proposed epoch | --> | highlighted    |
| 0.2.0          |     | diagram        |     | changed vars   |
+----------------+     +----------------+     +----------------+

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\src\com\viper\notes\ViperLabSuiteServer.java
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\src\com\viper\notes\ViperLabSuiteApp.java
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\JAVA_SDK_PERSISTENCE_DESIGN.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  UI/documentation enhancement only. Main GUI remains untouched.

Modification 0047
-----------------
Intent:
  Checkpoint the system and add an evidence-based epoch upgrade proof analyzer.
  The analyzer reads live bridge benchmarks, house health, shipper health,
  shipper log tails, and topology loop tails, then emits concrete surgical
  proposals with highlighted changes and acceptance tests.

Checkpoint:
  C:\Users\viper\VIPER_JAVA_RISC_CHECKPOINTS\VIPER_JAVA_RISC_checkpoint_20260507_215603.zip

+----------------+     +----------------+     +----------------+
| live evidence  | --> | proposed epoch | --> | acceptance     |
| logs/health    |     | highlighted    |     | test + SHA     |
+----------------+     +----------------+     +----------------+

Concrete proof proposals:
  - EPOCH_BRIDGE_HEADROOM_REPAIR
  - EPOCH_SHIPPER_UPLINK_COMPAT
  - EPOCH_KAROO_COMPARATOR_ATTACH
  - EPOCH_SOVEREIGN_AGENT_CONTRACT

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\src\com\viper\notes\ViperLabSuiteServer.java
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\JAVA_SDK_PERSISTENCE_DESIGN.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Proposal and logging only. No subsystem code is auto-applied by the proof
  analyzer.

Modification 0048
-----------------
Intent:
  Make proposed epoch changes actually visible, restore the rolling recursive
  triplet as an approved proposal, give the local AI longer response headroom,
  and add the user-supplied inference optimization stack plus axiomatic weighted
  truth tables to the epoch upgrade system.

Version:
  0.3.0-rolling-triplet-proof

+----------------+     +----------------+     +----------------+
| tiny chooser   | --> | rolling triplet| --> | tail stitch    |
+----------------+     +----------------+     +----------------+
        |                       |                       |
        v                       v                       v
+----------------+     +----------------+     +----------------+
| highlighted UI | --> | TBD tests      | --> | SHA proof      |
+----------------+     +----------------+     +----------------+

Approved proposal additions:
  - EPOCH_ROLLING_TRIPLET_RESTORE
  - EPOCH_MISSION_DIRECTIVE_ALWAYS_ON
  - EPOCH_LONG_RESPONSE_TAIL_STITCH
  - EPOCH_INFERENCE_OPTIMIZATION_STACK
  - EPOCH_DISTRIBUTED_RESOURCE_APP
  - EPOCH_AXIOMATIC_WEIGHTED_TRUTH_TABLES

Files:
  - C:\Users\viper\risc_bridge_server.py
  - C:\Users\viper\house_inference_engine.py
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\src\com\viper\notes\ViperLabSuiteServer.java
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\src\com\viper\notes\ViperLabSuiteApp.java
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\JAVA_SDK_PERSISTENCE_DESIGN.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Bridge/house defaults require service restart to take effect. Epoch upgrade
  proposals remain approval/test gated with TBD results until measured.

Modification 0049
-----------------
Intent:
  Unblock the Karoo active-training + system-advancer automation inside sandboxed
  runs by supporting a workspace-writable sqlite DB override, while preserving
  the locked GUI and keeping all advancement outputs proposal-gated.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_karoo_active_training.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_karoo_system_advancer.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md

Risk:
  Low. Default behavior still uses the canonical DB when available; sandboxed
  runs can set `VIPER_DB_PATH` (or pass `--db` when calling python directly) to
  keep proposal-gated DB writes inside the workspace.

Modification 0050
-----------------
Intent:
  Repair post-update environment intermingling by forcing chat feedback,
  chat-route training, and the global ACL/KQML library through the same proxy
  and `VIPER_DB_PATH` shield used by the environment monitor and continue suite.

+----------------+     +----------------+     +----------------+
| user feedback  | --> | one DB path    | --> | route cards    |
+----------------+     +----------------+     +----------------+
        |                       |                       |
        v                       v                       v
+----------------+     +----------------+     +----------------+
| global ACL     | --> | env monitor    | --> | proof status   |
+----------------+     +----------------+     +----------------+

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_CHAT_FEEDBACK_ANALYZER.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_CHAT_ROUTE_TRAINER.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_GLOBAL_AGENT_NETWORK.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_chat_feedback_analyzer.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_chat_route_trainer.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\global_agent_network.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_environment_monitor.py
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md

Risk:
  Low. No GUI files, local model processes, or model weights are touched. The
  global library now reports the DB path it used so split-write failures are
  visible instead of silent. The monitor now reports stale-busy house model
  generations as routing pressure rather than restarting the model. The bridge
  source now includes a stale-busy normal-chat fast path, but it requires a
  future bridge reload before the already-running process can use it.

Modification 0051
-----------------
Intent:
  Load approved house-only stale-busy recovery, then move GUI presence chat in
  front of retrieval, tiny routing, and house generation so visible replies are
  present and natural instead of hardened diagnostic text.

+----------------+     +----------------+     +----------------+
| gui chat turn  | --> | presence route | --> | natural reply  |
+----------------+     +----------------+     +----------------+
        |                       |                       |
        v                       v                       v
+----------------+     +----------------+     +----------------+
| metadata only  | --> | no DB wait     | --> | proof probe    |
+----------------+     +----------------+     +----------------+

Files:
  - C:\Users\viper\house_inference_engine.py
  - C:\Users\viper\VIPER_JAVA_RISC\START_HOUSE_ENGINE_RECOVERY.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  House reloaded to pid 26860 with `stale_busy=false` and
  `busy_policy=reject_new_generation_while_busy`. Bridge reloaded to pid 16788.
  GUI chat probe returned 200 with response:
  "I am present in the turn. Viper chat is not pretending at presence; it is
  answering directly, with routing details kept behind the visible reply."
  Follow-up streamlined-chat probe returned 200 with a full natural response
  instead of a bare acknowledgement.

Risk:
  Medium-low. Short natural/presence GUI turns bypass synchronous DB and model
  calls by design. Longer work, Sprite, Karoo, build, and planning turns keep
  their existing routes. No GUI files or model weights were edited.

Modification 0052
-----------------
Intent:
  Close remaining recovery gaps by adding a bounded chat pedagogy verifier,
  env-shielded relay backlog repair wrapper, and durable public GUI URL
  source-of-truth file.

+----------------+     +----------------+     +----------------+
| chat probes    | --> | route proof    | --> | latest report  |
+----------------+     +----------------+     +----------------+
        |                       |                       |
        v                       v                       v
+----------------+     +----------------+     +----------------+
| relay preview  | --> | archive only   | --> | no deletion    |
+----------------+     +----------------+     +----------------+

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\CLOUDFLARE_URL.txt
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_CHAT_PEDAGOGY_VERIFY.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_RELAY_BACKLOG_REPAIR.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_chat_pedagogy_verifier.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_relay_backlog_repair.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Low. Chat verifier posts bounded GUI-chat probes and writes proof artifacts.
  Relay repair archives duplicate or stale pending rows only, never deletes
  rows, and now defaults to `VIPER_DB_PATH`/workspace DB under the wrapper.

Proof:
  `RUN_VIPER_CHAT_PEDAGOGY_VERIFY.ps1 -Json -Timeout 20` passed 4/4:
  presence, streamlined chat, micro-ok, and depth-correction pingback.
  `RUN_VIPER_RELAY_BACKLOG_REPAIR.ps1 -Json -StaleHours 12` archived
  workspace DB pending relay rows from 55 to 0 using duplicate/stale archive
  statuses, with no row deletion.

Modification 0053
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T19:35:09.7380401Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Keep the behavior-learning stream verifier stable when Cloudflare try URLs
  rotate by reading the public GUI URL from the workspace source-of-truth file,
  and ensure the wrapper clears localhost proxy trap env vars.

Top table (axioms):
  - Public GUI URL truth set:
    { CLOUDFLARE_URL.txt, DEFAULT_PUBLIC_GUI }
  - Selection axiom:
    If CLOUDFLARE_URL.txt contains a valid trycloudflare URL, prefer it.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_front_to_back_verifier.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_FRONT_TO_BACK_VERIFY.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\README.md

Risk:
  Low. No GUI edits; verifier uses the existing URL truth file and keeps a safe
  fallback default. Wrapper only changes process env vars for this run.

Modification 0054
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T19:45:26Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Record the Viper95 final-addition automation suite as a staged sidecar
  blueprint before any live implementation. This preserves the locked GUI and
  keeps database editing, model control, desktop automation, SMTP, downloads,
  and mobile sync behind proof and approval gates.

Top table (axioms):
  - Viper95 shell set:
    { desktop, databases, notes, models, downloads, Lean/EPMO, email, projects,
      todo tree, mobile sync }
  - First-version axiom:
    read-only/proposal-only before write, operate, external, or model-control.
  - Safety axiom:
    every unfinished power action is tagged `TBD`.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER95_FINAL_ADDITION_BLUEPRINT.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Low. Documentation-only change. No GUI files, databases, model processes,
  desktop hooks, SMTP profiles, or external download actions were changed.

Proof:
  Blueprint file added with `TBD` implementation state and acceptance tests for
  shell load, GUI non-mutation, DB read-only counts, notes roundtrip, model
  status, chat presence, relay backlog, SMTP draft-only behavior, desktop-hook
  dry run, and mobile read-only sync.

Modification 0055
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T19:58:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Correct the VIPER chat definition after the scripted fast path regression:
  real chat means visible output from the live house cpp / Ollama-class local
  model inference lane, not deterministic bridge text.

Top table (axioms):
  - Real chat source set:
    { house_cpp, ollama_class_local_model_inference }
  - Non-chat-output set:
    { scripts, templates, tiny canned replies, route metadata }
  - Speed optimization set:
    { DB schema fencing, route preflight, context packing, queue control,
      timeout policy, resource monitoring }

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_chat_pedagogy_verifier.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Medium. Source change only until bridge reload is explicitly approved. It
  removes scripted normal-chat impersonation from the source path, but the
  currently running bridge process may still serve the previous fast path until
  reloaded.

Proof:
  `py -3 -m py_compile system_mirrors\risc_bridge_server.py tools\viper_chat_pedagogy_verifier.py`
  completed successfully. House health reported idle after the direct model
  generation probe completed. TBD live proof requires approved bridge reload
  and a verifier pass with `model_source=house_cpp`.

Modification 0056
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T20:17:14Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Get the model ecosystem working before Viper95 by adding a live-safe real-chat
  sidecar that preserves the locked `8080` web UI while routing normal GUI chat
  to the house cpp model lane.

Top table (axioms):
  - Visible chat source:
    { house_cpp }
  - Router/tidy metadata:
    { Danube chooser, deterministic boolean route, tiny tidy when budget allows }
  - Karoo analysis rows:
    { REAL_CHAT_ROUTE_SIGNALS, CHAT_FEEDBACK_VARIABLE_SIGNALS,
      REAL_CHAT_LONG_INPUT_CHUNKS, REAL_CHAT_MARKOV_STATE }
  - Long input policy:
    hash/chunk/schema first, house model over bounded digest, Danube skipped.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_real_chat_proxy.py
  - C:\Users\viper\VIPER_JAVA_RISC\START_VIPER_REAL_CHAT_PROXY.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\public\index.html
  - C:\Users\viper\VIPER_JAVA_RISC\agent_control_web\index.html
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_chat_pedagogy_verifier.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Medium-low. The `8080` web UI process was not restarted. A refreshed browser
  tab uses the new `11436` sidecar. Existing loaded tabs may keep old JavaScript
  until refresh. The sidecar can be restarted independently.

Proof:
  - `8080`, `11435`, `11436`, `18081`, and `18181` all listened after changes.
  - Normal chat prompt returned `model_source=house_cpp`, route `house`, with
    deterministic-clear chooser and Markov continuity metadata.
  - Sprite action prompt routed to `sprite_talk` and created five Sprite packets.
  - Karoo status prompt routed to grounded bridge status.
  - Like feedback returned `status=weighted`, `weight_delta=1.0`, and DB readback
    showed one `CHAT_FEEDBACK_VARIABLE_SIGNALS` row.
  - Long input test wrote three `REAL_CHAT_LONG_INPUT_CHUNKS` rows and returned
    a `house_cpp` response from the bounded digest.

Modification 0057
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T20:25:37Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Record the new roadmap and add an offline stochastic logic skeleton before
  Viper95. The skeleton chooses among one or many layers using a safety-first
  formula, but it is not wired into live chat or automation.

Top table (axioms):
  - Roadmap:
    model ecosystem -> stochastic skeleton -> real stochastic layer -> Viper95
  - Stochastic layer set:
    { real_model_source, danube_route_choice, feedback_weight,
      markov_continuity, long_input_schema, resource_pressure, proposal_gate }
  - Safety floor:
    safety_floor < 0.70 blocks the option no matter how fast it is.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_stochastic_logic_skeleton.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_STOCHASTIC_LOGIC_SKELETON.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Low. Offline/proposal-only skeleton. No live routes, DB mutation hooks,
  GUI process, model process, Sprite queue, Karoo approval, or Viper95 surface
  was changed by the stochastic layer.

Proof:
  `py -3 -m py_compile tools\viper_stochastic_logic_skeleton.py` passed.
  `py -3 tools\viper_stochastic_logic_skeleton.py --demo` emitted a
  `TBD_skeleton_only_not_live` payload, selected among layered options, and
  blocked `scripted_chat` by safety floor.

Modification 0058
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T20:28:50Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Offload safe follow-up work to the existing Sprite DB packet path before
  Viper95. Work stays inside Sprite/Karoo proposal gates and does not create,
  delete, rename, split, or merge Sprites.

Top table (offload set):
  - SPRITE_DESKTOP_KEEPER:
    monitor 8080, 11435, 11436, 18081, 18181, route freshness, and ledgers.
  - SPRITE_AUTOMATION_FORGE:
    draft verifier/prune proposal for real-chat model ecosystem.
  - SPRITE_REPAIR_MAINTAINER:
    review real-chat proxy and stochastic skeleton failure modes.
  - SPRITE_RESEARCH_CRAWLER:
    source-card research for tiny chooser/tidy models and DB schemas.
  - SPRITE_CLIPBOARD_NLP:
    raw-content filtering schema with sticky clipboard boundary.
  - ALL:
    coordinate roadmap proof targets for model ecosystem -> stochastic -> Viper95.

Risk:
  Low. DB-backed Sprite packets only. No GUI edits, no web UI restart, no model
  restart, no external download, and no source-code promotion by Sprites.

Proof:
  `add_plutonic_talk` created 10 total packet/inbox/task rows:
  five focused packets plus five all-Sprites coordination packets. Sprite
  snapshot counts moved from 35 to 45 for `sprite_plutonic_talk_packets`,
  `sprite_main_model_inbox`, and `sprite_karoo_comm_tasks`; summary stayed
  `overall=pass` with `sprite_nodes=5` and `sprite_population_locked=1`.

Modification 0059
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T20:42:56Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add a bounded real-chat ecosystem verifier and close the DB split-brain gap
  found after the `11436` sidecar was already running with the home DB.

Top table (proof set):
  - `8080`: stayed up; web UI was not restarted.
  - `11436`: reloaded only the real-chat sidecar and now advertises the
    workspace DB path.
  - `house_cpp`: normal chat returned a real house-model answer.
  - Static routes: normal chat -> house; Sprite/Karoo/depth-fix action text
    -> bridge.
  - Feedback: verifier like signal wrote `CHAT_FEEDBACK_VARIABLE_SIGNALS`
    with `status=karoo_analysis_ready`.
  - Monitor: environment monitor now checks `11436` and flags sidecar DB
    split-brain.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_real_chat_ecosystem_verifier.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_REAL_CHAT_ECOSYSTEM_VERIFY.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\START_VIPER_REAL_CHAT_PROXY.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_real_chat_proxy.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_environment_monitor.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Low-medium. The `8080` web UI process was not restarted. The `11436` sidecar
  was restarted once, after verifying the owning command line was
  `viper_real_chat_proxy.py`, so it could pick up the workspace DB path.
  Existing old route rows remain in `C:\Users\viper\gemini_bridge.db` until a
  user-approved merge/compaction is added.

Proof:
  - `py -3 -m py_compile tools\viper_real_chat_proxy.py
    tools\viper_real_chat_ecosystem_verifier.py tools\viper_environment_monitor.py`
    passed.
  - `8080` stayed on pid `46032` before and after the `11436` sidecar restart.
  - `11436/health` returned `db_path=C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\data\gemini_bridge.db`,
    `real_chat_source=house_cpp`, and `house_ready=true`.
  - `.\RUN_VIPER_REAL_CHAT_ECOSYSTEM_VERIFY.ps1 -Json` returned `overall=pass`
    and wrote `testing_lab_reports\20260524T204112Z_real_chat_ecosystem.json`.
  - `.\RUN_VIPER_REAL_CHAT_ECOSYSTEM_VERIFY.ps1 -Json -ExerciseBridge`
    returned `overall=pass`, `bridge_route_probe.status=pass`, and wrote
    `testing_lab_reports\20260524T204136Z_real_chat_ecosystem.json`.
  - `.\RUN_VIPER_ENVIRONMENT_MONITOR.ps1 -Json -ProcessLimit 30` wrote a
    degraded monitor report because of bridge pressure, `8080` TIME_WAIT,
    migration due, and Karoo backlog, while `11436` health and DB path passed.

Modification 0060
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T20:53:49Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Reduce normal-use resource pressure without restarting protected VIPER
  services, then add a monitor rule so stale browser automation does not
  silently accumulate again.

Top table (cleanup set):
  - Closed:
    exact `chrome.exe` processes with `browser-use-user-data-dir` in the command
    line.
  - Preserved:
    `8080` bridge, `11435` house model, `11436` real-chat sidecar, `18081`
    shipper, `18181` Java lab, Codex, Edge, and user browser windows.
  - Future guard:
    environment monitor cleanup candidates include stale `browser-use` Chrome
    processes older than 12 hours.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\dynamic_articulation_triage.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_DYNAMIC_ARTICULATION_TRIAGE.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_environment_monitor.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Low-medium runtime action. Closed only old headless automation Chrome
  processes identified by their temporary `browser-use-user-data-dir` command
  line. No protected VIPER service or user browser process was stopped.

Proof:
  - `RUN_VIPER_RELAY_BACKLOG_REPAIR.ps1 -Json -DryRun -StaleHours 12`
    returned `overall=pass` with zero pending workspace relay candidates.
  - `RUN_VIPER_APPROVAL_KERNEL.ps1 --json` returned
    `ready_for_user_review_with_guards`, normal-use-only, auto-apply false.
  - `RUN_VIPER_DYNAMIC_ARTICULATION_TRIAGE.ps1 -Json -DryRun` used the
    workspace DB and found zero new low-value queued rows, so no apply was run.
  - Closed 28 stale `browser-use` Chrome processes and freed about 335.4 MB
    working set; remaining matching processes: 0.
  - Follow-up `RUN_VIPER_ENVIRONMENT_MONITOR.ps1 -Json -ProcessLimit 30`
    showed all protected listeners still healthy. Overall remained degraded
    because bridge memory, `8080` TIME_WAIT, migration due, and Karoo backlog
    remain real pressure signals.

Modification 0061
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T20:56:17Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Prune duplicated global TODO pressure without deleting data or touching
  protected GUI/model services.

Top table (archive set):
  - Table:
    `GLOBAL_TODO_QUEUE`
  - Duplicate key:
    exact `title`
  - Kept row:
    oldest open row by `created_at`, then `todo_id`
  - Archived rows:
    status set to `archived_duplicate_todo_triage`
  - Deletion:
    none

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_global_todo_backlog_repair.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_GLOBAL_TODO_BACKLOG_REPAIR.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Low. Status-only archive of exact-title duplicate TODO rows in the workspace
  DB. One oldest row remains open for each title. No row deletion, GUI edit,
  process restart, model restart, or source promotion.

Proof:
  - `py -3 -m py_compile tools\viper_global_todo_backlog_repair.py` passed.
  - Dry run found 1,214 duplicate open TODO candidates and wrote
    `testing_lab_reports\20260524T205610Z_global_todo_backlog_repair.json`.
  - Apply run archived 1,214 rows, reducing workspace `GLOBAL_TODO_QUEUE`
    status counts from `open=1259` to `open=45`,
    `archived_duplicate_todo_triage=1214`, and wrote
    `testing_lab_reports\20260524T205617Z_global_todo_backlog_repair.json`.

Modification 0062
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T21:56:18Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Reduce Karoo backlog pressure in the workspace DB without deleting rows,
  touching the locked web UI, or restarting model/bridge services.

Top table (archive set):
  - `KAROO_ACTIVE_TASKS`:
    duplicate key `objective`; active status `active_queued`; archive status
    `archived_duplicate_objective_triage`; keep oldest by `created_at`, then
    `task_id`.
  - `KAROO_DISTILLATION_QUEUE`:
    duplicate key `summary_text`; active status `queued`; archive status
    `archived_duplicate_summary_triage`; keep oldest by `created_at`, then
    `queue_id`.
  - `TOPO_APPROVAL_REPORTS`:
    duplicate key `summary`; active status `pending_user_approval`; archive
    status `archived_duplicate_summary_triage`; keep oldest by `created_at`,
    then `id`.
  - Deletion:
    none.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_karoo_backlog_repair.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_KAROO_BACKLOG_REPAIR.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Low-medium. This is a status-only archive over exact-text duplicates in the
  workspace DB. The script inspects table columns before writing optional
  fields such as `updated_at`. No rows are deleted. The locked `8080` web UI,
  house model, real-chat sidecar, shipper, and Java lab were not restarted.

Proof:
  - `py -3 -m py_compile tools\viper_karoo_backlog_repair.py` passed.
  - Dry run found 1,360 exact duplicate candidates and wrote
    `testing_lab_reports\20260524T215414Z_karoo_backlog_repair.json`.
  - Apply run archived 1,360 rows and wrote
    `testing_lab_reports\20260524T215421Z_karoo_backlog_repair.json`.
  - Workspace `KAROO_ACTIVE_TASKS` changed from `active_queued=441` to
    `active_queued=11`, `archived_duplicate_objective_triage=430`.
  - Workspace `KAROO_DISTILLATION_QUEUE` changed from `queued=935` to
    `queued=378`, `archived_duplicate_summary_triage=557`.
  - Workspace `TOPO_APPROVAL_REPORTS` changed from
    `pending_user_approval=386` to `pending_user_approval=13`,
    `archived_duplicate_summary_triage=373`.
  - `RUN_VIPER_ENVIRONMENT_MONITOR.ps1 -Json -ProcessLimit 30` kept all
    protected listeners healthy and showed workspace Karoo backlog reduced;
    overall remains degraded because RAM, bridge memory, migration due, and
    older home-DB backlog still need bounded follow-up.
  - `RUN_VIPER_APPROVAL_KERNEL.ps1 --json` returned
    `ready_for_user_review_with_guards` with DB readback pass.
  - `RUN_VIPER_REAL_CHAT_ECOSYSTEM_VERIFY.ps1 -Json -Timeout 300
    -WaitHouseSeconds 60` returned `overall=pass` with normal chat routed to
    `house_cpp` and static Sprite/Karoo/depth-fix route checks passing.
  - `RUN_VIPER_REAL_CHAT_ECOSYSTEM_VERIFY.ps1 -Json -Timeout 360
    -WaitHouseSeconds 60 -IncludeLong` returned `overall=pass`; the 8,692-char
    long-input probe chunked into 4 hash-addressed chunks and stayed on
    `house_cpp`.

Modification 0063
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T21:58:37Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Prevent the environment monitor from treating legacy home-DB backlog as active
  runtime pressure after the real-chat and verifier stack moved to the workspace
  DB.

Top table (DB role set):
  - Active runtime DB:
    `VIPER_DB_PATH`, currently
    `C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\data\gemini_bridge.db`.
  - Legacy home DB:
    `C:\Users\viper\gemini_bridge.db`.
  - Degraded backlog signal:
    `KAROO_BACKLOG_HIGH` only when the DB is the active runtime DB.
  - Info migration signal:
    `LEGACY_DB_BACKLOG_HIGH` when a non-active DB has old backlog.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_environment_monitor.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Low. Monitor classification change only. No DB mutation, GUI edit, process
  kill, web UI restart, model restart, or source promotion.

Proof:
  - `py -3 -m py_compile tools\viper_environment_monitor.py` passed.
  - Read-only home-DB duplicate probe found 506 exact Karoo duplicate candidates
    and wrote `testing_lab_reports\20260524T215743Z_karoo_backlog_repair.json`;
    no home-DB rows were modified.
  - Workspace dry-run restored `karoo_backlog_repair_latest.json` to the active
    DB state with `candidate_count=0` and wrote
    `testing_lab_reports\20260524T215759Z_karoo_backlog_repair.json`.
  - `RUN_VIPER_ENVIRONMENT_MONITOR.ps1 -Json -ProcessLimit 30` returned
    `LEGACY_DB_BACKLOG_HIGH` as `info`, while active workspace DB counts stayed
    at `KAROO_ACTIVE_TASKS active_queued=11`,
    `KAROO_DISTILLATION_QUEUE queued=378`, and
    `TOPO_APPROVAL_REPORTS pending_user_approval=13`.
  - Overall remains `degraded` from RAM, bridge memory, and pipeline migration
    due, not from active workspace Karoo backlog.

Modification 0064
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T22:00:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Fix source-side bridge/lens DB split defaults and reduce future bridge memory
  pressure from tiny GGUF model caching without restarting the locked `8080`
  web UI.

Top table (source fix set):
  - Bridge DB path:
    honor `VIPER_DB_PATH`, otherwise default to workspace
    `java_notes_suite\data\gemini_bridge.db`.
  - Lens DB path:
    honor `VIPER_DB_PATH`, otherwise default to workspace
    `java_notes_suite\data\gemini_bridge.db`.
  - Bridge readback:
    add `/api/runtime/db` for post-reload proof.
  - Tiny model cache:
    `VIPER_TINY_MAX_CACHED_MODELS=1` default; evict older cached tiny model
    instances and run `gc.collect()`.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\data_retrieval_lens_agent.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\tiny_model_runtime.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Medium pending live reload. Source compiles, but the current protected `8080`
  process was intentionally not restarted. The live bridge still returns 404 for
  `/api/runtime/db` until an approved bounded bridge reload. This preserves GUI
  uptime now and leaves live proof explicit.

Proof:
  - `py -3 -m py_compile system_mirrors\risc_bridge_server.py
    tools\data_retrieval_lens_agent.py tools\tiny_model_runtime.py
    tools\viper_environment_monitor.py` passed.
  - Import readback with `VIPER_DB_PATH` set showed
    `data_retrieval_lens_agent.DB_PATH` equals the workspace DB.
  - `tiny_model_runtime.model_status()` reported `max_cached_models=1`,
    existing tiny GGUF model files, and `cached_model_kinds=[]` without loading a
    model.
  - Live `http://127.0.0.1:8080/api/runtime/db` returned 404, confirming the
    protected bridge process has not been reloaded and this source fix is not
    yet claimed live.

Modification 0065
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T22:04:14Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add a dry-run-first bridge reload wrapper and make the monitor distinguish
  source-fixed from live-fixed bridge DB state.

Top table (bridge reload guard set):
  - Dry-run command:
    `RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1`
  - Apply command:
    `RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1 -Apply`
  - Stop gate:
    every owner of port `8080` must have `risc_bridge_server.py` in the command
    line.
  - Environment gate:
    clears proxy vars, sets `VIPER_DB_PATH` to workspace DB, and sets
    `VIPER_TINY_MAX_CACHED_MODELS=1`.
  - Post-reload proof:
    `/api/datapoints` returns 200 and `/api/runtime/db` returns 200 with the
    workspace DB path.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_environment_monitor.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Low for dry-run and monitor change. Apply mode is medium because it reloads
  the protected `8080` bridge and can briefly affect the GUI; it must be run
  only in an approved bounded reload window.

Proof:
  - `RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1` dry-run returned owner PID `46032`,
    `safe_bridge_owner=true`, `/api/datapoints` 200, and `/api/runtime/db` 404.
  - `py -3 -m py_compile tools\viper_environment_monitor.py` passed.
  - `RUN_VIPER_ENVIRONMENT_MONITOR.ps1 -Json -ProcessLimit 30` reported
    `bridge_runtime_db.status=pending_reload` and prediction
    `BRIDGE_RUNTIME_DB_READBACK_PENDING_RELOAD`, while all protected listeners
    stayed healthy.

Modification 0066
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T22:57:14Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Apply the bounded `8080` bridge reload after dry-run approval, making the
  workspace DB path and tiny-cache cap live while preserving GUI availability.

Top table (live proof set):
  - Before reload:
    PID `46032`, bridge working set about 1.2 GB, `/api/datapoints` 200,
    `/api/runtime/db` 404.
  - Reload guard:
    dry-run owner check returned `safe_bridge_owner=true` for PID `46032`.
  - After reload:
    PID `23164`, `/api/runtime/db` 200,
    `db_path=C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\data\gemini_bridge.db`,
    `active_runtime_db=true`.
  - Memory result:
    bridge working set about 60.7 MB; system RAM about 79.7% used.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Medium runtime action completed. The protected bridge was reloaded after owner
  verification. The web UI came back on `8080`; no house model, real-chat
  sidecar, shipper, Java lab, or GUI source file was restarted or edited during
  this apply step.

Proof:
  - `py -3 -m py_compile system_mirrors\risc_bridge_server.py
    tools\data_retrieval_lens_agent.py tools\tiny_model_runtime.py
    tools\viper_environment_monitor.py` passed before apply.
  - `RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1` dry-run returned owner PID `46032`,
    `safe_bridge_owner=true`, `/api/datapoints` 200, and `/api/runtime/db` 404.
  - `RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1 -Apply` exited 0; direct follow-up
    probes returned `/api/runtime/db` 200, `/api/datapoints` 200, and
    `/api/benchmarks?limit=1` 200.
  - `RUN_VIPER_ENVIRONMENT_MONITOR.ps1 -Json -ProcessLimit 30` reported
    `bridge_runtime_db.status=pass`, active workspace DB readback, PID `23164`
    on `8080`, bridge working set about 60.7 MB, and all protected listeners
    healthy.
  - `RUN_VIPER_REAL_CHAT_ECOSYSTEM_VERIFY.ps1 -Json -Timeout 300
    -WaitHouseSeconds 60` returned `overall=pass`; normal chat routed to
    `house_cpp`, Sprite/Karoo/depth-fix route checks passed, and feedback DB
    readback passed.

Modification 0067
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T23:00:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Confirm and normalize the monthly pipeline-migration watchdog so vendor
  cutovers like Gemini CLI / Code Assist to Antigravity are checked before they
  surprise the VIPER stack.

Top table (automation set):
  - Automation ID:
    `viper-monthly-migration-pipeline-watch`
  - Status:
    `ACTIVE`
  - Schedule:
    first Monday of each month at 09:00 local time.
  - Workspace:
    `C:\Users\viper\VIPER_JAVA_RISC`
  - Safety:
    proposal-only; no local model restart, no process stop, no GUI edit, no
    install, no DB mutation beyond read-only status checks, and no migration
    apply without explicit approval.

Files:
  - C:\Users\viper\.codex\automations\viper-monthly-migration-pipeline-watch\automation.toml
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Low. Schedule/config update only. No workspace process, GUI file, DB table,
  model, tool install, or migration was changed by this automation update.

Proof:
  - Existing automation file was found at
    `C:\Users\viper\.codex\automations\viper-monthly-migration-pipeline-watch\automation.toml`.
  - It was already active but used `FREQ=WEEKLY;INTERVAL=4`.
  - The app automation update changed it to
    `FREQ=MONTHLY;BYDAY=MO;BYSETPOS=1;BYHOUR=9;BYMINUTE=0;BYSECOND=0`.
  - Readback showed `status=ACTIVE`, `execution_environment=local`, and
    `cwds=["C:\Users\viper\VIPER_JAVA_RISC"]`.

Modification 0068
-----------------
Stamp:
  - timestamp_utc: 2026-05-24T23:19:08Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add a bounded OpenRouter Sprite cloud planning layer so Sprites can request
  cloud action packets without bypassing local safety gates or consuming local
  model performance.

Top table (cloud Sprite set):
  - API key handling:
    reads only `OPENROUTER_API_KEY` from the environment; no key is stored,
    printed, or written to artifacts.
  - Budget:
    shared SQLite hourly window defaults to five total OpenRouter calls across
    all Sprites.
  - Execution:
    cloud output becomes `sprite_cloud_action_packets` with
    `proposal_only_pending_user_approval`; Aider/aichat execution is disabled.
  - Sprite handoff:
    approved local flow is DB-first: action packet, plutonic Sprite inbox row,
    QA message, and Karoo communication task.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_sprite_cloud_layer.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_SPRITE_CLOUD_LAYER.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Low for the implemented state. No live OpenRouter call was made, no Aider
  command was run, no GUI file was edited, no local model was restarted, and no
  cloud suggestion can execute through this wrapper.

Proof:
  - `py -3 -m py_compile tools\viper_sprite_cloud_layer.py` passed.
  - `RUN_VIPER_SPRITE_CLOUD_LAYER.ps1 -Json -DryRun -AllSprites -Task
    "business school KPI planning for sprites"` returned `overall=pass`,
    five Sprite targets, zero used API calls, Aider available, aichat missing,
    and OpenRouter env key missing. Follow-up correction keeps dry-run from
    writing or migrating the Sprite SQLite DB.
  - `RUN_VIPER_SPRITE_CLOUD_LAYER.ps1 -Json -QueueOnly -SpriteId
    SPRITE_AUTOMATION_FORGE -Task "draft next coding action packet for Sprite
    business school KPI and aider proposal layer"` returned `overall=pass`,
    created `SPRITE_CLOUD_ACTION_1860249bcf06a105`, and notified
    `SPRITE_AUTOMATION_FORGE` through `PLUTONIC_3f9c5f15728197b7`.
  - `RUN_VIPER_SPRITE_CLOUD_LAYER.ps1 -Json -QueueOnly -AllSprites -Task
    "stage OpenRouter and Aider proposal lane for Sprite business school KPI
    coding work"` returned `overall=pass`, queued five proposal-only cloud
    lane packets, notified all five Sprites through plutonic talk, and still
    used zero API calls.

Modification 0069
-----------------
Stamp:
  - timestamp_utc: 2026-05-25T00:38:52Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Wrap Sprite cloud action packets into the existing Aider bridge structure so
  every Sprite can hand a bounded plan to Aider review without giving Aider
  execution authority.

Top table (Aider bridge set):
  - Source:
    `sprite_cloud_action_packets` rows with
    `proposal_only_pending_user_approval`.
  - Export:
    Markdown plan files under
    `C:\Users\viper\SPRITE_HOME\aider_bridge\pending`.
  - DB bridge:
    `aider_requests`, `aider_responses`, and
    `sprite_aider_bridge_exports`.
  - Execution:
    disabled. No Aider command, source edit, candidate command, commit, GUI
    edit, model restart, or API call is performed.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_sprite_aider_bridge.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_SPRITE_AIDER_BRIDGE.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Low. The bridge writes proposal plan files and DB request rows only. It does
  not invoke Aider and does not change project source files.

Proof:
  - `py -3 -m py_compile tools\viper_sprite_aider_bridge.py` passed.
  - `RUN_VIPER_SPRITE_AIDER_BRIDGE.ps1 -Json -DryRun -Limit 10` returned
    `overall=pass`, selected six pending Sprite cloud packets, and wrote no
    plan files or DB rows.
  - `RUN_VIPER_SPRITE_AIDER_BRIDGE.ps1 -Json -Export -Limit 10` returned
    `overall=pass`, exported six plan files, and created six
    `planned_for_aider_review` bridge records.
  - Aider was detected at
    `C:\Users\viper\AppData\Local\Programs\Python\Python311\Scripts\aider.EXE`,
    but execution remained `disabled_proposal_only`.

Modification 0070
-----------------
Stamp:
  - timestamp_utc: 2026-05-25T00:40:17Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add watchdog visibility for the Sprite cloud/Aider layer so cloud packets and
  Aider review plans are visible in the environment monitor and continue suite
  without creating another execution channel.

Top table (watch set):
  - Environment monitor:
    read-only `sprite_cloud_bridge` counts for pending cloud packets,
    planned Aider exports, planned Aider requests, and unexported packet count.
  - Continue suite:
    optional `-SpriteCloudCheck` runs cloud-layer dry-run and Aider-bridge
    dry-run with `--include-exported`.
  - Boundary:
    no OpenRouter calls, no Aider execution, no source edits, no GUI edits, no
    model restarts.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_environment_monitor.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_continue_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_CONTINUE_SUITE.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Low. Read-only monitor addition plus dry-run continue-suite checks. No live
  cloud call, Aider execution, process restart, or GUI mutation.

Proof:
  - `py -3 -m py_compile tools\viper_environment_monitor.py
    tools\viper_continue_suite.py tools\viper_sprite_cloud_layer.py
    tools\viper_sprite_aider_bridge.py` passed.
  - `RUN_VIPER_ENVIRONMENT_MONITOR.ps1 -Json -ProcessLimit 25` reported
    `sprite_cloud_bridge.status=pass`, `pending_action_packets=6`,
    `planned_aider_exports=6`, `planned_aider_requests=6`,
    `planned_aider_responses=6`, `unexported_pending_action_packets=0`, and
    `executes_aider=false`.
  - `RUN_VIPER_CONTINUE_SUITE.ps1 -Json -SpriteCloudCheck` returned
    `sprite_cloud_layer_dry_run.status=pass` for five Sprite targets and
    `sprite_aider_bridge_dry_run.status=pass` for six selected packets.
  - Continue-suite overall stayed `degraded` because the pre-existing
    `live_status_suite` returned degraded; the new cloud/Aider checks were not
    the degraded step.

Modification 0071
-----------------
Stamp:
  - timestamp_utc: 2026-05-25T01:34:37Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Repair the post-update runtime split-brain and route-speed regressions without
  restarting local models or mutating locked GUI files. The bridge now keeps
  direct chat questions in chat and returns deterministic planning/build route
  replies before heavy micro-router, preprompt, and Karoo fast-lane work.

Top table (route/runtime set):
  - Runtime DB:
    `tools\viper_ai_test_suite.py`, `tools\topology_sidecar.py`,
    `tools\logic_blockchain_shipper.py`, and `START_LOGIC_BLOCKCHAIN_PORT.ps1`
    prefer `VIPER_DB_PATH` and default to the writable workspace DB.
  - Bridge chat:
    `what is your role?` and similar identity/conversation questions route to
    `chat` before DB-vector micro-routing.
  - Bridge speed:
    planning/build probes use early route engines and move Karoo/proof logging
    behind the visible response.
  - Safety:
    controlled bridge reload only after `RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1`
    proves every `8080` owner is `risc_bridge_server.py`; no model restart and
    no GUI file edit.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_test_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\topology_sidecar.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\logic_blockchain_shipper.py
  - C:\Users\viper\VIPER_JAVA_RISC\START_LOGIC_BLOCKCHAIN_PORT.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Risk:
  Medium-low. Port `8080` was reloaded, but only after owner verification and
  runtime DB readback. The local model/house process was not restarted. The
  change does not replace model chat with auto replies; it fences obvious route
  decisions before expensive work and keeps proof logging asynchronous.

Proof:
  - `py -3 -m py_compile system_mirrors\risc_bridge_server.py
    tools\viper_ai_test_suite.py tools\topology_sidecar.py
    tools\logic_blockchain_shipper.py tools\viper_environment_monitor.py
    tools\viper_continue_suite.py tools\viper_sprite_cloud_layer.py
    tools\viper_sprite_aider_bridge.py` passed.
  - `RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1` dry-run proved `8080` owner was the
    expected bridge process and `active_runtime_db=true`; `-Apply` reloaded to a
    new safe owner and `/api/runtime/db` stayed on the workspace DB.
  - Exact probes passed after reload: `what is your role?` -> `chat` in about
    `3 ms`; planning probe -> `planning_early_fast_route_engine` in about
    `3.5 ms`; build probe -> `build_early_fast_route_engine` in about `35 ms`.
  - `py -3 tools\viper_ai_test_suite.py status --json --local-only` returned
    `overall=pass`, `15/15`, with no degraded or failed checks.
  - `py -3 tools\viper_ai_test_suite.py lab --section full --json --local-only`
    returned `overall=pass`, `35/35`, report
    `testing_lab_reports\20260525T013437Z_full_testing_lab_report.json`.
  - `RUN_VIPER_CONTINUE_SUITE.ps1 -Json -SpriteCloudCheck` returned
    `overall=pass`, six checks passed.
  - `RUN_VIPER_ENVIRONMENT_MONITOR.ps1 -Json -ProcessLimit 25` returned
    `sprite_cloud_bridge.status=pass`. A stale public shipper tunnel record was
    refreshed through `http://127.0.0.1:18081/api/cloudflare/status`, which
    returned `status=up`, `health_code=200`; the public GUI URL also returned
    `200`.
  - Final monitor remained `degraded` for real resource pressure:
    `RAM_HIGH`, `PORT_8080_TIME_WAIT_HIGH`, `BRIDGE_PRESSURE_HIGH`, and the
    scheduled 2026-06-18 Gemini-to-Antigravity migration watch. Top RAM owners
    were the protected house model at about `2982 MB` and the bridge at about
    `783 MB`; the local model was not restarted.
  - Secret scan `rg -n "OPENROUTER_KEY_PATTERN_REDACTED|OPENROUTER_API_KEY\s*=|api-key\s+openrouter" .`
    returned no matches.

Modification 0072
-----------------
Stamp:
  - timestamp_utc: 2026-05-25T01:53:13Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Correct the definition of real chat in the live bridge after route-speed work:
  direct chat questions must come from the house model when available, while
  Sprite language must split between action routing and social chat.

Top table (chat/Sprite route set):
  - Direct chat:
    `what is your role?` calls the live house lane and reports
    `model_source=house_cpp`; if the house lane is unavailable, the bridge
    reports `no_real_model_*` instead of substituting a scripted answer.
  - Sprite action:
    `sprite should draft...`, `plan`, `outline`, and `design` count as Sprite
    action terms and can queue proposal-only Sprite packets.
  - Sprite social:
    `I hope the sprites like me` stays `chat`; DB-vector Sprite evidence is
    kept as metadata but cannot override the social fence.
  - Safety:
    Applied through `RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1` only after owner and
    workspace DB proof. No GUI files were edited and the house model was not
    restarted.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile system_mirrors\risc_bridge_server.py` passed.
  - Controlled `8080` reload dry-run proved safe bridge owner and
    `active_runtime_db=true`; apply reloaded only the bridge.
  - Live probes after reload:
    `what is your role?` -> `chat`, `direct_chat_question`,
    `model_source=house_cpp`;
    `sprite should draft a small project plan for the GUI but do not apply it`
    -> `sprite_talk`, `sprite_program_work`;
    `I hope the sprites like me` -> `chat`, `house_cpp`.
  - `RUN_VIPER_REAL_CHAT_ECOSYSTEM_VERIFY.ps1 -Json` returned
    `overall=pass`, normal chat route `house`, `model_source=house_cpp`,
    feedback DB readback pass, and static Sprite/Karoo/depth-fix routes pass.
  - Constructed-pattern secret scan returned `secret_scan=pass`.

Modification 0073
-----------------
Stamp:
  - timestamp_utc: 2026-05-25T04:39:28Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Fix Sprite status chat so `how are sprites?` gives a real house-model reply
  first, then Sprite updates, instead of creating more Sprite packets.

Top table (Sprite chat update set):
  - Status chat:
    Sprite status/social questions route to `chat` with intent
    `sprite_status_chat`. The bridge calls the house model first and appends
    read-only Sprite counts/blips from `sprite.sqlite`.
  - Action route:
    Sprite work verbs still route to `sprite_talk` and queue proposal-only
    packets.
  - Micro-router fence:
    DB-vector Sprite evidence cannot override `sprite_social_chat` or
    `sprite_no_action_term`.
  - GUI ping:
    `public\index.html` polls `/api/sprites/chat-updates` every 30 seconds and
    appends new `SPRITE:` blips without generating packets.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\public\index.html
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_CHAT_ROUTE_CORRECTION_SOP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile system_mirrors\risc_bridge_server.py` passed.
  - Safe bridge reload dry-run proved owner `risc_bridge_server.py` and
    `active_runtime_db=true`; apply reloaded only port `8080`.
  - `GET /api/sprites/chat-updates?limit=3` returned `status=ok`,
    `read_only=true`, `sprites=5`, `queued_talk=73`, `unread_inbox=73`.
  - `how are sprites?` returned `route=chat`, `intent=sprite_status_chat`,
    `model_source=house_cpp`, `queued=false`, and Sprite counts appended after
    the model reply.
  - `sprite should draft a small project plan...` still returned
    `route=sprite_talk`, `queued=true`.
  - Public GUI URL returned HTTP `200`, and served HTML contains
    `pollSpriteChatUpdates` plus `/api/sprites/chat-updates`.
  - `RUN_VIPER_REAL_CHAT_ECOSYSTEM_VERIFY.ps1 -Json` returned
    `overall=pass`, report
    `testing_lab_reports\20260525T044751Z_real_chat_ecosystem.json`.
  - Constructed-pattern secret scan returned `secret_scan=pass`.

Modification 0074
-----------------
Stamp:
  - timestamp_utc: 2026-05-25T05:05:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Make the real-chat sidecar and Sprites cooperate on the current repair work:
  natural chat remains house-model backed, Sprite status questions show a real
  model answer first, clear fix/status routes skip wasted Danube chooser calls,
  and Sprites receive bounded work packets plus proposal-only review exports.

Top table (model ecosystem proof set):
  - Real chat:
    `RUN_VIPER_REAL_CHAT_ECOSYSTEM_VERIFY.ps1 -Json` passed after the sidecar
    reload. Normal chat returned `model_source=house_cpp`; static plain,
    Sprite-action, Karoo-action, and depth-fix route checks passed.
  - Danube chooser:
    Clear `fix`/Sprite-status routes now return `chooser_status=deterministic_clear`
    and `chooser_used=0`, leaving the tiny model for ambiguous routing.
  - Sprite status:
    `how are sprites?` returned `real_chat_proxy_route=bridge`,
    `model_source=house_cpp`, Sprite counts, and read-only blips after the
    house answer.
  - Sprite offload:
    Functionalizer queued DB-backed packets; cloud layer queued five Sprite
    planning packets without API calls; Aider bridge exported eleven
    proposal-only plans; headless automation assigned work/experiment lanes.
  - Remaining gap:
    `RUN_VIPER_CONTINUE_SUITE.ps1 -Json -SpriteCloudCheck` is still
    `degraded` because of resource/Karoo hold gates such as duplicate protected
    logic-shipper listeners and genetic/matrix proposal holds. This is not a
    normal-chat scripted-response failure.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_real_chat_proxy.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile tools\viper_real_chat_proxy.py` passed.
  - `START_VIPER_REAL_CHAT_PROXY.ps1 -Restart -Port 11436` reloaded only the
    scoped real-chat sidecar; `8080/api/datapoints` stayed healthy.
  - `You should reply in more depth fix` returned route `bridge`,
    `chooser_status=deterministic_clear`, `chooser_used=0`.
  - `how are sprites?` returned `real_chat_proxy_route=bridge`,
    `model_source=house_cpp`, `queued_talk=78`, `unread_inbox=78`,
    `qa_messages=126`.
  - `GET /api/sprites/chat-updates?limit=8` returned `status=ok`,
    `read_only=true`, and the new Sprite packet counts.
  - `tools\viper_sprite_functionalizer.py --json` returned `overall=pass` and
    moved Sprite talk/inbox/QA counts from `73/73/121` to `78/78/126`.
  - `tools\viper_sprite_cloud_layer.py --json --queue-only --all-sprites`
    returned `overall=pass`, `queued_without_api_call=5`, and preserved
    `remaining=5` API calls for the hour.
  - `tools\viper_sprite_aider_bridge.py --json --export --limit 15
    --include-exported` returned `overall=pass`, `exported=11`.
  - `tools\headless_sprite_automation.py --json` returned `overall=pass`,
    with three work Sprites and two experiment Sprites assigned.
  - `RUN_VIPER_REAL_CHAT_ECOSYSTEM_VERIFY.ps1 -Json` returned `overall=pass`,
    report `testing_lab_reports\20260525T050455Z_real_chat_ecosystem.json`.

Modification 0075
-----------------
Stamp:
  - timestamp_utc: 2026-05-25T05:10:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Start the Sprite promotion system that Viper95 will display and eventually
  manage. Promotions are internal responsibility tiers backed by KPIs and queued
  work packets; they do not grant external authority or mutate source.

Top table (Sprite promotion set):
  - Scorecard:
    `sprite_promotion_scorecards` records communication, proof, learning,
    teaching, lane ownership, and safety KPI parts for each Sprite.
  - Proposal:
    `sprite_promotion_proposals` stores Viper95-displayable promotion cards.
  - Packet:
    Each promoted Sprite receives a `promotion_board` packet in
    `sprite_plutonic_talk_packets` and `sprite_main_model_inbox`.
  - Authority:
    External authority stays unchanged. No GUI, source, OS, model, SMTP, or
    external-service power is added.
  - Automation:
    Codex automation `viper-daily-autonomous-ecosystem-advance` now includes
    `RUN_VIPER_SPRITE_PROMOTION_BOARD.ps1 -Json` and readback of tier changes.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_sprite_promotion_board.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_SPRITE_PROMOTION_BOARD.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER95_FINAL_ADDITION_BLUEPRINT.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile tools\viper_sprite_promotion_board.py` passed.
  - `RUN_VIPER_SPRITE_PROMOTION_BOARD.ps1 -Json` returned `overall=pass`,
    `sprites_scored=5`, `internal_promotions=5`,
    `external_authority_changed=false`.
  - Tier results:
    `SPRITE_AUTOMATION_FORGE=sprite_manager`,
    `SPRITE_CLIPBOARD_NLP=sprite_manager`,
    `SPRITE_DESKTOP_KEEPER=sprite_manager`,
    `SPRITE_REPAIR_MAINTAINER=sprite_manager`,
    `SPRITE_RESEARCH_CRAWLER=sprite_specialist`.
  - Readback returned `scorecards=5`, `proposals=5`, `packets=5`,
    `inbox_total=83`, `talk_total=83`.
  - `GET /api/sprites/chat-updates?limit=5` returned the five
    `PROMOTION_BOARD` packets as latest Sprite talk, with counts
    `queued_talk=83`, `unread_inbox=83`, `qa_messages=126`.
  - Report path:
    `testing_lab_reports\20260525T050928Z_sprite_promotion_board.json`.

Modification 0076
-----------------
Stamp:
  - timestamp_utc: 2026-05-25T05:15:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add the advanced Agentic Circle pattern for Sprites and tiny candidate agents:
  a max-eight rotating Lean Six Sigma handoff circle where active Sprites keep
  working together, new agents are discovered as sub-500MB GGUF shadow
  candidates, and every candidate receives pedagogy before any activation.

Top table (Agentic Circle set):
  - Max:
    `MAX_AGENTS=8`.
  - Active core:
    Existing five active Sprites occupy the first circle seats.
  - Candidate seats:
    Remaining seats are shadow model candidates only; no model download or
    activation occurs.
  - Work loop:
    Each member gets a predecessor, successor, Lean DMAIC lane, handoff turn,
    proof requirement, and proposal-only packet.
  - Pedagogy:
    Candidate models receive five onboarding lessons: safety contract, VIPER
    routing, proof packet, Lean DMAIC, and pair work.
  - Safety:
    No GUI edit, source edit, OS action, model restart, model download, SMTP, or
    external send authority is granted.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_agentic_circle.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_AGENTIC_CIRCLE.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER95_FINAL_ADDITION_BLUEPRINT.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Candidate research rows:
  - `SmolLM2-360M-Instruct Q4_K_M GGUF`: `258MB`, proposed
    `rewrite_summarize_pedagogy_agent`.
  - `H2O Danube3 500M Chat Q4_K_M GGUF`: `318MB`, proposed
    `route_chooser_critic_agent`.
  - `MiniPLM-Qwen-500M Q4_K_M GGUF`: `320MB`, proposed
    `code_pattern_review_agent`.

Proof:
  - `py -3 -m py_compile tools\viper_agentic_circle.py` passed.
  - `RUN_VIPER_AGENTIC_CIRCLE.ps1 -Json` returned `overall=pass`,
    `max_agents=8`, `active_sprites=5`, `shadow_candidates=3`,
    `eligible_model_candidates=3`, `pedagogy_cards=15`,
    `external_authority_changed=false`.
  - DB readback returned `members=8`, `turns=8`, `candidates=3`,
    `pedagogy_cards=15`, `sprite_talk_total=88`, `sprite_inbox_total=88`.
  - `GET /api/sprites/chat-updates?limit=8` returned the new
    `AGENTIC_CIRCLE` packets as latest Sprite talk.
  - Codex automation `viper-daily-autonomous-ecosystem-advance` now includes
    Agentic Circle readback and candidate onboarding status.
  - Report path:
    `testing_lab_reports\20260525T051439Z_agentic_circle.json`.

Modification 0077
-----------------
Stamp:
  - timestamp_utc: 2026-05-25T05:29:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add a no-download tiny-agent search layer so the Agentic Circle can refresh
  sub-500MB GGUF candidate rows from current Hugging Face metadata instead of
  relying only on fixed seed candidates.

Top table (tiny-agent search set):
  - Source:
    Hugging Face model metadata and model file metadata only.
  - Cap:
    Candidate GGUF file must be under `500MB`; parsed model size must be at or
    below `500M` parameters.
  - File choice:
    Search terms stay broad; GGUF files are selected after metadata inspection,
    with `Q4_K_M` preferred when present.
  - Diversity:
    Candidate selection keeps at least one Qwen/MiniPLM, one SmolLM, and one
    H2O Danube family before filling duplicate-family slots.
  - Safety:
    No model download, model activation, GUI edit, source edit, model restart,
    SMTP action, OS action, or external authority change.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_tiny_agent_search.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_TINY_AGENT_SEARCH.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_agentic_circle.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER95_FINAL_ADDITION_BLUEPRINT.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile tools\viper_tiny_agent_search.py tools\viper_agentic_circle.py`
    passed.
  - `RUN_VIPER_TINY_AGENT_SEARCH.ps1 -Json -SearchLimit 8 -MaxCandidates 8`
    returned `overall=pass`, `candidate_count=8`,
    `downloads_models=false`, `external_authority_changed=false`.
  - Tiny-agent search selected Q4-class files for:
    `mradermacher/MiniPLM-Qwen-500M-i1-GGUF`,
    `mfuntowicz/SmolLM2-360M-Instruct-Q4_K_M-GGUF`, and
    `Edge-Quant/h2o-danube3-500m-chat-Q4_K_M-GGUF`.
  - `RUN_VIPER_AGENTIC_CIRCLE.ps1 -Json` returned `overall=pass`,
    `max_agents=8`, `active_sprites=5`, `shadow_candidates=3`,
    `eligible_model_candidates=3`, `pedagogy_cards=15`,
    `external_authority_changed=false`.
  - `GET /api/sprites/chat-updates?limit=8` returned `status=ok`,
    `queued_talk=93`, `unread_inbox=93`, and the newest
    `AGENTIC_CIRCLE` packets.
  - Codex automation `viper-daily-autonomous-ecosystem-advance` now runs the
    tiny-agent metadata refresh before Agentic Circle readback.
  - Report paths:
    `testing_lab_reports\20260525T052807Z_tiny_agent_search.json`;
    `testing_lab_reports\20260525T052824Z_agentic_circle.json`.

Modification 0078
-----------------
Stamp:
  - timestamp_utc: 2026-05-25T05:36:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add a bounded Agentic Circle worker so queued Lean DMAIC turns become
  proposal-only work reports and active Sprite-visible update packets.

Top table (circle worker set):
  - Input:
    Latest `agentic_circle_turns` rows not yet represented in
    `agentic_circle_work_reports`.
  - Output:
    One DMAIC report per queued turn with issue, KPI, cause, proposal, control
    check, status, hash, and artifact path.
  - Active Sprites:
    Work reports for active Sprites are mirrored to
    `sprite_plutonic_talk_packets` and `sprite_main_model_inbox` so the chat UI
    can show visible progress.
  - Shadow candidates:
    Work reports are recorded, but shadow models are not activated and do not
    receive executable authority.
  - Safety:
    No model download, model activation, GUI edit, source edit, local model
    restart, SMTP action, OS action, or external authority change.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_agentic_circle_worker.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_AGENTIC_CIRCLE_WORKER.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER95_FINAL_ADDITION_BLUEPRINT.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile tools\viper_agentic_circle_worker.py tools\viper_tiny_agent_search.py tools\viper_agentic_circle.py`
    passed.
  - `RUN_VIPER_AGENTIC_CIRCLE_WORKER.ps1 -Json -Limit 8` returned
    `overall=pass`, `reports_created=8`, `external_authority_changed=false`,
    `downloads_models=false`, and `edits_gui_files=false`.
  - DB readback returned `reports_for_circle=8`, `sprite_talk_total=98`, and
    `sprite_inbox_total=98`.
  - `GET /api/sprites/chat-updates?limit=5` returned `status=ok` and showed the
    five latest `AGENTIC_WORK_REPORT` packets for active Sprites.
  - Codex automation `viper-daily-autonomous-ecosystem-advance` now includes
    the Agentic Circle worker and work-report count readback.
  - Report path:
    `testing_lab_reports\20260525T053543Z_agentic_circle_worker.json`.

Modification 0079
-----------------
Stamp:
  - timestamp_utc: 2026-05-25T12:55:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Make the Sprite advancement loop real by adding local-model-backed Agentic
  Circle pedagogy, visible Sprite web UI pings for fresh work reports, and a
  real local-model fallback for chat when the house lane is busy or too slow.

Top table (real Sprite/chat set):
  - Sprite worker model path:
    `RUN_VIPER_AGENTIC_CIRCLE_WORKER.ps1 -Json -ModelProvider auto`.
  - Default worker model source:
    local tiny GGUF models, not scripts and not house batch generation.
  - House policy:
    house chat remains the preferred normal-chat source when healthy, but batch
    Sprite work does not call house by default because long generations can
    stall the live chat lane.
  - Chat fallback:
    if house is busy or exceeds the chat speed gate, the real-chat proxy returns
    `model_source=local_qwen_tiny_model` instead of a scripted/no-real-answer
    reply.
  - Web UI ping:
    the GUI Sprite poller chooses the newest event across blips, talk packets,
    and model messages, so fresh `AGENTIC_WORK_REPORT` packets are visible.
  - Safety:
    no model download, model-weight mutation, GUI redesign, SMTP action, source
    auto-apply, or external authority change.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_agentic_circle_worker.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_AGENTIC_CIRCLE_WORKER.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_real_chat_proxy.py
  - C:\Users\viper\VIPER_JAVA_RISC\public\index.html
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER95_FINAL_ADDITION_BLUEPRINT.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile system_mirrors\risc_bridge_server.py tools\viper_real_chat_proxy.py tools\viper_agentic_circle_worker.py`
    passed.
  - `RUN_VIPER_AGENTIC_CIRCLE_WORKER.ps1 -Json -Limit 8 -ModelProvider auto`
    returned `overall=pass`, `reports_created=8`,
    `model_backed=true`, and `model_source=local_qwen_tiny_model`.
  - Latest worker report readback returned `sprite_talk_total=123` and
    `sprite_inbox_total=123`.
  - `GET /api/sprites/chat-updates?limit=5` returned `status=ok`,
    `queued_talk=123`, and fresh `AGENTIC_WORK_REPORT` packets containing
    `model_teach` and `model_advance` fields.
  - Browser verification of `http://127.0.0.1:8080/` showed the chat pane
    containing a visible `SPRITE:` ping for the newest
    `AGENTIC_WORK_REPORT`.
  - House was recovered from stale-busy using `START_HOUSE_ENGINE_RECOVERY.ps1`
    without restarting the web UI; `GET /health` on `11435` returned
    `busy=false`, `stale_busy=false`.
  - Real-chat proxy returned `model_source=local_qwen_tiny_model` when house was
    busy, proving fallback is real model output rather than a scripted reply.

Modification 0080
-----------------
Stamp:
  - timestamp_utc: 2026-05-25T13:20:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Reduce the real Sprite advancement latency without returning to scripted
  replies by routing Agentic Circle pedagogy through the persistent real-chat
  proxy tiny-model endpoint and shrinking generation into Qwen micro-batches.

Top table (micro-batch real-model set):
  - Persistent endpoint:
    `POST http://127.0.0.1:11436/api/tiny/generate`.
  - Worker default:
    `RUN_VIPER_AGENTIC_CIRCLE_WORKER.ps1 -Json -ModelProvider auto`.
  - Default model source:
    `local_qwen_tiny_model` through the already-running real-chat proxy.
  - Experimental speed lane:
    `-ModelProvider danube` remains explicit because H2O Danube returned
    malformed pedagogy text in local tests.
  - Repair gate:
    missing model pedagogy/advancement lines trigger targeted model repair
    generation instead of silently passing blank fields.
  - GUI boundary:
    no web UI restart, no model download, no model-weight mutation, no SMTP
    action, no source auto-apply, and no external authority change.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_agentic_circle_worker.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_real_chat_proxy.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_AGENTIC_CIRCLE_WORKER.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER95_FINAL_ADDITION_BLUEPRINT.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile tools\viper_agentic_circle_worker.py tools\viper_real_chat_proxy.py system_mirrors\risc_bridge_server.py`
    passed.
  - `POST /api/tiny/generate` on port `11436` returned
    `status=local_qwen_tiny_model` for the Qwen chooser lane.
  - Full 8-turn proof:
    `RUN_VIPER_AGENTIC_CIRCLE.ps1 -Json; RUN_VIPER_AGENTIC_CIRCLE_WORKER.ps1 -Json -Limit 8 -ModelProvider auto`
    returned `overall=pass`, `reports_created=8`,
    `model_backed=true`, `model_source=local_qwen_tiny_model`,
    `ok_chunks=3`, `total_chunks=3`, `repair_count=0`,
    `blank_model_fields=0`, and elapsed time about `35702 ms`.
  - Latest report path:
    `testing_lab_reports\20260525T131857Z_agentic_circle_worker.json`.
  - Real-chat proxy health stayed `status=ok` and `house_ready=true` during the
    worker optimization.

Modification 0081
-----------------
Stamp:
  - timestamp_utc: 2026-05-26T00:18:57Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Create a docs backup checkpoint after the real-chat/Sprite worker integration
  so future agents can restore or compare the current state without guessing.

Top table (backup checkpoint set):
  - Checkpoint ID:
    `DOCS_BACKUP_CHECKPOINT_20260526T001856Z`.
  - Checkpoint path:
    `C:\Users\viper\VIPER_JAVA_RISC\docs\backup_checkpoints\DOCS_BACKUP_CHECKPOINT_20260526T001856Z`.
  - Manifest:
    `C:\Users\viper\VIPER_JAVA_RISC\docs\backup_checkpoints\DOCS_BACKUP_CHECKPOINT_20260526T001856Z\manifest.json`.
  - Manifest SHA-256:
    `bfeceeaa675fe6038aca1458f471dea15315f8ab3f1a6243ba32d87cd044487f`.
  - Copied files:
    `55`.
  - Policy:
    read-back reference only; restore requires explicit target confirmation.
    GUI surfaces remain locked and Karoo/Sprite authority changes remain
    proposal-only.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\docs\BACKUP_CHECKPOINTS.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\backup_checkpoints\DOCS_BACKUP_CHECKPOINT_20260526T001856Z\manifest.json

Proof:
  - The checkpoint directory was created and populated.
  - The manifest reports `copied_count=55`.
  - `Get-FileHash` on the manifest returned
    `BFECEEAA675FE6038ACA1458F471DEA15315F8AB3F1A6243BA32D87CD044487F`.
  - `docs\BACKUP_CHECKPOINTS.md` now indexes the checkpoint and restore rule.

Modification 0082
-----------------
Stamp:
  - timestamp_utc: 2026-05-26T00:23:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Resume after the docs checkpoint by reducing live chat hangs while preserving
  real model output.

Top table (live chat speed set):
  - House speed gate:
    `VIPER_HOUSE_MAX_CHAT_SECONDS`, default `35`.
  - Fast fallback:
    real local Qwen tiny-model output, not scripted text.
  - Sprite status route:
    proxy-local fast path uses real tiny-model wording first, then appends live
    `/api/sprites/chat-updates` counts and packets.
  - Web UI:
    `8080` remains untouched; only the real-chat proxy on `11436` is reloaded.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_real_chat_proxy.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - TBD run live normal-chat and Sprite-status probes after proxy reload.

Modification 0083
-----------------
Stamp:
  - timestamp_utc: 2026-05-31T18:09:56Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Stabilize the choppy local runtime by making AI self-repair local-first,
  SLM-guided, Karoo-readable, and able to prune duplicate same-script service
  listeners.

Top table (local-first repair set):
  - Primary command:
    `.\RUN_VIPER_AI_SELF_REPAIR.ps1`.
  - Preferred bridge runtime:
    `C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py`.
  - Local service set:
    `8080`, `11435`, `18081`, `18181`.
  - SLM lane:
    local tiny chooser first, deterministic local repair guardrail second.
  - Prune lane:
    duplicate same-script Python listeners only; no broad Python kill.
  - Karoo repair packet:
    `testing_lab_reports\*_karoo_local_first_repair_packet.json`,
    `SYSTEM_TEST_LOG`, `GLOBAL_TODO_QUEUE`, and `KAROO_ACTIVE_TASKS`.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_self_repair.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_test_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\START_LOGIC_BLOCKCHAIN_PORT.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_AI_SELF_REPAIR_AUTOMATION_PLAN.md
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile tools\viper_ai_self_repair.py tools\viper_ai_test_suite.py` passed.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` restored the local-first repair artifact
    bundle and wrote `java_notes_suite\data\ai_self_repair_latest.json`.
  - Latest repair preflight reported `overall=pass`, `degraded_before=[]`,
    `unresolved_after=[]`, and `duplicates_pruned=1`.
  - Duplicate logic shipper PID `40444` was pruned; PID `51128` remained the
    only `18081` listener.
  - Live endpoints after pruning answered on `8080`, `11435`, `18081`, and
    `18181`; `/api/runtime/db` returned the workspace DB.
  - Full lab still reports `overall=fail` with `32` pass, `2` degraded, and
    `1` fail. TBD resolve `SystemSet.chat_regression_pack` plus degraded
    Karoo genetic monitor and matrix topology checks before declaring final
    full-suite pass.

Modification 0084
-----------------
Stamp:
  - timestamp_utc: 2026-05-31T18:29:19Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Stabilize the self-repair loop so it reaches homeostasis instead of carrying
  a stale prior full-lab failure into Karoo's self-referential gates.

Top table (homeostasis set):
  - No new subsystem:
    existing `.\RUN_VIPER_AI_SELF_REPAIR.ps1` remains the control command.
  - Convergence gate:
    if only `ReasoningSet.karoo_genetic_monitor` and
    `ReasoningSet.karoo_matrix_topology` are degraded, rerun those two checks
    after the fresh full-lab report exists.
  - Stale-proof guard:
    rewrite the same full-lab report with convergence evidence instead of
    creating a second competing source of truth.
  - Safety lane:
    no GUI files edited, no automatic code promotion, Karoo remains
    proposal-only.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_self_repair.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_AI_SELF_REPAIR_AUTOMATION_PLAN.md
  - C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile tools\viper_ai_self_repair.py tools\viper_ai_test_suite.py` passed.
  - Existing Darwin endpoint `POST http://127.0.0.1:18181/api/darwin-lab`
    completed `5` generations with winner `ALG_LATENCY_GUARD_SEED_G2_4_G4_4`,
    `winnerFitness=1.0`, and `winnerBeatsBaseline=true`.
  - `py -3 tools\karoo_genetic_monitor.py --once --json` returned
    `health_status=pass`, `decision_status=ready_for_user_review`, and `5/5`
    gates.
  - `py -3 tools\karoo_matrix_topology_advancer.py --once --json` returned
    `health_status=pass`, `decision_status=matrix_topology_advanced_for_review`,
    and `5/5` gates.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 35}`, report
    `testing_lab_reports\20260531T182918Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0085
-----------------
Stamp:
  - timestamp_utc: 2026-05-31T18:33:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Remove fixed visible chat autoreplies from the locked bridge runtime path.

Top table (no-autoreply chat set):
  - Micro chat:
    real tiny or house model text is attempted before fallback.
  - Fixed phrases removed:
    `Chat state is live` and `Signal received` style replies are no longer
    returned by `_local_stateful_chat_response`.
  - Failure honesty:
    if no real model text is available, the bridge reports that no real model
    answer was generated instead of pretending with a canned conversational
    answer.
  - Regression guard:
    `SystemSet.chat_regression_pack` now rejects the removed fixed phrases and
    the no-model fallback notice.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_test_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile system_mirrors\risc_bridge_server.py tools\viper_ai_self_repair.py tools\viper_ai_test_suite.py` passed.
  - `.\RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1 -Apply -WaitSeconds 60` completed
    and reloaded `8080`.
  - Live probes for `hello`, `thanks`, `what is your role?`, and
    `can you explain the current problem?` returned HTTP `200` on route `chat`
    without the removed fixed autoreply phrases.
  - `/api/runtime/db` and `/api/datapoints` returned HTTP `200` after reload.
  - After the tiny-model-first direct chat fix, `what is your role?` returned
    on route `chat` in `1672.9ms` instead of timing out near the `30s` test
    limit.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 35}`, report
    `testing_lab_reports\20260531T183849Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0086
-----------------
Stamp:
  - timestamp_utc: 2026-05-31T18:47:08Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Issue audit-only directives to external laptop/laptop-HD agents so cleaner
  systems can compare VIPER homeostasis and no-autoreply behavior without
  mutating the locked GUI or source path.

Top table (cross-laptop audit directive set):
  - Directive id:
    `CROSS_LAPTOP_AUDIT_20260531T184531Z`.
  - Packet hash:
    `df83a030cec2d0a78c9bb01ffd758fb97af087e119c99859e9c2943f79f52f51`.
  - Target agents:
    `OTHER_LAPTOP`, `LAPTOP_HD`, `ANDROID_PHONE_CLI`.
  - Existing queues used:
    `GLOBAL_AGENT_REGISTRY`, `GLOBAL_ACL_MESSAGES`, `GLOBAL_TODO_QUEUE`,
    and `RESOURCE_NETWORK_TASKS`.
  - Copy lane:
    `C:\Users\viper\OneDrive\Desktop\VIPER_NAS_SYNC_STAGING`.
  - Policy:
    audit-only first, proof required, no GUI edits, no source mutation, no broad
    process kills, proposals only for any repair.

Files / artifacts:
  - C:\Users\viper\VIPER_JAVA_RISC\testing_lab_reports\20260531T184531Z_cross_laptop_audit_directive.json
  - C:\Users\viper\OneDrive\Desktop\VIPER_NAS_SYNC_STAGING\20260531T184531Z_cross_laptop_audit_directive.json
  - C:\Users\viper\OneDrive\Desktop\VIPER_NAS_SYNC_STAGING\20260531T184531Z_CROSS_LAPTOP_AUDIT_DIRECTIVE.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `GLOBAL_AGENT_REGISTRY` contains active rows for `OTHER_LAPTOP`,
    `LAPTOP_HD`, and `ANDROID_PHONE_CLI`.
  - `GLOBAL_ACL_MESSAGES` queued:
    `ACL_20260531T184531Z_85afc3c1e8e1`,
    `ACL_20260531T184531Z_e267edf55290`, and
    `ACL_20260531T184531Z_70cdc9ed72fa`.
  - `GLOBAL_TODO_QUEUE` queued proof-required todos:
    `TODO_20260531T184531Z_b3bdf3a6cb`,
    `TODO_20260531T184531Z_5780550e2c`, and
    `TODO_20260531T184531Z_21eb4ef227`.
  - `RESOURCE_NETWORK_TASKS` opened:
    `RTASK_20260531T184531Z_f4c69d884582`,
    `RTASK_20260531T184531Z_bf4f844f6a57`, and
    `RTASK_20260531T184531Z_781ca75af613`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 35}`, report
    `testing_lab_reports\20260531T184707Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0087
-----------------
Stamp:
  - timestamp_utc: 2026-05-31T23:21:50Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Continue the cross-laptop audit handoff and tighten the no-autoreply guard
  after live tiny-model output produced generic assistant boilerplate.

Top table (next stability set):
  - Pickup cards:
    per-node `OTHER_LAPTOP`, `LAPTOP_HD`, and `ANDROID_PHONE_CLI` cards copied
    to `C:\Users\viper\OneDrive\Desktop\VIPER_NAS_SYNC_STAGING`.
  - Relay notices:
    workspace `MISSED_MESSAGE_RELAY` rows queued for each target node.
  - Autoreply guard:
    bridge visible-reply filter now rejects `what can I assist`, `always here
    to assist`, `if you need anything else`, and `let me know if you need
    anything`.
  - Regression guard:
    `SystemSet.chat_regression_pack` rejects the same assistant-boilerplate
    phrases.
  - Policy:
    no GUI edits, no source mutation by external agents, proof/proposal only.

Files / artifacts:
  - C:\Users\viper\OneDrive\Desktop\VIPER_NAS_SYNC_STAGING\20260531T231513Z_OTHER_LAPTOP_PICKUP_CARD.md
  - C:\Users\viper\OneDrive\Desktop\VIPER_NAS_SYNC_STAGING\20260531T231513Z_LAPTOP_HD_PICKUP_CARD.md
  - C:\Users\viper\OneDrive\Desktop\VIPER_NAS_SYNC_STAGING\20260531T231513Z_ANDROID_PHONE_CLI_PICKUP_CARD.md
  - C:\Users\viper\VIPER_JAVA_RISC\testing_lab_reports\20260531T231513Z_node_pickup_cards_summary.json
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_test_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - Pickup card summary wrote
    `testing_lab_reports\20260531T231513Z_node_pickup_cards_summary.json`.
  - Relay rows queued:
    `MISSED_20260531T231513Z_1e5be393c20d`,
    `MISSED_20260531T231513Z_d62d17485469`, and
    `MISSED_20260531T231513Z_de870807651c`.
  - `py -3 -m py_compile system_mirrors\risc_bridge_server.py tools\viper_ai_test_suite.py tools\viper_ai_self_repair.py` passed.
  - `.\RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1 -Apply -WaitSeconds 60` completed.
  - Live chat probes for `hello`, `thanks`, `what is your role?`, and current
    problem explanation returned HTTP `200`, route `chat`, and no banned
    autoreply hits.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 35}`, report
    `testing_lab_reports\20260531T232149Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0088
-----------------
Stamp:
  - timestamp_utc: 2026-05-31T23:39:35Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Enforce the user's "no autoreplies at all" rule by making tiny social chat
  fail closed instead of falling through to helper/service phrasing.

Top table (hard no-autoreply set):
  - Tiny social turn policy:
    one local tiny-model attempt, then empty degraded output if the visible text
    matches echo, fixed acknowledgement, service greeting, or assistant
    boilerplate.
  - Micro chat route:
    removed the `house_chat_guarded_response(... timeout_sec=35)` fallback from
    short chat paths so `hello`, `thanks`, and `ok` cannot wait on or inherit
    generic house helper text.
  - Visible-reply filter:
    now rejects `how can I assist today` / `how can I help today` variants in
    addition to the prior `what can I assist`, `what can I help`, `assist
    users`, `inquiries`, `conversation state`, and `mode active` patterns.
  - Regression guard:
    `SystemSet.chat_regression_pack` accepts empty fail-closed output for pure
    social probes while still requiring non-empty, non-boilerplate output for
    real chat questions.
  - Policy:
    no GUI edits, no new subsystem, no scripted replacement answer.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_test_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile .\system_mirrors\risc_bridge_server.py .\tools\viper_ai_test_suite.py .\tools\viper_ai_self_repair.py` passed.
  - `.\RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1 -Apply -WaitSeconds 60` completed.
  - Live probes for `hello`, `thanks`, and `ok` returned HTTP `200`, route
    `chat`, empty degraded output, and no banned autoreply hits.
  - Live probes for `what is your role?` and
    `can you explain the current problem?` returned HTTP `200`, route `chat`,
    non-empty positive output, and no banned autoreply hits.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 35}`, report
    `testing_lab_reports\20260531T233935Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0089
-----------------
Stamp:
  - timestamp_utc: 2026-06-01T00:17:55Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Remove remaining choppiness from the hard no-autoreply path by bypassing
  model generation entirely for exact social probes that should produce no
  visible reply.

Top table (exact social fast-close set):
  - Exact social set:
    `hi`, `hello`, `hey`, `yo`, `sup`, `hiya`, `howdy`, `ok`, `okay`, `nice`,
    `cool`, `great`, `thanks`, `thank you`, `sounds good`, `alright`,
    `yes please`.
  - Response rule:
    exact social turns return route `chat`, `model_source=exact_social_no_autoreply`,
    empty visible output, and `error=no_model_response_available_no_autoreply`.
  - Latency rule:
    do not invoke tiny or house generation for exact social turns.
  - Scope:
    no GUI edits, no new subsystem, no scripted replacement answer.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile .\system_mirrors\risc_bridge_server.py .\tools\viper_ai_test_suite.py .\tools\viper_ai_self_repair.py` passed.
  - `.\RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1 -Apply -WaitSeconds 60` completed.
  - Live probes returned HTTP `200`, route `chat`, empty output, no banned
    autoreply hits, and `model_source=exact_social_no_autoreply` for:
    `hello` in `22.1ms`, `thanks` in `31.5ms`, and `ok` in `36.3ms`.
  - Live problem-explanation probe returned HTTP `200`, route `chat`, positive
    non-empty output, and no banned autoreply hits in `290.1ms`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 35}`, report
    `testing_lab_reports\20260601T001755Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0090
-----------------
Stamp:
  - timestamp_utc: 2026-06-01T02:21:06Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Cut visible bridge latency for normal chat and direct status questions without
  adding a subsystem or changing locked GUI files.

Top table (performance fast-path set):
  - Exact social fast-close:
    moved exact social no-autoreply handling ahead of micro-router, DB vector
    evidence, lens crafting, tiny generation, and house generation.
  - Direct local chat:
    known direct chat answers now return before route DB scans and model calls.
  - Direct question fallback:
    if a known direct answer is unavailable, direct chat questions still try
    tiny/house generation, but the house fallback is capped at seconds instead
    of using long interactive waits.
  - Scope:
    no GUI edits, no new service, no model restart, no scripted autoreply for
    exact social turns.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile .\system_mirrors\risc_bridge_server.py .\tools\viper_ai_test_suite.py .\tools\viper_ai_self_repair.py` passed.
  - `.\RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1 -Apply -WaitSeconds 60` completed.
  - Five-probe local averages after reload:
    `hello=14.6ms`, `thanks=16.9ms`, `what is your role?=5.0ms`,
    `can you explain the current problem?=9.4ms`, route-meta chat `7.7ms`,
    planning `6.3ms`, and build `71.5ms`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 35}`, report
    `testing_lab_reports\20260601T022104Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0091
-----------------
Stamp:
  - timestamp_utc: 2026-06-01T05:03:36Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Make the autonomous agentic network continue bounded pedagogy, schema
  exchange, BM25 learning, and system advancement under an explicit CPU
  governor instead of free-running or sleeping.

Top table (always-on governed work set):
  - Work governor:
    `RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 8` runs one cycle and
    records CPU start/end plus every selected work step.
  - CPU policy:
    target at least `10%` useful work when idle; do not start heavy/model work
    at or above `80%` CPU.
  - Existing lanes reused:
    smoke testing lab, Agentic Circle, Agentic Circle worker, and Karoo active
    training are selected only through the governor and only while under cap.
  - Schema/logit exchange:
    workspace and Sprite SQLite schemas are copied into
    `AGENT_SCHEMA_EXCHANGE`; local logit exchange is represented by
    `AGENT_LOGIT_SCHEMA_EXCHANGE` as schema-only until a local model exposes
    logits.
  - BM25 learning:
    latest artifacts and schema docs are tokenized into
    `BM25_ORCHESTRATOR_LEARNING` for local-first retrieval/orchestration.
  - Recurring automation:
    existing automation `viper-daily-autonomous-ecosystem-advance` was renamed
    `VIPER always-on governed ecosystem advance` and updated to hourly.
  - Policy:
    no GUI edits, no local model restarts, no cloud/API spend, no Aider
    execution, no private export, and no source auto-apply.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_always_on_orchestrator.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_test_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md
  - C:\Users\viper\.codex\automations\viper-daily-autonomous-ecosystem-advance\automation.toml

Proof:
  - `py -3 -m py_compile .\tools\viper_always_on_orchestrator.py .\tools\viper_ai_test_suite.py .\tools\viper_agentic_circle.py .\tools\viper_agentic_circle_worker.py` passed.
  - `.\RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 8` ran three governed
    cycles. CPU sampled at or above cap, so heavy/model steps were correctly
    throttled while light schema/BM25 work continued.
  - Latest orchestrator report:
    `testing_lab_reports\20260601T050311Z_always_on_orchestrator.json`.
  - `BehaviorSet.always_on_orchestrator` passed with
    `runs=3`, `schemas=160`, `logit_schemas=1`, and `bm25_docs=128` in
    `testing_lab_reports\20260601T050336Z_behavioral_testing_lab_report.json`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 36}`, report
    `testing_lab_reports\20260601T050232Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0092
-----------------
Stamp:
  - timestamp_utc: 2026-06-01T05:11:31Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Move the governed agentic loop from proposal-only reporting toward actual
  completed work by adding a completed-work ledger for bounded safe actions.

Top table (actual work set):
  - Completed-work ledger:
    `ACTUAL_SYSTEM_WORK_LOG` records work type, command/function, evidence,
    status, timestamp, and SHA-256 for real completed actions.
  - Safe work that can complete while throttled:
    schema exchange and BM25 orchestrator refresh.
  - Safe work that can complete under CPU cap:
    compile core agent tools, smoke testing lab, Agentic Circle refresh,
    Agentic Circle worker reports, and Karoo active training.
  - Current host pressure:
    CPU sampled at `100%`, so the governor correctly refused heavy/model work
    and completed only the light safe work classes.
  - Policy:
    source mutation, GUI edits, model restarts, cloud/API spend, Aider
    execution, and private export remain gated.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_always_on_orchestrator.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_test_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md
  - C:\Users\viper\.codex\automations\viper-daily-autonomous-ecosystem-advance\automation.toml

Proof:
  - `py -3 -m py_compile .\tools\viper_always_on_orchestrator.py .\tools\viper_ai_test_suite.py` passed.
  - `.\RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 8` wrote
    `testing_lab_reports\20260601T050803Z_always_on_orchestrator.json`.
  - `ACTUAL_SYSTEM_WORK_LOG` readback returned `2` completed work rows:
    `schema_exchange` and `bm25_learning_refresh`.
  - Workspace readback returned `ALWAYS_ON_ORCHESTRATOR_RUNS=4`,
    `AGENT_SCHEMA_EXCHANGE=161`, and `BM25_ORCHESTRATOR_LEARNING=131`.
  - `py -3 .\tools\viper_ai_test_suite.py lab --section behavioral --json --local-only`
    passed with `BehaviorSet.always_on_orchestrator`, report
    `testing_lab_reports\20260601T050847Z_behavioral_testing_lab_report.json`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 36}`, report
    `testing_lab_reports\20260601T051128Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0093
-----------------
Stamp:
  - timestamp_utc: 2026-06-01T05:23:47Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Make the always-on loop more stable under host pressure and add local-first
  SLM repair state so agents can recover from offline or stale-state problems
  using local DB/report evidence before any model-heavy work.

Top table (offline repair and stability set):
  - Heavy-work buffer:
    heavy smoke/model/worker lanes now require CPU below `50%`, while the hard
    max remains `80%`.
  - DB integrity proofs:
    `DB_INTEGRITY_PROOFS` stores read-only `PRAGMA quick_check` proof rows for
    the workspace and Sprite SQLite databases.
  - Artifact hash manifest:
    `ARTIFACT_MANIFEST_INDEX` stores SHA-256, kind, status, size, and mtime
    for the freshest latest/report JSON artifacts.
  - Local-first repair state:
    `LOCAL_FIRST_REPAIR_STATE` stores the SLM-first repair order, policy locks,
    table counts, and proof pointers.
  - Completed work:
    the latest throttled cycle completed schema exchange, BM25 refresh, DB
    integrity proof, artifact manifest refresh, and local repair-state refresh.
  - Policy:
    no GUI edits, no source auto-apply, no model restart, no cloud/API spend,
    no Aider execution, and no private export.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_always_on_orchestrator.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_test_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile .\tools\viper_always_on_orchestrator.py .\tools\viper_ai_test_suite.py` passed.
  - `.\RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 8` wrote
    `testing_lab_reports\20260601T052257Z_always_on_orchestrator.json` with
    `overall=throttled`, `steps_run=0`, `actual_work_completed=5`,
    `actual_work_degraded=0`, CPU `80.0 -> 70.0`, and heavy gate `50.0`.
  - Latest local DB readback returned `ALWAYS_ON_ORCHESTRATOR_RUNS=7`,
    `AGENT_SCHEMA_EXCHANGE=164`, `AGENT_LOGIT_SCHEMA_EXCHANGE=1`,
    `BM25_ORCHESTRATOR_LEARNING=142`, `ACTUAL_SYSTEM_WORK_LOG=24`,
    completed work rows `21`, `DB_INTEGRITY_PROOFS=6`,
    `ARTIFACT_MANIFEST_INDEX=90`, and `LOCAL_FIRST_REPAIR_STATE=3`.
  - `py -3 .\tools\viper_ai_test_suite.py lab --section behavioral --json --local-only`
    passed with `BehaviorSet.always_on_orchestrator`, report
    `testing_lab_reports\20260601T052311Z_behavioral_testing_lab_report.json`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 36}`, report
    `testing_lab_reports\20260601T052347Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0094
-----------------
Stamp:
  - timestamp_utc: 2026-06-01T05:35:18Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Make choppy host pressure and degraded prior work visible to the local-first
  repair loop, without killing processes, restarting models, editing GUI files,
  or repeating heavy lanes blindly.

Top table (pressure/degradation set):
  - Host pressure snapshots:
    `HOST_PRESSURE_SNAPSHOTS` records CPU percent plus top cumulative process
    rows as observe-only evidence.
  - Degradation index:
    `DEGRADATION_EVENTS` records degraded local artifacts and degraded
    completed-work rows for repair triage.
  - Repair-state input:
    `LOCAL_FIRST_REPAIR_STATE` now includes host pressure and degradation
    evidence in the SLM-first repair order.
  - Latest pressure:
    CPU sampled at `93%`; heavy lanes stayed off because the heavy gate is
    `50%`.
  - Policy:
    observe only; no process kill, no restart, no GUI edit, no source
    auto-apply, no cloud/API spend, no private export.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_always_on_orchestrator.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_test_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile .\tools\viper_always_on_orchestrator.py .\tools\viper_ai_test_suite.py` passed.
  - `.\RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 8` wrote
    `testing_lab_reports\20260601T053432Z_always_on_orchestrator.json` with
    `overall=throttled`, `steps_run=0`, `actual_work_completed=7`,
    `actual_work_degraded=0`, CPU `93.0 -> 53.0`, and heavy gate `50.0`.
  - Latest pressure snapshot status was `high_pressure`; top cumulative process
    rows were Edge/explorer/WebView processes, recorded as evidence only.
  - `DEGRADATION_EVENTS` wrote `39` candidate events from degraded local
    artifacts/work rows for future repair triage.
  - `py -3 .\tools\viper_ai_test_suite.py lab --section behavioral --json --local-only`
    passed with `BehaviorSet.always_on_orchestrator`, report
    `testing_lab_reports\20260601T053449Z_behavioral_testing_lab_report.json`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 36}`, report
    `testing_lab_reports\20260601T053518Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0095
-----------------
Stamp:
  - timestamp_utc: 2026-06-01T05:45:50Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Convert local pressure/degradation evidence into cooldown-aware repair triage
  actions so agents know what to defer, skip, or inspect before repeating
  heavy work.

Top table (repair triage set):
  - Triage table:
    `REPAIR_TRIAGE_ACTIONS` stores source, action label, priority, status,
    cooldown, evidence, timestamp, and SHA-256.
  - Host pressure action:
    `defer_heavy_lanes_until_cpu_below_50`.
  - Orchestrator degradation action:
    `keep_heavy_gate_50_and_continue_light_repair_cycle`.
  - Worker degradation action:
    `skip_worker_until_new_circle_turns_or_cpu_below_50`.
  - Generic failed-artifact action:
    `read_artifact_manifest_and_latest_report_before_retry`.
  - Policy:
    local cooldown queue only; no process kill, no restart, no GUI edit, no
    source auto-apply, no cloud/API spend, no private export.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_always_on_orchestrator.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_test_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile .\tools\viper_always_on_orchestrator.py .\tools\viper_ai_test_suite.py` passed.
  - `.\RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 8` wrote
    `testing_lab_reports\20260601T054509Z_always_on_orchestrator.json` with
    `overall=throttled`, `steps_run=0`, `actual_work_completed=8`,
    `actual_work_degraded=0`, CPU `54.0 -> 59.0`, and heavy gate `50.0`.
  - `REPAIR_TRIAGE_ACTIONS` wrote `4` cooldown actions:
    `defer_heavy_lanes_until_cpu_below_50`,
    `keep_heavy_gate_50_and_continue_light_repair_cycle`,
    `skip_worker_until_new_circle_turns_or_cpu_below_50`, and
    `read_artifact_manifest_and_latest_report_before_retry`.
  - `py -3 .\tools\viper_ai_test_suite.py lab --section behavioral --json --local-only`
    passed with `BehaviorSet.always_on_orchestrator`, report
    `testing_lab_reports\20260601T054521Z_behavioral_testing_lab_report.json`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 36}`, report
    `testing_lab_reports\20260601T054550Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0096
-----------------
Stamp:
  - timestamp_utc: 2026-06-01T06:01:51Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Force advanced project/code work to keep moving at a bounded `5%` target
  under high host pressure, while lowering non-code maintenance first and
  preserving the no GUI/source-auto-apply locks.

Top table (forced 5 percent active packet set):
  - Heavy work gate:
    `35%` CPU start gate for smoke/model/worker lanes.
  - Max CPU rule:
    `80%` still blocks heavy lanes.
  - Minimum useful work target:
    `10%` when the host is idle.
  - Forced slow completion:
    `SLOW_COMPLETION_PACKAGES` stores active `5%` target work packages.
  - Advanced projects:
    `ADVANCED_PROJECT_QUEUE` status is `active_forced_5pct_packets`.
  - Advanced work packets:
    `ADVANCED_PROJECT_WORK_PACKETS` status is `active_proof_required`.
  - Pressure response:
    lower artifact manifest refresh to `40` and BM25/schema refresh to `60`
    before reducing code/project slow-completion work.
  - Policy:
    no process kill, no restart, no GUI edit, no source auto-apply, no
    cloud/API spend, no private export.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_always_on_orchestrator.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_test_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile .\tools\viper_always_on_orchestrator.py .\tools\viper_ai_test_suite.py` passed.
  - `.\RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 8` wrote
    `testing_lab_reports\20260601T060108Z_always_on_orchestrator.json` with
    `overall=throttled`, CPU `69.0 -> 79.0`, heavy gate `35.0`,
    forced slow-completion target `5.0`, `lowered_non_code_maintenance=true`,
    `maintenance_artifact_limit=40`, `bm25_schema_limit=60`,
    `actual_work_completed=10`, `actual_work_degraded=0`,
    `advanced_projects_written=4`, `work_packets_written=12`,
    `agent_matches_written=12`, and `slow_completion_packages_written=8`.
  - DB readback after the run showed `13` orchestrator runs, `4` active
    advanced projects, `12` active proof-required advanced packets, `17` active
    slow-completion packages, `169` schema rows, `1` logit-schema contract,
    `150` BM25 docs, `18` DB integrity proofs, `130` artifact rows, `9`
    local-first repair states, `6` host-pressure snapshots, `42` degradation
    events, `19` repair triage rows, and `77` completed actual work rows.
  - `py -3 .\tools\viper_ai_test_suite.py lab --section behavioral --json --local-only`
    passed with `BehaviorSet.always_on_orchestrator`, report
    `testing_lab_reports\20260601T060122Z_behavioral_testing_lab_report.json`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 36}`, report
    `testing_lab_reports\20260601T060151Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0097
-----------------
Stamp:
  - timestamp_utc: 2026-06-01T11:19:56Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Reduce always-on choppiness by preventing false-low CPU samples from opening
  heavy lanes, skipping unchanged cache rows, and pruning stale always-on
  package state while preserving report artifacts as proof.

Top table (stability optimization set):
  - CPU sampling:
    use multiple local Windows counters and fail closed to `100%` if sampling is
    unusable.
  - Heavy lane rule:
    unreliable CPU evidence closes heavy lanes; forced `5%` slow-completion
    packages remain active.
  - Hash-aware no-op writes:
    unchanged schema, logit contract, BM25, artifact, advanced project, match,
    packet, and slow package rows are skipped instead of rewritten.
  - Operational prune:
    non-active advanced packets, orphan project/match rows, and slow packages
    whose target packet is no longer active are deleted from queue/cache tables.
  - Proof retention:
    report JSON artifacts and actual-work rows remain the proof source.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_always_on_orchestrator.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile .\tools\viper_always_on_orchestrator.py .\tools\viper_ai_test_suite.py` passed.
  - Direct CPU sampler probe returned `100.0`, proving fail-closed behavior
    when local counters are unreliable.
  - `.\RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 8` wrote
    `testing_lab_reports\20260601T111832Z_always_on_orchestrator.json` with
    `overall=throttled`, CPU `100.0 -> 100.0`, heavy gate `35.0`,
    forced slow-completion target `5.0`, `lowered_non_code_maintenance=true`,
    `maintenance_artifact_limit=40`, `bm25_schema_limit=60`,
    `actual_work_completed=11`, and `actual_work_degraded=0`.
  - The same run skipped unchanged rows instead of rewriting them:
    `schemas_written=0`, `schemas_unchanged=160`,
    `logit_schema_written=false`, `bm25_docs_written=2`,
    `bm25_docs_unchanged=65`, `slow_completion_packages_written=0`, and
    `slow_completion_packages_unchanged=8`.
  - The same run pruned stale state:
    `stale_advanced_projects_deleted=1`, `stale_agent_matches_deleted=3`,
    `stale_advanced_packets_deleted=3`, and `stale_slow_packages_deleted=3`.
  - DB readback after the run showed `18` orchestrator runs, `4` active
    advanced projects, `12` active proof-required packets, `8` active
    slow-completion packages, `169` schema rows, `1` logit-schema contract,
    `162` BM25 docs, `28` DB integrity proofs, `197` artifact rows, `14`
    local-first repair states, `11` host-pressure snapshots, `68` degradation
    events, `34` repair triage rows, and `133` completed actual work rows.
  - `py -3 .\tools\viper_ai_test_suite.py lab --section behavioral --json --local-only`
    passed with `BehaviorSet.always_on_orchestrator`, report
    `testing_lab_reports\20260601T111849Z_behavioral_testing_lab_report.json`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 36}`, report
    `testing_lab_reports\20260601T111954Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0098
-----------------
Stamp:
  - timestamp_utc: 2026-06-02T00:57:09Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Improve CPU telemetry stability so the governor is not stuck at fail-closed
  `100%` when real process-delta evidence is available, while still preventing
  false-low samples from opening heavy lanes.

Top table (CPU sampler correction set):
  - Primary sampler:
    two short process-CPU delta windows from local `Get-Process` cumulative CPU
    totals divided by logical processor count.
  - Fallback sampler:
    Windows instant counters for processor load and processor time.
  - Zero rule:
    return `0.0` only when at least two samplers return successful zero
    evidence.
  - Fail-closed rule:
    return `100.0` only when all samplers are unusable.
  - Heavy lane rule:
    keep `35%` as the heavy-work start gate and keep forced `5%`
    slow-completion active under pressure.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_always_on_orchestrator.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile .\tools\viper_always_on_orchestrator.py .\tools\viper_ai_test_suite.py` passed.
  - Direct sampler probe returned final sampled CPU `66.0`; direct delta
    windows returned `[53.0, 0.0, 6.0]`, proving one quiet window no longer
    controls the decision.
  - `.\RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 8` wrote
    `testing_lab_reports\20260602T005550Z_always_on_orchestrator.json` with
    `overall=throttled`, CPU `65.6 -> 51.0`, heavy gate `35.0`,
    forced slow-completion target `5.0`, `lowered_non_code_maintenance=true`,
    `maintenance_artifact_limit=40`, `bm25_schema_limit=60`,
    `actual_work_completed=11`, and `actual_work_degraded=0`.
  - The same run skipped stable rows instead of rewriting them:
    `schemas_written=0`, `schemas_unchanged=160`,
    `logit_schema_written=false`, `bm25_docs_written=2`,
    `bm25_docs_unchanged=65`, `slow_completion_packages_written=0`, and
    `slow_completion_packages_unchanged=8`.
  - DB readback after the run showed `31` orchestrator runs, `4` active
    advanced projects, `12` active proof-required packets, `8` active
    slow-completion packages, `169` schema rows, `1` logit-schema contract,
    `210` BM25 docs, `54` DB integrity proofs, `433` artifact rows, `27`
    local-first repair states, `24` host-pressure snapshots, `144` degradation
    events, `64` repair triage rows, and `276` completed actual work rows.
  - `py -3 .\tools\viper_ai_test_suite.py lab --section behavioral --json --local-only`
    passed with `BehaviorSet.always_on_orchestrator`, report
    `testing_lab_reports\20260602T005636Z_behavioral_testing_lab_report.json`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 36}`, report
    `testing_lab_reports\20260602T005708Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0099
-----------------
Stamp:
  - timestamp_utc: 2026-06-02T01:08:01Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Activate Karoo's programming-first lane for local script, tool, and wrapper
  maintenance so the system can make programs and update script libraries with
  proof-backed stability/performance gates instead of broad proposals.

Top table (Karoo programming activation set):
  - `KAROO_SCRIPT_LIBRARY_TASKS`:
    active proof-required rows for tools/RUN wrappers and local script-library
    maintenance.
  - Retrieval lens:
    `KAROO_SCRIPT_LIBRARY_TASKS` is a trusted build source and receives a
    script-library intent boost only for script/library/tool/programming asks.
  - Karoo active training:
    adds `programming_script_library_main_goal` as a build-route card with DB
    readback and recall proof.
  - Karoo system advancer:
    emits `programming_script_library` ready-for-review advancements with
    compile, behavioral, self-repair, DB readback, and GUI/source locks.
  - Always-on governor:
    adds `Karoo Programming Script Library` as an active advanced project with
    three proof-required packets and forced `5%` slow-completion packages.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_karoo_active_training.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_karoo_system_advancer.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\data_retrieval_lens_agent.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_always_on_orchestrator.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile .\tools\viper_karoo_active_training.py .\tools\viper_karoo_system_advancer.py .\tools\viper_always_on_orchestrator.py .\tools\data_retrieval_lens_agent.py` passed.
  - Direct retrieval-lens probe for `Karoo update the programming script
    libraries and make tested programs from existing local tools` returned
    `route=build`, `result_count=16`, and included
    `KAROO_SCRIPT_LIBRARY_TASKS`.
  - `.\RUN_VIPER_KAROO_ACTIVE_TRAINING.ps1` wrote
    `testing_lab_reports\KAROO_ACTIVE_20260602T010556Z_fb6dc5b9_training_report.json`
    with `overall=pass`, DB readback `KAROO_SCRIPT_LIBRARY_TASKS=1`, and the
    script-library recall test hitting all required sources.
  - `.\RUN_VIPER_KAROO_SYSTEM_ADVANCER.ps1` wrote
    `testing_lab_reports\KAROO_ADVANCE_20260602T010657Z_3861a2ac_system_advancer_report.json`
    with `overall=pass`, `advancement_count=5`, and
    `programming_script_library` ready for review.
  - `.\RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 8` wrote
    `testing_lab_reports\20260602T010727Z_always_on_orchestrator.json` with
    `overall=throttled`, CPU `73.4 -> 42.7`, heavy gate `35.0`, forced
    slow-completion `5.0`, `advanced_projects_written=1`,
    `work_packets_written=3`, and `slow_completion_packages_written=3`.
  - DB readback showed `1` active `KAROO_SCRIPT_LIBRARY_TASKS` row, `1`
    `Karoo Programming Script Library` advanced project, `3` proof-required
    script-library packets, `3` active forced slow-completion packages, and
    `287` completed actual-work rows.
  - `py -3 .\tools\viper_ai_test_suite.py lab --section behavioral --json --local-only`
    passed with `BehaviorSet.always_on_orchestrator`, report
    `testing_lab_reports\20260602T010739Z_behavioral_testing_lab_report.json`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 36}`, report
    `testing_lab_reports\20260602T010801Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0100
-----------------
Stamp:
  - timestamp_utc: 2026-06-02T01:19:08Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Test and repair chat-to-agent job dispatch so explicit build/planning chat
  requests create durable proof-gated agent jobs, then become active work
  packets and forced `5%` slow-completion packages.

Top table (chat agent job dispatch set):
  - `CHAT_AGENT_JOB_QUEUE`:
    bridge-owned chat job ledger for explicit agent-job requests.
  - `GLOBAL_TODO_QUEUE`:
    linked open todo row for each chat-created job.
  - `KAROO_EPOCH_REQUESTS`:
    proposal-only Karoo epoch row for each chat job.
  - `SYSTEM_TEST_LOG`:
    `ChatAgentJobDispatch=pass` proof rows with job/todo/epoch IDs.
  - `ADVANCED_PROJECT_WORK_PACKETS`:
    always-on dispatch converts queued chat jobs into `CHATPKT_*`
    proof-required packets.
  - `SLOW_COMPLETION_PACKAGES`:
    dispatched chat packets are picked up by the forced `5%` slow-completion
    lane.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_always_on_orchestrator.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_test_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - Initial live chat test sent three `/api/loibi/predict` build-route requests
    and showed a real gap: `delta=0` for chat memory, retrieval events, Karoo
    epochs, global todos, advanced packets, and system test log.
  - `py -3 -m py_compile .\system_mirrors\risc_bridge_server.py .\tools\viper_always_on_orchestrator.py .\tools\viper_ai_test_suite.py` passed.
  - Controlled reload dry run showed port `8080` owned only by the expected
    `system_mirrors\risc_bridge_server.py` process; `-Apply` reloaded the
    bridge and probes returned `200` for `/api/datapoints` and active workspace
    DB for `/api/runtime/db`.
  - Retest with three live chat requests created `3` `CHAT_AGENT_JOB_QUEUE`
    rows, `3` queued proof-required jobs, `3` `KAROO_EPOCH_REQUESTS`, `3`
    `GLOBAL_TODO_QUEUE` rows, and `3` `SYSTEM_TEST_LOG` rows.
  - `.\RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 12` wrote
    `testing_lab_reports\20260602T011733Z_always_on_orchestrator.json` with
    `overall=throttled`, CPU `48.0 -> 39.0`, `jobs_seen=3`,
    `jobs_dispatched=3`, `work_packets_written=3`,
    `agent_matches_written=3`, and `slow_completion_packages_written=6`.
  - DB readback showed `3` chat-agent jobs, `3` dispatched jobs, `3`
    chat-agent packets, `3` active chat-agent slow packages, `3`
    `ChatAgentJobDispatch` system-test rows, and `1` completed
    `chat_agent_job_dispatch` actual-work row.
  - `py -3 .\tools\viper_ai_test_suite.py lab --section behavioral --json --local-only`
    passed with `chat_agent_jobs=3`, `chat_agent_packets=3`, and
    `chat_agent_slow_count=3`; report
    `testing_lab_reports\20260602T011839Z_behavioral_testing_lab_report.json`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 36}`, report
    `testing_lab_reports\20260602T011908Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0101
-----------------
Stamp:
  - timestamp_utc: 2026-06-02T01:30:06Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Make BM25 orchestration self-modifying in the local DB so agents can
  streamline proof-backed packets and route messy chat/programming/repair
  wording without waiting on model-heavy work.

Top table (self-modifying BM25 orchestrator set):
  - `BM25_ORCHESTRATOR_LEARNING`:
    now includes latest artifacts, schema rows, chat-agent jobs, and global
    todo wording as retrieval documents.
  - `BM25_ORCHESTRATOR_SELF_STATE`:
    route-level top terms, source weights, ranking policy, and evidence for
    the active local BM25 policy.
  - `BM25_ORCHESTRATOR_MUTATIONS`:
    local policy mutation history for term/source-weight rebalancing.
  - `BM25_ORCHESTRATOR_ROUTE_DECISIONS`:
    selected document IDs and scores for build/planning/repair/schema route
    decisions.
  - `ACTUAL_SYSTEM_WORK_LOG`:
    records `bm25_self_modification` as completed bounded work.
  - `LOCAL_FIRST_REPAIR_STATE`:
    includes the BM25 self-state/mutation/decision counts and repair order.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_always_on_orchestrator.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_ai_test_suite.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile .\tools\viper_always_on_orchestrator.py .\tools\viper_ai_test_suite.py` passed.
  - `.\RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 12` wrote
    `testing_lab_reports\20260602T012900Z_always_on_orchestrator.json` with
    `overall=throttled`, CPU `100.0 -> 62.8`, `actual_work_completed=13`,
    `states_written=4`, `mutations_written=4`, `decisions_written=4`,
    `routes_updated=4`, and `source_rows_read=60`.
  - DB readback showed `263` `BM25_ORCHESTRATOR_LEARNING` rows, `4`
    `BM25_ORCHESTRATOR_SELF_STATE` rows, `4`
    `BM25_ORCHESTRATOR_MUTATIONS`, `4`
    `BM25_ORCHESTRATOR_ROUTE_DECISIONS`, and the latest
    `bm25_self_modification` actual-work row had status `completed`.
  - Route-decision readback showed active `ready_local_first` rows for
    `build`, `planning`, `repair`, and `schema`.
  - `py -3 .\tools\viper_ai_test_suite.py lab --section behavioral --json --local-only`
    passed with `bm25_docs=263`, `bm25_self_states=4`,
    `bm25_mutations=4`, and `bm25_decisions=4`; report
    `testing_lab_reports\20260602T012940Z_behavioral_testing_lab_report.json`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 36}`, report
    `testing_lab_reports\20260602T013005Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0102
-----------------
Stamp:
  - timestamp_utc: 2026-06-02T01:44:49Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Reduce live GUI lag without changing the visible GUI workflow.

Top table (GUI performance set):
  - `public/index.html`:
    active 8080 GUI now caps render points, label sprites, frame rate, pixel
    ratio, raycasting, and DOM history growth.
  - `agent_control_web/index.html`:
    secondary GUI copy receives the same render-loop optimizations.
  - `/api/datapoints?limit=N`:
    bridge endpoint now honors bounded point limits so the GUI no longer pulls
    a 1000-row payload when it renders 240 points.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\public\index.html
  - C:\Users\viper\VIPER_JAVA_RISC\agent_control_web\index.html
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - Inline JavaScript parse checks passed for `public/index.html` and
    `agent_control_web/index.html`.
  - `py -3 -m py_compile .\system_mirrors\risc_bridge_server.py` passed.
  - Controlled bridge reload dry run showed port `8080` had only the expected
    safe bridge owner; `.\RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1 -Apply` completed
    without error output.
  - After reload, `/api/datapoints?limit=5` returned `5` points in `2087`
    bytes, `/api/datapoints?limit=240` returned `240` points in `58672`
    bytes, and `/api/runtime/db` remained on the active workspace DB.
  - Browser verification loaded `http://127.0.0.1:8080/?v=gui-perf-20260602`,
    found a canvas plus chat/export/publish controls, showed `240/240 points
    rendered` in the resonance log, and had no browser console errors.
  - `py -3 .\tools\viper_ai_test_suite.py lab --section behavioral --json --local-only`
    passed with report
    `testing_lab_reports\20260602T014449Z_behavioral_testing_lab_report.json`.
  - `.\RUN_VIPER_AI_SELF_REPAIR.ps1` returned exit code `0` with
    `overall=pass`, `counts={'pass': 36}`, report
    `testing_lab_reports\20260602T014544Z_full_testing_lab_report.json`, and
    `NEXT no_action_needed`.

Modification 0103
-----------------
Stamp:
  - timestamp_utc: 2026-06-06T05:20:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Remove visible scripted/autoresponse chat fallbacks while preserving the live
  real-chat model lane.

Top table (non-autoresponse chat set):
  - `tools/viper_real_chat_proxy.py`:
    visible `local_chat_guard` text is removed; exhausted guard paths now return
    metadata-only `visible_chat_suppressed=true` / `non_chat_error` instead of a
    fabricated chat sentence.
  - `system_mirrors/risc_bridge_server.py`:
    exact-social legacy bridge turns are allowed to forward to `11436`; if the
    proxy cannot produce a real reply, the bridge returns no-visible-chat proof
    rather than the old fixed acknowledgement sentence.
  - `tools/viper_real_chat_ecosystem_verifier.py`:
    adds a bounded non-autoresponse corpus for `ok`, `next`, `continue`, and a
    current-improvement prompt; repeated template/canned replies fail proof.
  - `tools/viper_front_to_back_verifier.py`:
    short-chat guard now blocks canned helper/bonding phrases, suppressed guard
    sources, and too-short micro replies.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_real_chat_proxy.py
  - C:\Users\viper\VIPER_JAVA_RISC\system_mirrors\risc_bridge_server.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_real_chat_ecosystem_verifier.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_front_to_back_verifier.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_CHAT_ROUTE_CORRECTION_SOP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile tools\viper_real_chat_proxy.py
    tools\viper_real_chat_ecosystem_verifier.py
    tools\viper_front_to_back_verifier.py system_mirrors\risc_bridge_server.py`
    passed.
  - `START_VIPER_REAL_CHAT_PROXY.ps1 -Restart -Port 11436` reloaded only the
    scoped real-chat sidecar; `11436/health` returned workspace DB
    `java_notes_suite\data\gemini_bridge.db`.
  - `RUN_VIPER_BRIDGE_RELOAD_VERIFY.ps1 -Apply` reloaded the scoped `8080`
    bridge from `system_mirrors\risc_bridge_server.py`.
  - `RUN_VIPER_REAL_CHAT_ECOSYSTEM_VERIFY.ps1 -Json` passed; report
    `testing_lab_reports\20260606T053441Z_real_chat_ecosystem.json` includes
    `non_autoresponse_corpus.status=pass`, `prompt_count=4`,
    `fail_count=0`, `visible_reply_count=4`, and no duplicate response hashes.
  - `RUN_VIPER_FRONT_TO_BACK_VERIFY.ps1 -Json` passed; report
    `testing_lab_reports\20260606T053613Z_front_to_back_verifier.json` has
    `33` pass checks, and embedded full lab
    `testing_lab_reports\20260606T053559Z_full_testing_lab_report.json` has
    `36` pass checks.

Modification 0104
-----------------
Stamp:
  - timestamp_utc: 2026-06-11T00:00:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Put environmental performance first for resumed Codex repair work and add a
  proposal-only token tower that lets the larger house lane coordinate epoch
  upgrade instructions through the existing Java lab queue.

Top table (Codex performance / token tower set):
  - `tools/viper_environment_monitor.py`:
    adds non-CIM RAM/process fallbacks and netstat-backed PID-file liveness so
    Codex sandbox access denial does not falsely hide resource state or mark a
    live listener stale.
  - `tools/viper_codex_performance_preflight.py` and
    `RUN_VIPER_CODEX_PERFORMANCE_PREFLIGHT.ps1`:
    run the headless env preflight, record `CODEX_THREAD_ID`, and report that
    current-chat pruning requires Codex app compaction/archive because no local
    repo API can rewrite the thread.
  - `tools/viper_tok_tower_sync.py` and `RUN_VIPER_TOK_TOWER_SYNC.ps1`:
    inventory local GGUF model lanes, ask the house model for one compact epoch
    instruction, and queue it through Java `/api/epoch-implement` with
    proposal-only guards.
  - `docs/VIPER_CODEX_PERFORMANCE_AND_TOK_TOWER_SOP.md`:
    documents run order, forbidden actions, and TBD chat-prune automation gate.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_environment_monitor.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_codex_performance_preflight.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_tok_tower_sync.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_CODEX_PERFORMANCE_PREFLIGHT.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_TOK_TOWER_SYNC.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_CODEX_PERFORMANCE_AND_TOK_TOWER_SOP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile tools\viper_tok_tree_agent.py
    tools\viper_tok_tower_sync.py tools\viper_codex_performance_preflight.py
    tools\viper_environment_monitor.py tools\viper_real_chat_proxy.py`
    passed.
  - `RUN_VIPER_CODEX_PERFORMANCE_PREFLIGHT.ps1 -Json -ProcessLimit 25`
    completed with monitor `status=pass`, report
    `testing_lab_reports\20260612T004645Z_codex_performance_preflight.json`,
    and `overall=degraded` only for existing environment/backlog risks:
    `JAVA_HOME_DIFFERS_FROM_BUNDLED_RUNTIME`,
    `DUPLICATE_PROTECTED_PROJECT_PROCESS`, `PIPELINE_MIGRATION_DUE`,
    `LEGACY_DB_BACKLOG_HIGH`, and `KAROO_BACKLOG_HIGH`.
  - `START_VIPER_REAL_CHAT_PROXY.ps1` now handles duplicate `11436`
    listeners through health proof, command-line gating, `Stop-Process`, and
    `taskkill` fallback. Manual cleanup removed stale proxy PIDs `20116`,
    `58232`, and `38736`; final netstat showed one listener on PID `60512`.
  - Direct chat probe to `http://127.0.0.1:11436/api/real-chat/predict`
    answered `what is your role?` with `model_source=house_cpp` in
    `13727ms`; `11436/health` showed `house_ready=true`, workspace DB, and
    `real_chat_source=house_cpp`.
  - `RUN_VIPER_TOK_TOWER_SYNC.ps1 -Json -DryRun` passed with `3` GGUF lanes,
    `queue_handoff_status=pass`, and report
    `testing_lab_reports\TOK_TOWER_20260612T004534Z_c2f3aef1_tok_tower_model_sync.json`.
  - `RUN_VIPER_TOK_TOWER_SYNC.ps1 -Json` passed and Java
    `/api/epoch-implement` returned `implementationStatus=bridge_request_recorded`
    for proposal `TOK_TOWER_20260612T004610Z_41cf5d12`; report
    `testing_lab_reports\TOK_TOWER_20260612T004610Z_41cf5d12_tok_tower_model_sync.json`.

Modification 0105
-----------------
Stamp:
  - timestamp_utc: 2026-06-12T00:46:45Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add a wrapped token-tree agent and local DePIN performance/env balancer for
  advanced project asks, while keeping CMDL web-crawl, ADEE dependency install,
  source auto-patching, and broad agent fanout proposal-only.

Top table (tok tree / DePIN set):
  - `tools/viper_tok_tree_agent.py` and `RUN_VIPER_TOK_TREE_AGENT.ps1`:
    analyze messy project asks, classify the route, hydrate deterministic
    `TOK_TREE_*` SQLite state, call the local tiny SLM endpoint when available,
    write Supervisor/Scout/Splicer/Warden/DePINMonitor packets, and emit
    acceptance tests plus a report.
  - DePIN local node packet:
    reads `environment_monitor_latest.json`, reports service readiness,
    memory pressure, proxy/DB env balance, and `VIPER_AGENT_CONCURRENCY` style
    recommendations without joining external networks or storing secrets.
  - SOP/docs:
    document token-tree run order, active/proposal-only boundaries, and proof
    paths next to Codex preflight and token tower sync.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_tok_tree_agent.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_TOK_TREE_AGENT.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\START_VIPER_REAL_CHAT_PROXY.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_CODEX_PERFORMANCE_AND_TOK_TOWER_SOP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `RUN_VIPER_TOK_TREE_AGENT.ps1 -Json -DryRun -AskFile
    C:\Users\viper\.codex\attachments\065b8666-f372-4993-a4ce-8cb3ae3673b6\pasted-text.txt`
    wrote report `testing_lab_reports\20260612T004417Z_tok_tree_agent.json`
    with route `agentic`, CMDL blocks, proposal-only web-crawl/install lane,
    and no source/install action.
  - `RUN_VIPER_TOK_TREE_AGENT.ps1 -Json -AskFile
    C:\Users\viper\.codex\attachments\065b8666-f372-4993-a4ce-8cb3ae3673b6\pasted-text.txt
    -SlmTimeout 20` wrote report
    `testing_lab_reports\20260612T004517Z_tok_tree_agent.json`,
    `slm_semantic_check.status=pass`, and DB readback
    `TOK_TREE_NODES=80`, `TOK_TREE_ASK_ANALYSIS=2`,
    `TOK_TREE_AGENT_PACKETS=5`.
  - DePIN env balance reported all monitored local services pass
    (`8080`, `11435`, `11436`, `18081`, `18181`, `18282`), proxy vars cleared,
    `VIPER_DB_PATH` on the workspace DB, and memory `used_pct=74.9`.

Modification 0106
-----------------
Stamp:
  - timestamp_utc: 2026-06-12T00:00:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Restore the advanced chat-routing design so normal chat, Sprite status,
  Karoo status, project memory, and RAG memory each answer from the right
  evidence surface, while explicit project/build work remains Karoo/proposal
  gated.

Top table (advanced chat route set):
  - `tools/viper_real_chat_proxy.py`:
    adds read-only `project_memory_fast_path` and `rag_memory_fast_path`.
    Project-memory answers read `ADVANCED_PROJECT_QUEUE`,
    `ADVANCED_PROJECT_WORK_PACKETS`, `CHAT_AGENT_JOB_QUEUE`,
    `GLOBAL_TODO_QUEUE`, `TOK_TREE_ASK_ANALYSIS`, and
    `SUCCESSFUL_CODE_ADVANCES`, then return descriptive counts, rows,
    modifiers, and subquestions.
  - `tools/viper_real_chat_proxy.py`:
    tightens Sprite status wording so Sprites stay defined as local
    project-agent lanes, rejecting tiny-model text that frames them as game
    graphics or player-triggered objects.
  - `docs/VIPER_AGENTIC_PROJECT_GENERATION_RESEARCH.md`:
    records the research-backed design: repo-level planning, agent-computer
    interfaces, Reflexion-style feedback memory, Voyager-style skill
    libraries, and SWE-bench-style proof discipline mapped to VIPER/Karoo.
  - `README.md` and `docs/VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md`:
    document the new project/RAG memory chat surfaces.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_real_chat_proxy.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_AGENTIC_PROJECT_GENERATION_RESEARCH.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_SOURCE_OF_TRUTH_RUNTIME_MAP.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile tools\viper_real_chat_proxy.py
    tools\viper_tok_tree_agent.py` passed.
  - `START_VIPER_REAL_CHAT_PROXY.ps1 -Restart -Port 11436 -ModelTimeout 260
    -MicromodelBudgetMs 3500` completed; netstat showed one `11436`
    listener after restart.
  - Normal chat probe `what is your role?` returned `model_source=house_cpp`,
    route `house`, in `11658ms`.
  - Sprite probe `how are sprites working?` returned
    `real_chat_proxy_route=sprite_fast_path`, guarded local-project-agent
    wording, `5` sprites, `240` queued talk packets, and no game-object frame.
  - Karoo probe `what is Karoo doing with coding and learning?` returned
    `model_source=karoo_status_sidecar`, `karoo_fast_path=true`,
    algorithm learning `pass`, active training `pass`, system advancer `pass`,
    and DB counts including `1082` active tasks and `1343` verified code
    advances.
  - Project-memory probe `tell me about my projects with modifiers and
    subquestions` returned `model_source=project_memory_sidecar`,
    `project_memory_fast_path=true`, `6` projects, `23` work packets,
    `4` chat-agent jobs, `2316` todos, `334684` RAG rows, and modifier plus
    subquestion prompts.
  - RAG probe `what does RAG remember about chat and project memory?` returned
    `model_source=rag_memory_sidecar`, `rag_memory_fast_path=true`,
    `334684` RAG rows, matching evidence, modifiers, and subquestions.

Modification 0107
-----------------
Stamp:
  - timestamp_utc: 2026-06-12T04:40:23Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add a repeatable advanced chat route verifier and close the remaining route
  quality gaps: wrong-DB proxy acceptance, duplicated RAG evidence, weak
  project-name filtering, Sprite contract drift, and Karoo status missing the
  verified-code count.

Top table (advanced route verifier set):
  - `tools\viper_advanced_chat_route_verifier.py` and
    `RUN_VIPER_ADVANCED_CHAT_ROUTE_VERIFY.ps1`:
    probe normal house chat, Sprite status, Karoo status, broad project memory,
    filtered Karoo project memory, and RAG memory; write latest/run/report JSON
    with response-shape checks.
  - `tools\viper_real_chat_proxy.py`:
    dedupes RAG/project evidence rows, preserves meaningful filters such as
    `karoo`, `sprite`, `rag`, `token`, and `chat`, and adds verified-code
    counts to Karoo status.
  - `START_VIPER_REAL_CHAT_PROXY.ps1`:
    refuses non-restart success when the existing proxy is not using the
    workspace DB; restart may clean an unhealthy port only when all owners are
    command-line-proven `viper_real_chat_proxy.py`.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_advanced_chat_route_verifier.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_ADVANCED_CHAT_ROUTE_VERIFY.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_real_chat_proxy.py
  - C:\Users\viper\VIPER_JAVA_RISC\START_VIPER_REAL_CHAT_PROXY.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile tools\viper_real_chat_proxy.py
    tools\viper_advanced_chat_route_verifier.py` passed.
  - `START_VIPER_REAL_CHAT_PROXY.ps1 -Restart -Port 11436 -ModelTimeout 260
    -MicromodelBudgetMs 3500` restored the proxy on the workspace DB after an
    unhealthy stale proxy had been serving `C:\Users\viper\gemini_bridge.db`.
  - `RUN_VIPER_ADVANCED_CHAT_ROUTE_VERIFY.ps1 -Json -Timeout 60` passed all
    `6/6` probes with report
    `testing_lab_reports\20260612T044023Z_advanced_chat_route_verifier.json`.
  - Passing probe details:
    normal chat `model_source=house_cpp`, route `house`, `8084ms`;
    Sprite `sprite_fast_path` with local project-agent wording and no
    game/player/Minecraft frame; Karoo `karoo_status_sidecar` with `1347`
    verified code advances; project memory `project_memory_sidecar` with
    modifiers/subquestions; filtered Karoo project memory with
    `Filter term: karoo`; RAG memory `rag_memory_sidecar` with deduped evidence
    and `Filter term: chat`.

Modification 0108
-----------------
Stamp:
  - timestamp_utc: 2026-06-12T00:00:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add the enterprise state-management layer requested for backups, code
  database hydration, command repeat detection, protected port proof,
  research-card classification, and feedback-weighted crawl memory.

Top table (enterprise state set):
  - `tools\viper_enterprise_state_manager.py`:
    creates source/control-plane checkpoints, snapshots runtime SQLite DBs,
    indexes source files/symbols/tokens/token transitions, checks or records
    normalized command hashes, probes protected localhost ports, creates dense
    local-code or explicit-URL research cards, and records like/dislike
    feedback weights.
  - `RUN_VIPER_ENTERPRISE_STATE_MANAGER.ps1`:
    wraps the manager with the standard VIPER env shield and workspace DB
    defaults.
  - `docs\VIPER_ENTERPRISE_STATE_MANAGEMENT_SOP.md`:
    documents the approval boundary for model training, global shell blocking,
    web-search provider integration, and service recovery maps as `TBD` items.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_enterprise_state_manager.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_ENTERPRISE_STATE_MANAGER.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENTERPRISE_STATE_MANAGEMENT_SOP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile tools\viper_enterprise_state_manager.py` passed.
  - `RUN_VIPER_ENTERPRISE_STATE_MANAGER.ps1 -Json -Backup -IndexCode
    -PortCheck -NoRecover` completed after the indexer was bounded and batched;
    latest bounded code DB proof indexed `500` selected files from `7380`
    candidates and reported cumulative DB counts of `999` files, `3127`
    symbols, `151785` token rows, and `305400` token-transition rows.
  - Backup checkpoint
    `docs\backup_checkpoints\ENTERPRISE_STATE_CHECKPOINT_20260612T132202Z`
    copied `7381` source/control files and backed up `gemini_bridge.db`,
    `sprite.sqlite`, and `viper_enterprise_state.db`.
  - Port proof in
    `testing_lab_reports\20260612T132126Z_enterprise_state_manager.json`
    passed `11435`, `11436`, `18081`, `18181`, and `18282`; `8080` remained
    listener-present but degraded because `/health` returned `404` and multiple
    listeners were present, so no locked-GUI restart was attempted.
  - Command ledger proof recorded
    `py -3 -m py_compile tools\viper_enterprise_state_manager.py` as `passed`,
    then `CheckCommand` returned `duplicate=true` with `prior_run_count=1`.
  - Research-card dry run extracted variables `web`, `multi`, `agent`,
    `generation`, generated six query strings, classified local code/doc/topology
    snippets, and wrote report
    `testing_lab_reports\20260612T132140Z_enterprise_state_manager.json`.
  - `py -3 -m py_compile tools\viper_real_chat_proxy.py
    tools\viper_enterprise_state_manager.py` passed after preserving
    `model_source=house_cpp` through tiny cleanup metadata.
  - `START_VIPER_REAL_CHAT_PROXY.ps1 -Restart -Port 11436 -ModelTimeout 260
    -MicromodelBudgetMs 3500` completed.
  - `RUN_VIPER_ADVANCED_CHAT_ROUTE_VERIFY.ps1 -Json -Timeout 60` passed `6/6`
    with report
    `testing_lab_reports\20260612T132543Z_advanced_chat_route_verifier.json`;
    normal chat returned `model_source=house_cpp`, Sprite status used
    `sprite_fast_path`, Karoo status used `karoo_status_sidecar`, project memory
    used `project_memory_fast_path`, and RAG memory used `rag_memory_fast_path`.

Modification 0109
-----------------
Stamp:
  - timestamp_utc: 2026-06-18T00:00:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Repair the Sprite chat visibility gap where chat could pass a narrow Sprite
  status verifier but still fail to see live Sprite SQLite data for broader
  Sprite data/log/inbox/task asks. Add a code implementation fingerprint ledger
  so Sprite/Karoo can check proposed code before starting work and avoid making
  the same code twice.

Top table (Sprite visibility and no-duplicate-code set):
  - `tools\viper_real_chat_proxy.py`:
    broadens Sprite-data route detection and reads `sprite.sqlite` directly for
    `sprite_nodes`, `sprite_plutonic_talk_packets`, `sprite_main_model_inbox`,
    `sprite_cloud_action_packets`, `sprite_karoo_comm_tasks`,
    `sprite_learning_progress`, `sprite_qa_messages`, and
    `sprite_webui_summary_packets`.
  - `tools\viper_sprite_chat_visibility_verifier.py` and
    `RUN_VIPER_SPRITE_CHAT_VISIBILITY_VERIFY.ps1`:
    prove visible chat replies include Sprite DB readbacks and real Sprite table
    names for data/log/inbox/task asks.
  - `tools\viper_enterprise_state_manager.py` and
    `RUN_VIPER_ENTERPRISE_STATE_MANAGER.ps1`:
    add `CODE_IMPLEMENTATION_LEDGER`, `-CheckCodeText`, and `-RecordCodeText`
    for Sprite/Karoo no-duplicate-code gates.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_real_chat_proxy.py
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_sprite_chat_visibility_verifier.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_SPRITE_CHAT_VISIBILITY_VERIFY.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_enterprise_state_manager.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_ENTERPRISE_STATE_MANAGER.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENTERPRISE_STATE_MANAGEMENT_SOP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - `py -3 -m py_compile tools\viper_real_chat_proxy.py
    tools\viper_enterprise_state_manager.py
    tools\viper_sprite_chat_visibility_verifier.py` passed.
  - `RUN_VIPER_ENTERPRISE_STATE_MANAGER.ps1 -Json -RecordCodeText
    "def duplicate_guard_probe(): return 'sprite-karoo'" -SourceAgent
    SPRITE_AUTOMATION_FORGE -Intent "no duplicate code probe" -Language python
    -CommandStatus accepted` recorded the first implementation fingerprint in
    `CODE_IMPLEMENTATION_LEDGER`.
  - `RUN_VIPER_ENTERPRISE_STATE_MANAGER.ps1 -Json -CheckCodeText
    "def duplicate_guard_probe(): return 'sprite-karoo'" -SourceAgent
    KAROO_PROGRAMMING_ORCHESTRATOR -Intent "no duplicate code probe" -Language
    python` returned `duplicate=true`, `prior_source_agent=SPRITE_AUTOMATION_FORGE`,
    `prior_status=accepted`, `prior_seen_count=1`.
  - `START_VIPER_REAL_CHAT_PROXY.ps1 -Restart -Port 11436 -ModelTimeout 260
    -MicromodelBudgetMs 3500` was used to reload the proxy. A later direct
    health probe confirmed `status=ok`, `kind=viper_real_chat_proxy`,
    `db_path=C:\Users\viper\VIPER_JAVA_RISC\java_notes_suite\data\gemini_bridge.db`,
    and `real_chat_source=house_cpp`.
  - First Sprite visibility run proved DB access but timed out because final
    dispatch still sent Sprite data asks to the bridge. The dispatch condition
    was widened for `data/db/log/read/show/inbox/packets/tasks/memory/latest`.
  - Second Sprite visibility run passed but showed the Sprite DB path still
    called the tiny wording model and took ~34 seconds per probe. The Sprite DB
    route was changed to direct DB-backed text with `model_source=sprite_db_sidecar`.
  - Final `RUN_VIPER_SPRITE_CHAT_VISIBILITY_VERIFY.ps1 -Json -Timeout 30`
    passed `2/2` with report
    `testing_lab_reports\20260619T052257Z_sprite_chat_visibility.json`.
    Direct DB readback used
    `C:\Users\viper\SPRITE_HOME\databases\sprite.sqlite` and proved `5`
    `sprite_nodes`, `240` `sprite_plutonic_talk_packets`, `240`
    `sprite_main_model_inbox` rows, `84` `sprite_karoo_comm_tasks`, `16`
    `sprite_cloud_action_packets`, and `23880` `sprite_random_blips`.
  - Final `RUN_VIPER_ADVANCED_CHAT_ROUTE_VERIFY.ps1 -Json -Timeout 60` passed
    `6/6` with report
    `testing_lab_reports\20260619T052325Z_advanced_chat_route_verifier.json`.
    Sprite status now returned in `93ms` through `sprite_db_sidecar` /
    `sprite_fast_path`; normal chat still returned `model_source=house_cpp`;
    Karoo, project memory, and RAG routes remained green.

Modification 0110
-----------------
Stamp:
  - timestamp_utc: 2026-06-19T00:00:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add Nyx as a seed-driven 2-layer, 3-expert MoA steering layer for Headless,
  Sprite, and Karoo work. Store the user's seed paradigm, Nyx topology,
  2006 aviation/Lean Six Sigma project matrix milestone, and Karoo epoch
  upgrade policy as durable local seeds rather than relying on blank-slate
  prompting.

Top table (Nyx seed MoA set):
  - `tools\viper_nyx_moa_seed.py`:
    creates `NYX_SEED_PACKETS`, runs Alpha Analyst, Beta Git, and Gamma
    Architect in parallel, aggregates contradictions, checks the enterprise
    code implementation ledger, writes proposal-only Headless commands, and
    records a Karoo epoch upgrade policy.
  - `RUN_VIPER_NYX_MOA_SEED.ps1`:
    wraps the Nyx seed/MoA engine with the standard workspace DB and proxy env
    shield.
  - `docs\nyx_moa.json`:
    stores the Nyx 3B-ready topology while marking the active runtime as
    deterministic local seed experts until live 3B model proof exists.
  - `docs\VIPER_NYX_MOA_SEED_SOP.md`:
    documents seed rules, Headless proposal boundaries, and Karoo epoch upgrade
    gates.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_nyx_moa_seed.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_NYX_MOA_SEED.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\nyx_moa.json
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_NYX_MOA_SEED_SOP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - PASS: `py -3 -m py_compile tools\viper_nyx_moa_seed.py`.
  - PASS: `RUN_VIPER_NYX_MOA_SEED.ps1 -Json` completed in 664 ms with
    report `testing_lab_reports\20260619T064412Z_nyx_moa_seed.json`;
    active seeds = 4, duplicate-code check = true for the known
    `duplicate_guard_probe`, Headless command records = 3, Karoo epoch policy
    status = `ready_for_user_review`.
  - PASS: Sprite visibility verifier `2/2`, report
    `testing_lab_reports\20260619T064429Z_sprite_chat_visibility.json`.
  - PASS: advanced chat route verifier `6/6`, report
    `testing_lab_reports\20260619T064512Z_advanced_chat_route_verifier.json`.
  - PASS: final enterprise checkpoint
    `docs\backup_checkpoints\ENTERPRISE_STATE_CHECKPOINT_20260619T064700Z`,
    report `testing_lab_reports\20260619T065014Z_enterprise_state_manager.json`.

Modification 0111
-----------------
Stamp:
  - timestamp_utc: 2026-06-19T00:00:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add a Business School Loop so agents and wrappers continuously learn from a
  management curriculum before proposing wrapper upgrades. The loop translates
  operations strategy, Lean Six Sigma, finance/capacity, product management,
  governance/risk, and organizational learning into durable review cards.

Top table (business school loop set):
  - `tools\viper_business_school_loop.py`:
    creates curriculum cards, reviews wrappers, queues proposal-only webcrawl
    research requests, and writes `ready_for_user_review` wrapper upgrade
    proposals without mutating source.
  - `RUN_VIPER_BUSINESS_SCHOOL_LOOP.ps1`:
    provides one-shot and bounded loop modes through the same localhost proxy
    shield and workspace DB rule used by other VIPER wrappers.
  - `docs\VIPER_BUSINESS_SCHOOL_LOOP_SOP.md`:
    documents the curriculum, command contract, output tables, and hard
    no-auto-apply rule.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_business_school_loop.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_BUSINESS_SCHOOL_LOOP.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_BUSINESS_SCHOOL_LOOP_SOP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - PASS: `py -3 -m py_compile tools\viper_business_school_loop.py`.
  - PASS: `RUN_VIPER_BUSINESS_SCHOOL_LOOP.ps1 -Json -Limit 25
    -ResearchLimit 6` completed with report
    `testing_lab_reports\20260619T071029Z_business_school_loop.json`;
    curriculum cards = 6, wrapper reviews = 25, upgrade proposals = 25,
    queued business-school research requests = 6, safety =
    `proposal_only_learning_committed` with `source_mutation=blocked`.
  - PASS: final enterprise checkpoint
    `docs\backup_checkpoints\ENTERPRISE_STATE_CHECKPOINT_20260619T071501Z`,
    report `testing_lab_reports\20260619T071800Z_enterprise_state_manager.json`.

Modification 0112
-----------------
Stamp:
  - timestamp_utc: 2026-06-19T00:00:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Promote the Business School Loop from standalone wrapper learner into the
  governed always-on ecosystem so wrapper research and learning can continue
  under existing CPU gates and actual-work logging.

Top table (governed business school integration):
  - `tools\viper_always_on_orchestrator.py`:
    now compiles `tools\viper_business_school_loop.py` and runs
    `RUN_VIPER_BUSINESS_SCHOOL_LOOP.ps1` in the lightweight maintenance lane.
    Pressure mode uses `-Limit 6 -ResearchLimit 1`; normal mode uses
    `-Limit 20 -ResearchLimit 3`.
  - `ACTUAL_SYSTEM_WORK_LOG`:
    receives `business_school_loop` entries with command and JSON evidence.
  - Business-school proposals remain `ready_for_user_review`; the orchestrator
    does not apply wrapper edits.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_always_on_orchestrator.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_BUSINESS_SCHOOL_LOOP_SOP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - PASS: `py -3 -m py_compile tools\viper_always_on_orchestrator.py
    tools\viper_business_school_loop.py`.
  - PASS: `RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 1 -NoModel`
    returned `overall=throttled` because CPU started at `69.0%`, but the
    lightweight `business_school_loop` maintenance work still completed with
    `returncode=0`, `status=pass`, `pressure_mode=true`, `business_school_limit=6`,
    and `business_school_research_limit=1`.
  - PASS: governed business-school report
    `testing_lab_reports\20260620T011608Z_business_school_loop.json`; orchestrator
    report `testing_lab_reports\20260620T011620Z_always_on_orchestrator.json`.
  - PASS: final enterprise checkpoint
    `docs\backup_checkpoints\ENTERPRISE_STATE_CHECKPOINT_20260620T011653Z`,
    report `testing_lab_reports\20260620T012021Z_enterprise_state_manager.json`.

Modification 0113
-----------------
Stamp:
  - timestamp_utc: 2026-06-20T00:00:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add a Business School Promotion Board so wrapper-learning proposals become
  exact, reviewable implementation packets with acceptance tests and pre-apply
  gates, instead of remaining abstract upgrade advice.

Top table (business school promotion set):
  - `tools\viper_business_school_promoter.py`:
    reads `BUSINESS_SCHOOL_UPGRADE_PROPOSALS`, ranks high-priority wrapper
    proposals, and writes `BUSINESS_SCHOOL_PROMOTION_PACKETS` with wrapper path,
    observed gaps, implementation steps, acceptance tests, and source-mutation
    block state.
  - `RUN_VIPER_BUSINESS_SCHOOL_PROMOTER.ps1`:
    exposes the promoter through the standard proxy shield and workspace DB
    rule.
  - `tools\viper_always_on_orchestrator.py`:
    now compiles the promoter and runs it after the business-school learner in
    the lightweight maintenance lane; pressure mode promotes at most `3`
    packets, normal mode promotes at most `8`.

Files:
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_business_school_promoter.py
  - C:\Users\viper\VIPER_JAVA_RISC\RUN_VIPER_BUSINESS_SCHOOL_PROMOTER.ps1
  - C:\Users\viper\VIPER_JAVA_RISC\tools\viper_always_on_orchestrator.py
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_BUSINESS_SCHOOL_LOOP_SOP.md
  - C:\Users\viper\VIPER_JAVA_RISC\docs\VIPER_ENVIRONMENT_MONITOR_RUNBOOK.md
  - C:\Users\viper\VIPER_JAVA_RISC\README.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - PASS: `py -3 -m py_compile tools\viper_business_school_promoter.py
    tools\viper_business_school_loop.py tools\viper_always_on_orchestrator.py`.
  - PASS: standalone `RUN_VIPER_BUSINESS_SCHOOL_PROMOTER.ps1 -Json -Limit 5`
    wrote `5` review packets with report
    `testing_lab_reports\20260620T013244Z_business_school_promoter.json`.
  - PASS: governed `RUN_VIPER_ALWAYS_ON_ORCHESTRATOR.ps1 -Json -Limit 1
    -NoModel` returned `overall=throttled` with CPU start `43.0%`, but
    `business_school_loop` and `business_school_promoter` both completed as
    maintenance work.
  - PASS: governed promoter used pressure-mode `-Limit 3`, `returncode=0`,
    `status=pass`, and report
    `testing_lab_reports\20260620T013519Z_business_school_promoter.json`;
    orchestrator report
    `testing_lab_reports\20260620T013526Z_always_on_orchestrator.json`.
  - PASS: final enterprise checkpoint
    `docs\backup_checkpoints\ENTERPRISE_STATE_CHECKPOINT_20260620T013555Z`,
    report `testing_lab_reports\20260620T014346Z_enterprise_state_manager.json`.

Modification 0114
-----------------
Stamp:
  - timestamp_utc: 2026-06-26T20:39:00Z
  - project_id: VIPER_JAVA_RISC
  - agent_id: viperAI

Intent:
  Add next-gen multi-sheet database planning and execution router, dynamic rules compiler,
  verification kernel, and connect them to the JavaFX dashboard while enabling twin-node critique audits.

Top table (precision executor set):
  - `matrix_agent.py` / `matrix_executor.py`:
    Implements next-gen database transaction guarantees including global version vectors,
    sheet shadow memory, constraint compilation, temporal ledgers, and atomic rollback buffers.
  - `rule_compiler.py` / `pipeline_registry.py` / `ir_registry.py`:
    Handles dynamic RuleSpec compilations, canonical normalization, schema validation, and SHA-256 IR hashing.
  - `dual_kai_critique.py` / `dashboard_helper.py`:
    Enables Twin-Node proposer/auditor critique loop and hooks JavaFX dashboard '/api/dashboard/excel-sync'
    endpoint directly to the Python agent executor.

Files:
  - C:\Users\viper\gan-otg-db\viper-scripts\matrix_agent.py
  - C:\Users\viper\gan-otg-db\viper-scripts\matrix_executor.py
  - C:\Users\viper\gan-otg-db\viper-scripts\matrix_router.py
  - C:\Users\viper\gan-otg-db\viper-scripts\rule_compiler.py
  - C:\Users\viper\gan-otg-db\viper-scripts\pipeline_registry.py
  - C:\Users\viper\gan-otg-db\viper-scripts\ir_registry.py
  - C:\Users\viper\gan-otg-db\viper-scripts\dual_kai_critique.py
  - C:\Users\viper\gan-otg-db\viper-scripts\dashboard_helper.py
  - C:\Users\viper\VIPER_JAVA_RISC\PROJECT_SNAPSHOT_ASCII.md
  - C:\Users\viper\VIPER_JAVA_RISC\ASCII_MODIFICATION_LEDGER.md

Proof:
  - PASS: E2E test suite `test_moe_e2e_new.py` running successfully (38/38 passing).
  - PASS: rule compiler tests `test_compiled_rules.py` running successfully.
  - PASS: dual-kai critique mock loop `dual_kai_critique.py` running successfully.
  - PASS: dashboard API sync `dashboard_helper.py excel_sync` running successfully.
