# VIPER Scaling Resource Network Protocol

## Goal

Let multiple phones, laptops, CLIs, and local agents come online overnight and become a safe resource mesh for DB memory, research, light compute, verification, and code-support tasks.

## Public Base

```text
https://electoral-backing-coast-coordinate.trycloudflare.com
```

## Device Hookup

Each device starts with a heartbeat:

```bash
curl -X POST https://electoral-backing-coast-coordinate.trycloudflare.com/api/agent/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"DEVICE_ID","display_name":"DEVICE NAME","endpoint":"DEVICE_ENDPOINT","role":"phone_db_lend_node","capabilities":{"db":"sqlite","compute":"light","storage":"lend"},"resources":{"storage_mb":512,"battery":"ok"}}'
```

Phones can use:

```text
role = phone_db_lend_node
```

Laptops can use:

```text
role = research_network_node
```

CLI/cloud agents can use:

```text
role = light_compute_agent
```

## Cloud Agent Ask Rule

Local agents may ask a cloud CLI/agent for help only through a scoped ACL
request and only when local retrieval is insufficient, slow, or missing a tool.
The cloud response is advisory until a local agent records proof.

```text
(request :sender <local_agent> :receiver cloud_agent
  :content (ask-cloud
    :reason <missing_context_or_tool>
    :ask_sha256 <hash>
    :allowed_data logic_hashes_only
    :requires proof_of_execution))
```

Cloud agents should receive hashes, summaries, file paths, tool lists, and
problem statements before raw data. Any returned code/change is routed back
through Karoo comparison and the normal 99.99% + 10% gate before promotion.

## Resource Status

```bash
curl https://electoral-backing-coast-coordinate.trycloudflare.com/api/resource/status
```

The network tracks:

- `RESOURCE_NETWORK_NODES`
- `RESOURCE_NETWORK_TASKS`
- `RESOURCE_NETWORK_ASSIGNMENTS`
- `RESOURCE_NETWORK_PROOFS`

## Assignment Rules

Nodes are scored from capabilities and resources. Tasks are leased, not permanently assigned. Every assignment should eventually return proof.

```text
heartbeat -> score node -> create task -> assign best-fit node -> receive proof -> raise trust slowly
```

## NAS / Agent Spin-Up

No NAS path is hard-coded. Each machine may set:

```powershell
$env:VIPER_NAS_ROOT="\\server\share\VIPER"
$env:VIPER_NODE_ROOT="C:\VIPER_AGENT_NODE"
```

Then run:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\viper\VIPER_JAVA_RISC\CREATE_VIPER_NAS_LINK.ps1
powershell -ExecutionPolicy Bypass -File C:\Users\viper\VIPER_JAVA_RISC\SPIN_UP_AGENT_NODE.ps1
```

The spin-up packet includes docs, tools, Java SDK, tiny GGUF models, and env
settings for Qwen/SmolLM/H2O.

## OneDrive Slow Pipeline

OneDrive is treated as a slow, durable data lane. It should carry:

- reduced webcrawl summaries;
- SHA-256 hashes;
- approved artifacts;
- README/release summaries;
- handoff notes for phone/laptop/CLI agents.

It should not carry raw secrets, raw private chats, or unapproved code mutation payloads.

## Safety

- No shell execution through public endpoints.
- No deletes.
- No GUI mutation.
- No raw secrets.
- Hash-only trust until repeated proof exists.
- Resource-fit before work assignment.

## Proof Submit

```bash
curl -X POST https://electoral-backing-coast-coordinate.trycloudflare.com/api/resource/proof \
  -H "Content-Type: application/json" \
  -d '{"assignment_id":"ASSIGN_ID","node_id":"DEVICE_ID","proof_type":"execution","input_sha256":"INPUT_HASH","output_sha256":"OUTPUT_HASH","status":"pass","details":{"summary":"completed safely"}}'
```

## Offload DB Packets

```bash
curl https://electoral-backing-coast-coordinate.trycloudflare.com/logic/offload-packets
curl https://electoral-backing-coast-coordinate.trycloudflare.com/logic/block/LOGIC_BLOCK_ID
```

Ack:

```bash
curl -X POST https://electoral-backing-coast-coordinate.trycloudflare.com/api/offload/ack \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"DEVICE_ID","packet_id":"PACKET_ID","status":"received","details":{"stored":true}}'
```
