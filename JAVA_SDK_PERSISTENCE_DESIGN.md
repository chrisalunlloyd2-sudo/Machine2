# VIPER Java SDK Persistence Design

Current SDK version:

```text
0.4.1-training-lab
```

This document defines the Java-side persistent SDK and lab suite. It is separate
from the locked main GUI. The main Java/Three.js page remains unchanged.

```text
+------------------------+        +----------------------------+
| VIPER Java SDK          | -----> | java_notes_suite/data      |
| http://127.0.0.1:18181  |        | append-only JSONL + JSON   |
+------------------------+        +----------------------------+
          |
          v
+------------------------+        +----------------------------+
| Local service probes    | -----> | bridge, house, shipper     |
| tests, AB, training     |        | logs, topology, ledger     |
+------------------------+        +----------------------------+
          |
          v
+------------------------+        +----------------------------+
| Benchmark graph panel   | -----> | benchmark_snapshots.jsonl  |
| recursive epoch log     |        | recursive_training_epochs  |
+------------------------+        +----------------------------+
          |
          v
+------------------------+        +----------------------------+
| ASCII epoch queue       | -----> | ascii_epoch_queue.jsonl    |
| optional judge slots    |        | Copilot/Gemini/cloud/local |
+------------------------+        +----------------------------+
          |
          v
+------------------------+        +----------------------------+
| upgrade proof analyzer  | -----> | epoch_upgrade_proofs.jsonl |
| evidence -> proposal    |        | highlighted acceptance     |
+------------------------+        +----------------------------+
```

## Java SDK Surface

The Java SDK is implemented in:

```text
java_notes_suite/src/com/viper/notes/ViperLabSuiteServer.java
```

Run command:

```powershell
.\java_notes_suite\START_LAB_SUITE.ps1
```

Local URL:

```text
http://127.0.0.1:18181
```

## Standalone And APK Shape

Desktop standalone launcher:

```text
java_notes_suite/src/com/viper/notes/ViperLabSuiteApp.java
java_notes_suite/BUILD_STANDALONE_APP.ps1
java_notes_suite/RUN_STANDALONE_APP.ps1
java_notes_suite/dist/viper-java-sdk-standalone.jar
java_notes_suite/dist/app-image/VIPERJavaSDK/VIPERJavaSDK.exe
```

The desktop launcher is a Java Swing shell. It starts or reuses the SDK server,
keeps the same dark VIPER visual language, and exposes quick buttons for:

```text
open SDK
health
state
benchmarks
capture benchmark
ASCII epoch queue
```

## Real Tiny-Model Retrieval/Chooser Contract

```text
purpose
  -> DB retrieval with real rows
  -> SmolLM2-360M closest 50-word axiomatic match
  -> Qwen2.5-0.5B active lens, <=100 words
  -> Qwen2.5-0.5B rolling recursive triplet card
  -> House/Karoo/abliterated response lane
```

Persistence tables:

```text
AXIOMATIC_RETRIEVAL_MATCHES
TINY_MODEL_EVENTS
ROLLING_TRIPLET_RUNS
USER_WORD_STATS
USER_TOPOLOGICAL_WANTS
BENCHMARK_EVENTS(component=tiny_model_runtime)
```

Deterministic prompt templates are now guardrails/fallback only. A passing
epoch requires `matched_by_smollm2` for retrieval and `chosen_by_qwen2_5` for
the active lens unless the model is explicitly disabled or offline.

APK skeleton:

```text
android_apk_skeleton/
```

The APK skeleton is an Android WebView app. It does not embed the Java backend
yet; it points to an SDK endpoint. On Android, `127.0.0.1` means the phone, so
desktop/laptop control should use a LAN, Cloudflare, or tunnel URL.

```text
phone APK -> WebView -> SDK URL -> Java SDK backend -> logs/benchmarks/ledger
```

The UI is a VS Code-like dark SDK surface with:

- explorer rail for logs and persistent datasets;
- service watch for bridge, house, and shipper;
- quick test runner;
- quick settings editor;
- A/B test logger;
- active eval training run logger;
- recursive training record backed by service/prefetch/benchmark proof;
- benchmark snapshot graph for bridge, house, and shipper latency;
- ASCII epoch queue with quick-edit variables and optional judge slots;
- upgrade proof analyzer that reads live logs/benchmarks and proposes concrete
  one-variable epoch upgrades;
- Loihi experiment logger;
- design endpoint.

## SDK Options Covered

The Java SDK is the place for durable operator controls. Current option groups:

```text
health/service watch:
  bridge 8080, house 11435, shipper 18081

logs:
  system, shipper, topology, house stdout/stderr, tests, AB, training,
  Loihi, persistence

settings:
  mode, reply token budgets, Karoo proposal-only flag, heartbeat seconds,
  promotion gate, notes destination

testing:
  one-variable system test records, service health proof, duration,
  SHA-256 record

AB testing:
  candidate A/B plans, metric, promotion gate, append-only record

training:
  dataset name, route, one changed variable, service probes, bridge prefetch,
  benchmark readback, candidate score, append-only proof record

recursive training:
  training-backed epoch, changed variable, dataset slice, evaluation score,
  benchmark snapshot, SHA-256 record; no model-weight mutation from this SDK yet

benchmarks:
  service latency graph, persistent snapshot log, current counts, log sizes

ASCII epochs:
  always-waiting proposal queue for chooser, DB retrieval, Karoo, abliterated,
  Loihi, Lava, SOAP, ledger, network, and Java SDK variables
  plus a VS Code-like proposed-change diagram that highlights the target
  subsystem, quick-edit variable, and judge slot

external judge slots:
  optional Copilot/Gemini/cloud agents may weigh an epoch, but local benchmark
  proof and SHA-256 logging remain the promotion authority

upgrade proof:
  live evidence scan over bridge benchmarks, house health, shipper health,
  shipper logs, and topology logs; emits highlighted proposed changes and
  acceptance tests without auto-applying code

Loihi:
  cube geometry, spike contract, simulation/proposal mode, SHA-256 edge ids

network/agents:
  heartbeat design references the 8-node ring stored in the main DB

notes/log archive:
  Java SDK reads durable logs; bridge queues notes and log archive shipments

security:
  Java SDK can view logs; passive sentinel stores events in the main DB
```

Not included by design:

- destructive cleanup;
- firewall or security mutation;
- raw model weight mutation;
- automatic promotion without proof;
- locked main GUI edits.

## Persistent Files

All Java SDK persistence is append-only or explicit settings replace.

```text
java_notes_suite/data/sdk_settings.json
java_notes_suite/data/system_tests.jsonl
java_notes_suite/data/ab_tests.jsonl
java_notes_suite/data/training_runs.jsonl
java_notes_suite/data/recursive_training_epochs.jsonl
java_notes_suite/data/benchmark_snapshots.jsonl
java_notes_suite/data/ascii_epoch_queue.jsonl
java_notes_suite/data/epoch_upgrade_proofs.jsonl
java_notes_suite/data/loihi_experiments.jsonl
java_notes_suite/data/persistence_events.jsonl
```

Rules:

- no deletes from the Java SDK;
- system tests append one JSON object per run;
- A/B tests append one JSON object per plan;
- active eval training appends one JSON object per run and a linked recursive
  epoch record;
- recursive training epochs append one proof-backed record per proposed
  variable change;
- benchmark snapshots append one service/count/log-size measurement per capture;
- ASCII epochs append one subsystem/variable/judge proposal per queue item;
- upgrade proofs append one evidence-based proposal set per analysis run;
- Loihi experiments append one JSON object per experiment;
- settings are explicitly replaced through `/api/settings`;
- every write records SHA-256 proof where practical.

## Endpoints

```text
GET  /health
GET  /api/state
GET  /api/settings
POST /api/settings
POST /api/run-test
POST /api/ab-test
POST /api/training
POST /api/recursive-training
GET  /api/benchmarks
POST /api/benchmark-snapshot
GET  /api/ascii-epochs
POST /api/ascii-epochs
POST /api/epoch-upgrade-proof
POST /api/loihi-experiment
GET  /api/log-tail?file=<name>&lines=80
GET  /api/design
```

Log names accepted by `/api/log-tail`:

```text
system
shipper
topology
house_stdout
house_stderr
tests
ab
training
recursive_training
benchmarks
ascii_epochs
epoch_upgrades
loihi
persistence
```

## Proof Of System Concept

The proof endpoint turns raw system state into concrete proposed epoch changes.

```text
scan:
  bridge benchmarks
  house health
  shipper health
  shipper tail
  topology tail

propose:
  bridge headroom repair
  shipper uplink compatibility
  Karoo comparator attachment
  sovereign agent capability contract
  rolling recursive triplet restore
  mission directive always-on
  tail continuation/stitching
  inference optimization stack
  distributed resource app
  axiomatic weighted truth tables

test:
  one variable per proposal
  acceptance test written beside each proposal
  test result starts as TBD until measured
  SHA-256 proof logged
  no automatic code mutation
```

## Rolling Triplet Restore

Approved proposal:

```text
tiny chooser/decider
  -> light draft model
  -> Karoo/action edit pass
  -> verifier edit pass
  -> tail continuation if long
  -> response stitched into one useful answer
```

The mission directive is placed before variable context so future prefix caching
can reuse the static instruction prefix.

## Inference Optimization Epochs

Approved proposal set:

```text
quantization:
  GGUF quant choice now; GPTQ/AWQ/FP8 only where hardware/runtime supports it

prefix caching:
  static mission/system/retrieval prefix first, variable ask last

prefill/decode split:
  proposal only until a vLLM/llm-d style serving layer exists

flash attention / paged KV / continuous batching:
  runtime capability table first, benchmark before enabling

speculative decoding:
  small draft model plus verifier model, best for code/structured output
```

## Axiomatic Weighted Truth Tables

Every coding proposal should carry:

```text
axiom | evidence | counterexample | weight | confidence | test | verdict
```

## Scientific Method Gate

Every system test should isolate one changed variable:

```text
variable -> test -> measure -> compare -> log -> decide
```

Promotion rule:

```text
success >= 99.99%
AND
(speed_gain >= 10% OR resource_drop >= 10%)
```

Everything else remains proposal-only.

## Recursive Training Truth Table

The Java SDK can now submit a real training/eval run and a linked recursive
training epoch record. It still does not mutate model weights.

```text
asked: "does this submit recursive training?"
answer: yes for proof-backed training/eval data; no for model-weight mutation

implemented:
  POST /api/training
  -> probes bridge/house/shipper
  -> asks bridge predictive prefetch
  -> reads bridge benchmark history
  -> scores one changed variable
  -> writes training run + recursive epoch + benchmark snapshot + SHA-256

implemented:
  POST /api/recursive-training
  -> logs changed variable, dataset slice, benchmark-before, gate, SHA-256

implemented:
  POST /api/benchmark-snapshot
  -> logs bridge/house/shipper latency, counts, log sizes, SHA-256

future runner:
  load dataset slice
  mutate one retrieval/logic variable
  run longer benchmark/eval suite
  compare against baseline
  promote only if gate passes
```

## Fabric and Tiny Cards

The 15-word limit is an internal lens-card limit, not a user-output limit.

```text
ask card       -> 15 words
DB card        -> 15 words
recent card    -> 15 words
repair card    -> 15 words
chosen Fabric  -> real retrieval + cards + route contract
large model    -> normal answer headroom
```

The Java SDK records and displays the resulting tests, AB plans, and active
training/eval runs. The Python bridge and database still handle the active
Fabric chooser.

## Loihi/Lava Sidecar Contract

Loihi is not treated as a thinking chat model. It is treated as a future
neuromorphic sidecar for measurable topology experiments.

## ASCII Logic Cube Flows

The logic cube is the shared mental map for routing asks, retrieval, Karoo
proposals, benchmark proof, and future Loihi topology work.

```text
                         z: top-code family
                              ^
                              |
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
            /
           v
  y: weight / amplitude / polarity
```

Runtime flow through the cube:

```text
user ask
  |
  v
+------------------+     +------------------+     +------------------+
| purpose card      | --> | DB retrieval      | --> | web/research card |
| tiny, compressed  |     | real local data   |     | only if needed    |
+------------------+     +------------------+     +------------------+
          |                        |                         |
          v                        v                         v
+---------------------------------------------------------------------+
| active lens: purpose + evidence + route + token budget + tools       |
+---------------------------------------------------------------------+
          |
          v
+------------------+     +------------------+     +------------------+
| chat route        |     | planning route   |     | build route       |
| direct answer     |     | Karoo proposal   |     | code/test/log     |
+------------------+     +------------------+     +------------------+
          |                        |                         |
          +------------+-----------+------------+------------+
                       |
                       v
+---------------------------------------------------------------------+
| benchmark proof: latency, tests, A/B, SHA-256, promotion gate         |
+---------------------------------------------------------------------+
                       |
                       v
+------------------+     +------------------+     +------------------+
| keep              |     | retry/repair     |     | reject/prune      |
| log success       |     | one variable     |     | no promotion      |
+------------------+     +------------------+     +------------------+
```

Future spike/topology readback:

```text
top-code point
  -> cube coordinate (x logic, y weight, z family)
  -> spike simulation / Lava sidecar
  -> measured delta
  -> Karoo comparison
  -> benchmark gate
  -> SHA-256 ledger record
```

Conceptual flow:

```text
NLP ask
  -> tiny chooser extracts topological codes
  -> top-code graph maps into spike topology
  -> simulated Lava/Loihi layer mutates/weights code points
  -> output is translated back into logic deltas
  -> Karoo compares and tests before promotion
```

Initial experiment shape:

```text
cube: 100x100x100
x: local code/logic coordinate
y: amplitude or positive/negative weight
z: topological code family
edge id: SHA-256 hybrid identifier
transport: normal TCP/IP or local API
verification: SHA-256 data record plus test proof
```

The Java SDK endpoint `/api/loihi-experiment` logs these experiments as
proposal/simulation records. Real Lava/Loihi execution should be added only
after resource checks pass.

## Karoo Role

Karoo remains the application-development optimizer:

```text
retrieve successful code
compare candidate options
propose one variable change
run or request test
log proof
promote only if gate passes
```

The Java SDK does not self-apply Karoo changes. It records tests, settings,
training runs, and Loihi experiments for review and later automation.

## Persistence Requirement

Persistence is mandatory for this design because agents and devices may go
offline, reconnect, or continue work later. Every important operational action
must leave a small durable record:

- what changed or was proposed;
- which variable was tested;
- which service was checked;
- which SHA-256 proof was generated;
- whether promotion was allowed.

This keeps the agent network coherent without relying on one long prompt or one
local process staying alive forever.
