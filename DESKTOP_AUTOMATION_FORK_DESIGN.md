# VIPER Desktop Automation Fork Design

Status: documented only; not active.

```text
user text
  |
  v
Qwen tiny pass 1: desktop automation needed?
  |
  +-- no -> normal chat/build/planning lane
  |
  v
environment scan: screenshot + window map + accessibility hints
  |
  v
Qwen tiny pass 2: coarse target area + action intent
  |
  v
Karoo coordinate narrowing: compare candidate points, one variable per test
  |
  v
execute approved action
  |
  v
abliterated/house report -> DB coordinate update -> next step
```

Rules:
- No unattended clicks or keystrokes until explicitly enabled.
- Use screenshot/vision only when the desktop target is ambiguous.
- Save learned coordinates by app/window/title/screenshot hash.
- Re-read coordinates before every action, then update after the result.
- Karoo may propose coordinates; execution remains approval-gated.
