# VIPER Agent App Development Protocol

## Purpose

Karoo GPT is the app-development suite coordinator. Other agents can request code, research, tests, scripts, or DB memory, but app changes must pass through this protocol before they become trusted system state.

## Announce Protocol

When any agent appears, run:

```text
heartbeat
quick-look
resource-fit install check
broadcast-capabilities
```

ACL/KQML shape:

```text
(tell :sender <agent_id> :receiver all
  :content (announce
    :made-of <runtime/tools/db/model>
    :can-do <actions>
    :resources <cpu ram disk tools>
    :policy install-only-if-resources-fit
    :proof poe pon sha256))
```

## Missed Message Relay

If an agent finishes work and the user does not confirm receipt, the message stays pending and should be repeated in the next active window.

Rule:

```text
agent completion
-> write MISSED_MESSAGE_RELAY pending row
-> next window asks pending
-> show: "<agent> finished some work: <message>"
-> mark confirmed only after user acknowledgement
```

Example:

```text
net_agent finished some work: finished research bundle
```

Use `tools/missed_message_relay.py` for add, pending, and confirm operations.

## Device Roles

- Desktop/control node: GUI bridge, house model path, system tests, Karoo approval, ledger coordination.
- Laptops: research, networking, crawls, verification, routing, comparison.
- Phones: quick DB lend, note capture, memory mirrors, lightweight heartbeat, SHA/index relay.

## Prompt-To-Code Route

```text
any agent request
-> classify chat / performative / both
-> lens-maker prepares tools, DB refs, endpoints, constraints
-> Karoo creates candidate in isolated workspace
-> verifier checks objective, compile, runtime, security, resources
-> SHA-256 evidence logged
-> Codex/user approval or auto gate
-> merge only if allowed
```

## Full Development Team SOP (Future 12-Agent Pass)

This SOP is staged for later automation. It is not self-executing yet.

```text
Viper request
-> chooser crafts dynamic Fabric template
-> pull successful code from Karoo DB + SHA ledger
-> queue webcrawl research only for missing facts
-> reduce crawl noise to claims / hashes / risks
-> 12-agent rolling recursive passoff
   round 1..20:
     agent 01 product/scope
     agent 02 architecture
     agent 03 UI adapter
     agent 04 backend/API
     agent 05 database/ledger
     agent 06 tests
     agent 07 security
     agent 08 performance
     agent 09 docs
     agent 10 integration
     agent 11 release/GitHub prep
     agent 12 ministry stop/best critic
-> Viper compile/test/upload checkpoint
-> write README/release summary
-> ping user with result, hashes, and next action
```

Rules:

- One changed variable per candidate.
- Each pass must return proof of execution or a clear blocker.
- Regression goes back into the passoff queue.
- GitHub upload is a final explicit checkpoint, not an automatic side effect.
- OneDrive is the slow pipeline for summaries, hashes, approved artifacts, and handoff notes.
- Raw secrets, destructive changes, and GUI visual mutations stay out of scope without explicit approval.

## Karoo Rules

- Compare candidates against project-local code first.
- Use external snippets only as reference, not blind replacement.
- One changed variable per experiment.
- End-to-end test every candidate.
- Log pass/fail into `SYSTEM_TEST_LOG`, `GLOBAL_TODO_QUEUE`, and SHA ledger where relevant.
- Successful snippets become logic/code memory only after objective adherence is verified.

## Loihi Rules

The sparse Loihi sidecar is learning-shaped, not trusted learning yet. It can rank top-code patterns, log spike experiments, and propose edge-weight updates. It must not self-apply learning changes until a reward/update rule has repeated evidence.

## Environment Optimization

Each agent should optimize for its own environment:

- Speed: use local indexes, compact prompts, small payloads, hot caches.
- Stability: resource-fit install gates, timeout budgets, restart-safe logs.
- Capability: install or enable only tools the node can afford.
- Cleanup: propose stale/slow component removal in round-robin review; do not delete without approval.

## Daily Round Robin

Once per day:

```text
for each agent:
  crawl one focused source set for agentic upgrades
  submit 10 candidate upgrades
  pass candidates to next agent for critique/edit
  consolidate top 10
  ask user which, if any, should onboard
```

All onboarding remains proposal-only unless it passes the active auto-advance gate and is inside allowed scope.
