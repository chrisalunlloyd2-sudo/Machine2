# VIPER Agent Specs

## Required Heartbeat Fields

```text
agent_id
endpoint
status
cpu_cores
ram_total_mb
ram_available_mb
disk_free_mb
tools
resource_sha256
```

## Required Cross-Window Reply Behavior

Agents must not assume the user saw a long-running completion message. If there is no explicit confirmation, record the completion in `MISSED_MESSAGE_RELAY` and repeat it in the next active window.

Commands:

```powershell
python tools/missed_message_relay.py add net_agent "finished some work" --source-window net_agent_worker
python tools/missed_message_relay.py pending --window phone_cli
python tools/missed_message_relay.py confirm MISSED_ID --by viper
```

## Install Gate

```text
install_allowed = resources meet rule AND required tools exist
```

Current rule classes:

- `tiny_sidecar`: small Python/router/lens scripts.
- `java_agent`: Java service work.
- `rust_builder`: Rust build/test work.
- `heavy_model_node`: local model service.

## Optimization Profiles

### Speed Optimized

- prefer local DB/index reads
- cache endpoints and tool lists
- reduce prompt payloads with conversation lenses
- use compact test commands
- avoid model calls when deterministic checks can decide

### Stability Optimized

- heartbeat before assignment
- resource-fit install checks
- timeout every network/model call
- append-only logs
- SHA-256 evidence for all state transitions
- proposal-only for removals, GUI changes, auth/security changes, and raw model changes

### Capability Addons

Potential addons must be proposed before onboarding:

- lightweight vector/search DB for code recall
- endpoint monitor/heartbeat dashboard
- static analyzer/test runner pack
- Java JDK enablement
- Rust toolchain enablement
- phone DB mirror/relay

No addon installs unless the node has resources for it.
