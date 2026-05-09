# VIPER Agent Control Web Copy

This folder is a managed copy of the locked Tripleted Manifold webpage.

```text
public/index.html  -> live GUI served on port 8080
agent_control_web  -> managed control-plane copy for future agent web ownership
```

Current policy:

- Keep the live GUI visual design unchanged.
- Use this copy for agent-control experiments, future Java SHA-256 ledger views, and cloud CLI pair coordination.
- Any promotion from this copy back to the live GUI requires explicit approval.

Planned role:

```text
agent_control_web
      |
      v
Java/SHA-256 ledger backend
      |
      v
GAME_DATA + GLOBAL_TODO_QUEUE + ACL/KQML messages
      |
      v
agent pairs propose work -> POE/PON -> approval -> global broadcast
```
