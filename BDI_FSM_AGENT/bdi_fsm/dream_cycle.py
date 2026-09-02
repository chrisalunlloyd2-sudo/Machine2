"""DREAM CYCLE — the agent's nightly sleep (maintenance).

At night the agent consolidates: dream-prune the journal (source coding ->
immutable long-term stability), GC low-fitness plans (NonTLStopPruner),
harvest self-sent emails (email cross-correlation -> corpus), and run the
triple learning loop (code + English self-training). The dream cycle is the
steady-state: it prunes exactly as much as it learns, so memory holds its
optimum size while progress continues.

Each stage is independently toggleable and failure-isolated — one failing
stage never blocks the others. Pure stdlib. Deterministic. Zero LLM.
ADD-only (pruning archives, never deletes).
"""
import time
from typing import Any, Dict, Optional

DREAM_CRON = "0 3 * * *"   # nightly at 03:00 local


def dream_cycle(agent, *, dream: bool = True, gc: bool = True,
                email: bool = True, self_train: bool = True,
                asymptotic: bool = True, linguistic: bool = True,
                seeds: bool = True, seed_token: str = "",
                email_dry_run: bool = True,
                dream_dry_run: bool = False) -> Dict[str, Any]:
    """Run the nightly maintenance and return a per-stage report."""
    report: Dict[str, Any] = {}
    if dream:
        try:
            report["dream"] = agent.dream(dry_run=dream_dry_run)
        except Exception as exc:
            report["dream"] = {"error": f"{type(exc).__name__}: {exc}"}
    if gc:
        try:
            from .daemon import NonTLStopPruner
            report["gc"] = NonTLStopPruner(agent).prune_pass()
        except Exception as exc:
            report["gc"] = {"error": f"{type(exc).__name__}: {exc}"}
    if email:
        try:
            report["email"] = agent.harvest_self_emails(dry_run=email_dry_run)
        except Exception as exc:
            report["email"] = {"error": f"{type(exc).__name__}: {exc}"}
    # digest repo facts -> Q&A into the chat corpus (Aegis v2: data in chats)
    try:
        report["digest"] = agent.digest_repos(dry_run=email_dry_run)
    except Exception as exc:
        report["digest"] = {"error": f"{type(exc).__name__}: {exc}"}
    if asymptotic:
        try:
            from .asymptotic import dream_asymptotic
            report["asymptotic"] = dream_asymptotic(agent, dry_run=email_dry_run)
        except Exception as exc:
            report["asymptotic"] = {"error": f"{type(exc).__name__}: {exc}"}
    if linguistic:
        try:
            report["linguistic"] = agent.linguistic_train()
        except Exception as exc:
            report["linguistic"] = {"error": f"{type(exc).__name__}: {exc}"}
    if self_train:
        try:
            report["self_train"] = agent.triple_learn_hourly(
                crawl=True, foundry=True, feature=True)
        except Exception as exc:
            report["self_train"] = {"error": f"{type(exc).__name__}: {exc}"}
    if seeds:
        try:
            from .seed_factory import run_nightly
            report["seeds"] = run_nightly(
                state_dir=os.path.join(agent.state_dir, "..") if agent.state_dir else "state",
                token=seed_token, dry_run=email_dry_run)
        except Exception as exc:
            report["seeds"] = {"error": f"{type(exc).__name__}: {exc}"}
    report["done"] = True
    return report


def nightly(agent, clock=None, now=None, **kw) -> Dict[str, Any]:
    """Run dream_cycle only if it's nighttime (the scheduled dream). Returns
    {ran: False, reason} when called outside the night window."""
    import datetime as dt
    from .scheduler import is_nighttime
    if now is None:
        ts = clock.now() if clock is not None else time.time()
        now = dt.datetime.fromtimestamp(ts)
    if not is_nighttime(now):
        return {"ran": False, "reason": "not nighttime", "hour": now.hour}
    return {"ran": True, **dream_cycle(agent, **kw)}

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
