"""DUAL-STREAM LOGGER — engine JSON-L + human progress cards.

Chris directive 2026-08-12:
"Dual-stream logger: JSON-L for engine recovery and structured plain-text
progress cards for human reading. Trigger on state transitions, Nash
equilibrium, exceptions, bottlenecks."

Architecture:
  [BDI FSM Loop] --> [State Delta Capture] --+--> Append JSON-L (Engine Log)
                                              +--> Format Markdown/Text (Email/Display)

Engine stream (always writes):
  {"t":1723449900,"cycle":14028,"b":{"mem_mb":14.2,"lat_ms":1.2},
   "d":"lat_ms<1.0","i":"unroll_loop_v4","nash":0.94}

Human stream (throttled, triggered on):
  - Periodic: every N cycles (default 100)
  - State transition: Desire succeeds, fails, or Nash >= 0.95
  - Exception: error rate exceeds threshold

Pure stdlib. Zero LLM. Deterministic.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional


class DualStreamLogger:
    """Dual-stream logging: JSON-L engine log + human-readable progress cards."""

    def __init__(self, state_dir: str, human_interval: int = 100,
                 max_engine_lines: int = 5000, error_rate_threshold: float = 0.3):
        self.engine_log_path = os.path.join(state_dir, "engine_log.jsonl")
        self.human_log_path = os.path.join(state_dir, "human_log.md")
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)

        self.human_interval = human_interval
        self.max_engine_lines = max_engine_lines
        self.error_rate_threshold = error_rate_threshold

        self._cycle_count = 0
        self._last_human_cycle = 0
        self._error_count = 0
        self._error_window: List[bool] = []  # sliding window of ok/fail

    # ---- engine stream (JSON-L, always writes) -------------------------
    def log_cycle(self, cycle: int, beliefs: Dict[str, Any],
                  desire: str, intention: str, nash: float,
                  status: str = "RUNNING", meta: Optional[Dict] = None) -> Dict:
        """Write one JSON-L line to engine log. Always called."""
        entry = {
            "t": int(time.time()),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cycle": cycle,
            "b": beliefs,
            "d": desire,
            "i": intention,
            "nash": round(nash, 4),
            "status": status,
            "meta": meta or {},
        }
        with open(self.engine_log_path, "a") as f:
            f.write(json.dumps(entry, sort_keys=True) + "\n")
        self._cycle_count += 1
        self._prune_engine_log()
        return entry

    def log_error(self, cycle: int, error_type: str, detail: str,
                  nash: float = 0.0) -> Dict:
        """Log an error/exception to engine log."""
        self._error_count += 1
        self._error_window.append(True)
        if len(self._error_window) > 100:
            self._error_window = self._error_window[-100:]
        return self.log_cycle(
            cycle=cycle,
            beliefs={"error_type": error_type},
            desire="recover",
            intention=f"handle_{error_type}",
            nash=nash,
            status="ERROR",
            meta={"error_detail": detail[:500]}
        )

    def log_ok(self, cycle: int) -> None:
        """Track a successful cycle in the error window."""
        self._error_window.append(False)
        if len(self._error_window) > 100:
            self._error_window = self._error_window[-100:]

    def error_rate(self) -> float:
        """Sliding window error rate (last 100 cycles)."""
        if not self._error_window:
            return 0.0
        return sum(self._error_window) / len(self._error_window)

    # ---- human stream (throttled, trigger-based) -----------------------
    def maybe_format_human(self, cycle: int, status: str,
                           beliefs: Dict[str, Any], desire: str,
                           intention: str, nash: float,
                           force: bool = False,
                           desires_queue: Optional[List[str]] = None,
                           intention_history: Optional[List[str]] = None,
                           hash_sig: str = "") -> Optional[str]:
        """Return formatted human card if threshold met, else None.

        Triggers:
          - force=True (terminal state: Nash >= 0.95, desire done/failed)
          - Periodic: cycle - last_human_cycle >= human_interval
          - Exception: error_rate() > error_rate_threshold
        """
        trigger = ""

        if force:
            trigger = "terminal"
        elif (cycle - self._last_human_cycle) >= self.human_interval:
            trigger = "periodic"
        elif self.error_rate() > self.error_rate_threshold:
            trigger = "exception"

        if not trigger:
            return None

        self._last_human_cycle = cycle
        return self._format_card(
            cycle=cycle, status=status, beliefs=beliefs,
            desire=desire, intention=intention, nash=nash,
            trigger=trigger, desires_queue=desires_queue or [],
            intention_history=intention_history or [],
            hash_sig=hash_sig
        )

    def force_human(self, cycle: int, status: str,
                    beliefs: Dict[str, Any], desire: str,
                    intention: str, nash: float,
                    desires_queue: Optional[List[str]] = None,
                    intention_history: Optional[List[str]] = None,
                    hash_sig: str = "") -> str:
        """Always format a human card (terminal event)."""
        card = self._format_card(
            cycle=cycle, status=status, beliefs=beliefs,
            desire=desire, intention=intention, nash=nash,
            trigger="terminal", desires_queue=desires_queue or [],
            intention_history=intention_history or [],
            hash_sig=hash_sig
        )
        self._last_human_cycle = cycle
        return card

    def _format_card(self, cycle: int, status: str,
                     beliefs: Dict[str, Any], desire: str,
                     intention: str, nash: float,
                     trigger: str = "",
                     desires_queue: Optional[List[str]] = None,
                     intention_history: Optional[List[str]] = None,
                     hash_sig: str = "") -> str:
        """Build the structured plain-text progress card."""
        lines = []
        # ---- HEADER ----
        nash_display = f"{nash:.2f}/1.00"
        lines.append(f"STATUS: [{status}] | Intention: {intention}")
        lines.append(f"Cycle: #{cycle} | Hash: {hash_sig[:8] or 'n/a'} | Nash Score: {nash_display}")
        lines.append(f"Trigger: {trigger} | Error Rate: {self.error_rate():.3f}")
        lines.append("")

        # ---- BELIEFS ----
        lines.append("[BELIEFS] (Environment & Constraints)")
        if beliefs:
            for k, v in sorted(beliefs.items()):
                lines.append(f"- {k}: {v}")
        else:
            lines.append("- (no beliefs recorded)")
        lines.append("")

        # ---- DESIRES ----
        lines.append("[DESIRES] (Goal Queue)")
        queue = desires_queue or ([desire] if desire else [])
        for d in queue:
            marker = ">" if d == intention else " "
            lines.append(f"- [{marker}] {d}")
        if not queue:
            lines.append("- (empty)")
        lines.append("")

        # ---- CURRENT INTENTION ----
        lines.append("[CURRENT INTENTION]")
        lines.append(f"- {intention}")
        if intention_history:
            lines.append("  Recent history:")
            for h in intention_history[-5:]:
                lines.append(f"    -> {h}")
        lines.append("")

        # ---- FOOTER ----
        lines.append(f"Engine log: {self._cycle_count} cycles recorded")
        lines.append(f"Errors: {self._error_count} total ({self.error_rate():.1%} recent)")
        card = "\n".join(lines)

        # Append to human log file
        with open(self.human_log_path, "a") as f:
            f.write(f"\n--- Cycle #{cycle} ({time.strftime('%Y-%m-%d %H:%M:%S')}) ---\n")
            f.write(card + "\n")

        return card

    # ---- maintenance ---------------------------------------------------
    def _prune_engine_log(self) -> None:
        """Keep engine log bounded — drop oldest lines when over max."""
        if not os.path.exists(self.engine_log_path):
            return
        try:
            with open(self.engine_log_path) as f:
                lines = f.readlines()
            if len(lines) > self.max_engine_lines:
                keep = lines[-self.max_engine_lines:]
                with open(self.engine_log_path, "w") as f:
                    f.writelines(keep)
        except Exception:
            pass

    def read_human_log(self, tail: int = 5) -> str:
        """Return last N human cards for display."""
        if not os.path.exists(self.human_log_path):
            return "(no human log yet)"
        with open(self.human_log_path) as f:
            content = f.read()
        blocks = content.split("\n--- Cycle #")
        if len(blocks) <= 1:
            return content
        recent = blocks[-tail:]
        return "--- Cycle #" + "--- Cycle #".join(recent)

    def stats(self) -> Dict[str, Any]:
        """Return logger statistics."""
        engine_size = 0
        human_size = 0
        if os.path.exists(self.engine_log_path):
            engine_size = os.path.getsize(self.engine_log_path)
        if os.path.exists(self.human_log_path):
            human_size = os.path.getsize(self.human_log_path)
        return {
            "cycles": self._cycle_count,
            "errors": self._error_count,
            "error_rate": self.error_rate(),
            "human_cards_written": self._last_human_cycle,
            "engine_log_bytes": engine_size,
            "human_log_bytes": human_size,
            "human_interval": self.human_interval,
        }

# LOCATIONS - this file lives in more than one place
#
#   live:  C:\Viper\projects\BDI_FSM_AGENT
#          -> C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#   mirror: J:\ViperVault\code\projects\BDI_FSM_AGENT
#   mirror: C:\Users\viper\gan-otg-db\BDI_FSM_AGENT
#
#   live detail (freshness, git coverage): docs\LOCATIONS.md
#   regenerate: python location_stamp.py apply
# end LOCATIONS
