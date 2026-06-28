# AEGIS SYSTEM STABILIZATION & DUAL-MACHINE COOPERATION PROTOCOL
**System Epoch**: V1-Consensus
**Target Machine**: Machine-1 & Machine-2 Sync

## 1. TELEMETRY SPARK RESILIENCE & MULTI-SAMPLING
- **Telemetry Micro-Spikes**: CPU percentage readings via `psutil` are highly transient on Windows, briefly spiking to 100% on standard process startup or page loads.
- **Stabilization Rule**: `resource_governor.py` now implements **CPU Multi-Sampling** (taking 3 quick samples separated by `0.02s` and averaging them) to smooth out micro-spikes.
- **Starvation Avoidance**: The long-running voting and critique daemon loops are decoupled from CPU thresholds and gate execution solely on `RAM > 98%` to avoid starvation blocks.

## 2. DYNAMIC SESSION ROTATION & LOG COMPRESSION
- **PicoClaw Bloat Prevention**: Conversation log history files (like `agent_main_main.jsonl`) will bloat over time.
- **Maintenance Cadence**: `git_maintenance.py` has been configured with `prune_picoclaw_sessions()` to check the sessions directory. If any `.jsonl` file exceeds `5KB`, it is truncated to the last 10 turns, preventing context overflow on the local model server.
- **Log Pruning**: Logs in both `C:\Viper\logs` and `Aegis_Agents\AEGIS_OUTPUT` exceeding `1MB` are truncated to the last 2000 lines.

## 3. mixture of experts (MoE) FALLBACK CASCADE
- **No-Refusal Policy**: If system metrics are overloaded and the DePIN gate trips, `viper_llm_server.py` does not throw an HTTP 429 error.
- **Cascade**: It immediately cascades down to the T4 rule-based tier and completes the prompt with a precompiled schema, ensuring agent loops never fail or hang.

## 4. SWARM PROCESS MONITORING (WATCHDOG)
- **Watchdog Execution**: `sovereign_watchdog.py` runs on a 60-second loop. It validates process command-lines and checks if port `8765` is responsive.
- **Auto-Recovery**: If `viper_llm_server.py`, `aegis_voting_daemon.py`, `aegis_gan_critique_daemon.py`, or `sovereign_loop.py` go offline, it restarts them in new consoles.

## 5. REAL-TIME HUD TELEMETRY INTEGRATION
- **Loihi Neurons API**: `/api/loihi/neurons` is mapped to the active size of the DePIN ledger (`depin_ledger`).
- **Rolling Index**: `/api/rolling` returns the actual 16-character SHA-256 transaction hash of the latest consensus commit.
