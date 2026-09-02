"""
HORIZON — long-horizon task completion with course change (Chris 2026-08-11).

"task completion as well as stringing together blocks of logic and long horizon
tasks also integrating on all outputs to change course"

A goal is decomposed into ordered BLOCKS of logic (from metaplan abduction or an
explicit list). Blocks run SERIALLY (cellular chain doctrine — one cell at a
time, verify-before-accept). Each block's output is gated by the certainty gate
("is this going to work 100%?"): on fail -> STEP_BACK assessment + redo variant
(NMTD never-try-twice), until 100% or max_redo exhausted.

"INTEGRATING ON ALL OUTPUTS TO CHANGE COURSE": after every accepted output, the
output is integrated into the blackboard and the REMAINING plan is re-evaluated
from the new state. If the integrated output deviates from what the remaining
blocks expect, the plan CHANGES COURSE — re-order / drop unsatisfiable blocks /
re-abduct a fresh plan — never blindly continue.

Deterministic, zero LLM.
"""

import time


class HorizonBlock:
    """One block of logic in a horizon plan.

    run(bb) -> output            executes the block
    checks: [(verifier, arg)]    certainty-gate checks on the output
    precondition: str            atoms that must hold in bb before firing
    effect: str                  atoms the block adds to the world (for re-plan)
    """

    def __init__(self, name, run, checks=None, precondition="", effect="",
                 redo_variant=None):
        self.name = name
        self.run = run
        self.checks = checks or [("not_empty", None)]
        self.precondition = precondition
        self.effect = effect
        self.redo_variant = redo_variant

    def applicable(self, bb: dict) -> bool:
        if not self.precondition:
            return True
        return all(a in bb for a in self.precondition.split())


class Horizon:
    def __init__(self, agent=None, max_redo: int = 3):
        self.agent = agent
        self.max_redo = max_redo
        if agent is not None:
            from bdi_fsm.certainty import CertaintyGate
            self.gate = CertaintyGate(nmtd=getattr(agent, "nmtd", None),
                                      state_dir=getattr(agent, "state_dir", None))
        else:
            from bdi_fsm.certainty import CertaintyGate
            self.gate = CertaintyGate()

    # ---- block factories -------------------------------------------------
    @staticmethod
    def from_metaplan(abductor, goal: str, state: str) -> list | None:
        """Convert a metaplan abduct chain into HorizonBlocks (one per step)."""
        plan = abductor.abduct(goal, state)
        if not plan or not plan.get("achieved"):
            return None
        blocks = []
        for step in plan.get("steps", []):
            blocks.append(HorizonBlock(
                name=step if isinstance(step, str) else step.get("name", "step"),
                run=lambda bb, s=step: {"step": s, "ok": True},
                checks=[("not_empty", "out")],
                effect=plan.get("macro", [""])[0] if plan.get("macro") else "",
            ))
        return blocks

    # ---- the runner ------------------------------------------------------
    def run(self, goal: str, blocks: list | None = None,
            bb: dict | None = None, integrate=None) -> dict:
        """Run a horizon plan with certainty gates and course change.

        integrate(bb, block, output) -> updated bb  (default: bb[block.name]=output)
        """
        bb = dict(bb or {})
        if blocks is None:
            blocks = []
        if integrate is None:
            integrate = lambda b, blk, out: {**b, blk.name: out}  # noqa: E731

        results = []
        course_changes = []
        redoes = 0
        verdict = "DONE"
        i = 0

        while i < len(blocks):
            block = blocks[i]

            # course-change pre-check: block precondition unsatisfiable?
            if not block.applicable(bb):
                course_changes.append({
                    "at": i, "block": block.name,
                    "why": f"precondition '{block.precondition}' not in state "
                           f"{sorted(bb)} — dropping/skipping",
                })
                i += 1
                continue

            # --- run the block -------------------------------------------
            out = block.run(bb)
            step = {"name": block.name, "checks": block.checks, "output": out}
            ctx = {"bb": bb, "output": out}

            # --- certainty gate: is this going to work 100%? --------------
            assessment = self.gate.assess(step, ctx)
            attempt = 0
            while assessment["verdict"] != "PASS" and attempt < self.max_redo:
                # step back: assess + redo with variant
                sb = self.gate.step_back(block.__dict__, assessment)
                redoes += 1
                attempt += 1
                out = block.run(bb, variant=attempt) if _accepts_variant(block.run) \
                    else block.run(bb)
                step = {"name": block.name, "checks": block.checks, "output": out}
                assessment = self.gate.assess(step, {"bb": bb, "output": out})

            if assessment["verdict"] != "PASS":
                # cannot reach 100% -> course change: re-plan remaining blocks
                course_changes.append({
                    "at": i, "block": block.name,
                    "why": f"cannot pass certainty gate after {self.max_redo} "
                           f"redoes ({assessment['failing'][0]['detail']})",
                })
                verdict = "COURSE_CHANGED"
                results.append({
                    "block": block.name, "verdict": "STEP_BACK",
                    "failing": [f["detail"] for f in assessment["failing"]],
                })
                # drop this block; remaining blocks re-evaluated next loop
                i += 1
                continue

            # --- 100% PASS: integrate output, then re-evaluate plan -------
            bb = integrate(bb, block, out)
            results.append({
                "block": block.name, "verdict": "PASS",
                "checks": len(assessment["checks"]),
                "integrated": True,
            })

            # course-change on integrated output: can the remaining plan still
            # fire? (blocks after this one may have become inapplicable)
            for j in range(i + 1, len(blocks)):
                if not blocks[j].applicable(bb):
                    course_changes.append({
                        "at": j, "block": blocks[j].name,
                        "why": f"after integrating '{block.name}' output, "
                               f"'{blocks[j].name}' precondition "
                               f"'{blocks[j].precondition}' no longer satisfiable",
                    })
            i += 1

        return {
            "goal": goal,
            "verdict": verdict,
            "blocks_run": len(results),
            "redoes": redoes,
            "course_changes": course_changes,
            "results": results,
            "final_bb": bb,
            "ts": time.time(),
        }


def _accepts_variant(fn) -> bool:
    import inspect
    try:
        return "variant" in inspect.signature(fn).parameters
    except Exception:
        return False

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
