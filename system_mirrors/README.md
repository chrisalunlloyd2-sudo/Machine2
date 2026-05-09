# System Mirrors

These files are exact project-local mirrors of VIPER runtime files that live
outside this repository root.

```text
risc_bridge_server.py
  source: C:\Users\viper\risc_bridge_server.py
  purpose: live GUI/backend bridge on http://127.0.0.1:8080
```

The mirror exists so local git/GitHub checkpoints include the patched bridge
logic. Runtime still uses the source path above unless a launcher is changed.
