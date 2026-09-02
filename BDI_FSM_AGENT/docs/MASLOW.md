# Maslow Hierarchy of Needs (Modular)

The agent has a **modular hierarchy of needs** — "to do a task, an agent
NEEDS:". Mirroring Maslow's human hierarchy, mapped to agent operations:

| Level | Need | What it means | Auto-tell signal |
|---|---|---|---|
| **Physiological** | Resources | disk free, RAM available | `resources` unmet → Aegis frees storage |
| **Safety** | Integrity | NMCT vault untampered, rollback available | `integrity` unmet → Aegis audits vault |
| **Belonging** | Comms | relay/control channel reachable | `comms` unmet → Aegis restarts relay |
| **Esteem** | Trust | trust ledger score ≥ threshold | `trust` unmet → Aegis reviews ledger |
| **Self-actualization** | Betterment | continuous improvements logged | `betterment` unmet → Aegis enables loop |

## How it works

1. `Maslow.register(Need(...))` — needs are **modular**; add/remove any
   need without touching the core.
2. Every heartbeat, the agent evaluates ALL needs
   (`Maslow.write_status()` → `.bdi_state/maslow/needs_status.json`).
3. The status file is the **auto-tell to the system**: Aegis reads it and
   satisfies unmet needs (free disk, fix vault, restart relay, ...).
4. Lower levels gate higher ones: if resources are starved, nothing else
   matters (blocking_levels logic).

## Built-in needs (all modular)

```python
maslow.add_resource_need(min_disk_mb=50, min_ram_mb=16)   # physiological
maslow.add_integrity_need(nmct)                            # safety
maslow.add_comms_need(relay_check)                         # belonging
maslow.add_trust_need(trust_file, min_trust=0.0)           # esteem
maslow.add_betterment_need(log_path, min_improvements=1)   # self-actualization
```

## The Chris workflow this enables

> "you can make thousand item lists, let the bot go and hope for the best,
> and then swoop in and correct the 50% good code"

1. Feed the agent a **thousand-item task list**.
2. The agent works autonomously, driven by needs — it only stops when a
   need is unmet, and it TELLS the system which one.
3. The system (Aegis) satisfies the need → the agent resumes.
4. Aegis reviews the output, corrects the ~50% that needs correction,
   seals winners into the NMCT vault.
5. Repeat — each cycle the vault hit-rate rises (compounding determinism),
   so fewer corrections are needed over time.

## Auto-tell example output

```json
{
  "levels": { "physiological": [...], "safety": [...], ... },
  "unmet": [
    {"id": "resources", "name": "Disk + RAM resources",
     "level": "physiological", "satisfied": false,
     "detail": "{\"disk_free_mb\": 41.2, \"ram_avail_mb\": 512.0}"}
  ],
  "blocking_levels": ["physiological"]
}
```
