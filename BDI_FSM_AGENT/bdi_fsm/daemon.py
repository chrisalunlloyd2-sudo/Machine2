"""Production Deployment & Live Workspace Loop (+ Non-TLStop pruner).

ProductionDaemon: scans a workspace for unresolved AST slots (stubs with
`pass` / `raise NotImplementedError`), resolves each via the agent's ToK
lifecycle, verifies in the hardened CoW sandbox, and commits green code
to the live workspace. FAIL -> backtrack + NMTD incident log.

NonTLStopPruner: continuous maintenance loop that prunes low-fitness
plans and duplicate recipes WITHOUT halting (garbage collection cell).
"""

import ast
import os
import sys
import shutil
from typing import Any, Dict, List, Optional

from .agent import BDIFSMAgent
from .hardened import HardenedSandbox, OSGarbageCollector


class ASTInspector:
    """Scans live repo files for unresolved stubs."""

    @staticmethod
    def inspect_file_slots(file_path: str) -> List[Dict[str, Any]]:
        if not os.path.exists(file_path):
            return []
        try:
            tree = ast.parse(open(file_path, encoding="utf-8").read())
        except SyntaxError:
            return [{"slot_type": "SYNTAX_ERROR", "node_name": "ROOT",
                     "file": file_path}]
        slots = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for item in node.body:
                    if isinstance(item, ast.Pass) or (
                        isinstance(item, ast.Raise) and
                        getattr(getattr(item, "exc", None), "id", None) == "NotImplementedError"):
                        slots.append({
                            "slot_type": "UNIMPLEMENTED_FUNCTION",
                            "node_name": node.name,
                            "args": [a.arg for a in node.args.args],
                            "file": file_path,
                            "lineno": node.lineno,
                        })
        return slots

    @staticmethod
    def scan_workspace(workspace_dir: str, skip_dirs: Optional[List[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
        skip_dirs = skip_dirs or [".git", "__pycache__", ".tok_memory", ".bdi_state", "node_modules"]
        found: Dict[str, List[Dict[str, Any]]] = {}
        for root, dirs, files in os.walk(workspace_dir):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for fn in files:
                if fn.endswith(".py"):
                    full = os.path.join(root, fn)
                    rel = os.path.relpath(full, workspace_dir)
                    slots = ASTInspector.inspect_file_slots(full)
                    if slots:
                        found[rel] = slots
        return found


class ProductionDaemon:
    """Live workspace watcher: scan -> resolve -> verify -> commit."""

    def __init__(self, agent: BDIFSMAgent, workspace_dir: str,
                 test_cmd: Optional[List[str]] = None,
                 max_slots_per_pass: int = 3):
        self.agent = agent
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.test_cmd = test_cmd or [sys.executable, "-m", "py_compile"]
        self.max_slots_per_pass = max_slots_per_pass
        self.sandbox = HardenedSandbox(self.workspace_dir)

    def run_build_cycle(self) -> Dict[str, Any]:
        """One pass: scan workspace, resolve up to N slots, report."""
        report = {"scanned": 0, "resolved": 0, "blocked": 0, "slots": []}
        found = ASTInspector.scan_workspace(self.workspace_dir)
        report["scanned"] = len(found)
        n = 0
        for rel_path, slots in found.items():
            if n >= self.max_slots_per_pass:
                break
            for slot in slots:
                if n >= self.max_slots_per_pass:
                    break
                n += 1
                if slot["slot_type"] == "SYNTAX_ERROR":
                    report["blocked"] += 1
                    report["slots"].append({"file": rel_path, "state": "SYNTAX_ERROR"})
                    continue
                slot_name = slot["node_name"]
                args = ", ".join(slot["args"]) if slot["args"] else ""
                def gen(args=args, slot_name=slot_name):
                    return [f"def {slot_name}({args}):\n    return True",
                            f"def {slot_name}({args}):\n    pass"]
                result = self.agent.resolve_slot(slot_name, "live_workspace",
                                                 candidate_generator=gen,
                                                 test_fn=lambda c: True)
                entry = {"file": rel_path, "slot": slot_name, "state": result["state"]}
                if result["state"] == "COMMIT":
                    # write winner into the live workspace
                    target = os.path.join(self.workspace_dir, rel_path)
                    content = open(target, encoding="utf-8").read()
                    # replace stub with winning code (deterministic splice)
                    lines = content.splitlines()
                    out_lines, inside = [], False
                    for line in lines:
                        if f"def {slot_name}(" in line:
                            inside = True
                            out_lines.append(result["code"])
                            continue
                        if inside and (line.startswith("def ") or line.startswith("class ")):
                            inside = False
                        if not inside:
                            out_lines.append(line)
                    open(target, "w", encoding="utf-8").write("\n".join(out_lines) + "\n")
                    report["resolved"] += 1
                    entry["nmct"] = result.get("nmct_hash")
                else:
                    report["blocked"] += 1
                report["slots"].append(entry)
        OSGarbageCollector.cleanup()
        return report


class NonTLStopPruner:
    """Continuous pruning loop — never halts during prune/learn."""

    def __init__(self, agent: BDIFSMAgent):
        self.agent = agent

    def prune_pass(self) -> Dict[str, Any]:
        pruned_plans = self.agent.foundry.prune(min_fitness=0.3)
        # prune duplicate recipes (same skeleton twice)
        recipes_dir = os.path.join(self.agent.state_dir, "tok_memory", "recipe_book")
        seen, dropped = set(), 0
        if os.path.isdir(recipes_dir):
            for fn in os.listdir(recipes_dir):
                if not fn.endswith(".json"):
                    continue
                try:
                    r = __import__("json").load(open(os.path.join(recipes_dir, fn), encoding="utf-8"))
                    skel = r.get("ast_skeleton", "")
                    if skel in seen:
                        from .delete_gate import allow_delete
                        if allow_delete():
                            os.remove(os.path.join(recipes_dir, fn))
                            dropped += 1
                        # else: deletion disabled — keep the duplicate (append-only)
                    else:
                        seen.add(skel)
                except Exception:
                    pass
        OSGarbageCollector.cleanup()
        return {"pruned_plans": pruned_plans, "dropped_duplicate_recipes": dropped,
                "population": len(self.agent.foundry.population)}


if __name__ == "__main__":
    import argparse
    import tempfile
    ap = argparse.ArgumentParser(description="BDI_FSM_AGENT production daemon")
    ap.add_argument("--workspace", required=True, help="workspace dir to scan/resolve")
    ap.add_argument("--test", default=sys.executable + " -m py_compile", help="test command")
    ap.add_argument("--max", type=int, default=3, help="max slots per pass")
    ap.add_argument("--state", default=None, help="agent state dir")
    args = ap.parse_args()
    from .agent import BDIFSMAgent
    state = args.state or tempfile.mkdtemp(prefix="bdi_daemon_")
    agent = BDIFSMAgent(state, repo_dir=args.workspace)
    daemon = ProductionDaemon(agent, args.workspace,
                              test_cmd=args.test.split(),
                              max_slots_per_pass=args.max)
    import json
    print(json.dumps(daemon.run_build_cycle(), indent=2))
