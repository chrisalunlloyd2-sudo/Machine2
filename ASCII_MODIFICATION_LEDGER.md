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
