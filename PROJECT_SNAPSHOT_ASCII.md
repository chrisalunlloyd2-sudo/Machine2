# VIPER RISC Snapshot: Topological Control Plane

Timestamp: 2026-05-07

```text
        .-------------------.              .----------------------.
        |  Human / Browser  |              | Cloud SHA-256 Ledger |
        |  GUI + last 10    |<---hash----->| Uplink / Replicas    |
        '---------+---------'              '----------+-----------'
                  |                                   ^
                  v                                   |
        .---------+---------.                         |
        |  RISC Bridge      |                         |
        |  port 8080        |---logic-only queue------'
        |  last 25 chats    |
        '---------+---------'
                  |
                  v
        .---------+---------.
        | gemini_bridge.db  |
        | logic + topology  |
        '----+---------+----'
             |         |
             |         |
             v         v
.------------+--.   .--+----------------.
| Karoo Sidecar |   | Loihi Spike Sidecar|
| propose only  |   | sparse 100^3 cube  |
| reports/hashes|   | Lava-ready manifest|
'-------+-------'   '---------+---------'
        |                     |
        v                     v
.-------+---------------------+-------.
| Approval Queue / Spike Reports      |
| no mutation without explicit yes    |
'-------------------------------------'
```

## What Changed

- Browser chat preserves the last 10 replies with `localStorage`.
- Backend bridge has `CHAT_MEMORY` for the last 25 user/TRIPLET exchanges.
- Reasoning prompt is compact: visible `<thought>` note when useful, not long hidden-style chain-of-thought dumping.
- Performative router classifies `chat`, `performative`, or `both`.
- Karoo loop maps subsystems, creates approval reports, watches dislikes, and queues hash blocks.
- Loihi sidecar runs sparse top-code spike experiments and records Lava/Loihi backend manifests.
- Ledger readiness tables prepare non-local hardware replicas and global agent access.

## CPU Clock Policy

```text
hot path:   GUI -> route -> DB recall -> compact model reply
side path:  Karoo/Loihi/Fabric-like analysis -> reports -> hashes
cloud path: hash metadata -> ledger replica -> reconcile
```

No extra prompt bulk in the live response path unless a task truly needs it.

## Current Guard Rails

- GUI style is locked.
- Java/backend mutations require explicit approval.
- Cloud and agentic systems can propose, not self-apply.
- Raw source/chat export stays off by default; hashes and metadata are the normal payload.
2026-05-07 RETRIEVAL / LENS CHECKPOINT
======================================

        +-------------------+
        | user ask          |
        | chat / plan/build |
        +---------+---------+
                  |
                  v
        +-------------------+        +-------------------+
        | retrieval chooser | -----> | SQLite logic hits |
        | fabric lens       |        | hashes + scores   |
        +---------+---------+        +-------------------+
                  |
                  v
        +-------------------+
        | RISC bridge chat  |
        | health guarded    |
        +----+---------+----+
             |         |
             v         v
       straight chat   Karoo epoch request
       no Karoo        proposal-only build/plan

New files:
  tools/data_retrieval_lens_agent.py
  ASCII_MODIFICATION_LEDGER.md

Stall fix:
  - House is health-checked before chat calls.
  - Chat/planning/build have bounded wait budgets.
  - Slow or crashed house returns a fallback instead of hanging the GUI.

2026-05-07 PREDICTIVE / LAB CHECKPOINT
======================================

       first 3 words
            |
            v
   +--------------------+
   | predictive prefetch|
   | route + intent     |
   +---------+----------+
             |
             v
   +--------------------+      every 5 chats      +-------------------+
   | CHAT_MEMORY        | ----------------------> | USER_TOPOLOGY     |
   | last 25 available  |                         | compact profile   |
   +--------------------+                         +-------------------+
             |
             v
   +--------------------+
   | BENCHMARK_EVENTS   |
   | route/ms/status    |
   +--------------------+

Separate Java GUI:
  java_notes_suite/src/com/viper/notes/ViperLabSuiteServer.java
  http://127.0.0.1:18181

Main GUI:
  unchanged and hash-locked.

2026-05-07 DYNAMIC FABRIC / SOP CHECKPOINT
==========================================

          ask
           |
           v
 +-------------------+
 | dynamic fabric    |
 | template snapshot |
 +----+---------+----+
      |         |
      v         v
 DB hooks     successful code hooks
              CODE_BLOCKCHAIN_DB / LEDGER / KAROO
      |
      v
 webcrawl request queue
 noise -> claims + hashes + risk only
      |
      v
 future 12-agent team SOP
 up to 20 recursive rounds
      |
      v
Viper compile / GitHub / README / pingback

OneDrive:
  slow lane for reduced summaries, approved artifacts, hashes, and handoffs.

2026-05-07 HOUSE ROBUSTNESS CHECKPOINT
======================================

      bridge route
           |
           v
 +--------------------+
 | inference governor |
 | pack / cap / retry |
 +----+----------+----+
      |          |
      v          v
 chat/plan     build route
 bounded       non-blocking lens queue
 house call    Karoo proposal lane

House:
  /health and /config expose n_ctx, safe input budgets, retry ladder.
