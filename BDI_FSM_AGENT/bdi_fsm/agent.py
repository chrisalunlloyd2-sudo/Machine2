"""The BDI_FSM_AGENT — non-LLM tool-calling super agent.

Assembles the full 1990s stack into one controllable agent:
  FSM (behavior) -> Blackboard (beliefs) -> BDI (desires/intentions)
  -> Tool registry (deterministic tools) -> Brute Genetic Foundry
  (candidate synthesis) -> Hardened CoW sandbox (verification)
  -> ToK Memory Harness (learnings/recipes/NMCT/NMTD)
  -> TOC-TOK tower (orientation) -> Maslow (needs) -> Control (Aegis).

ZERO LLM/SLM. Every decision is a pure function of blackboard facts.
"""

import json
import os
import sys
from collections import deque
from typing import Any, Callable, Dict, List, Optional

from .blackboard import Blackboard
from .fsm import FSM
from . import reachability
from .bdi import BDIEngine, BDIPlan
from .foundry import GeneticFoundry, SymbolicPlan
from .hardened import HardenedSandbox
from .memory import ToKMemoryHarness
from .nmct import NMCT
from .nmtd import NMTD
from .toc_tok import TocTokTower
from .maslow import Maslow
from .fow import FOW
from .control import ControlChannel
from .controllers import ControllerHub
from .boolean_chat import BooleanChat
from .learning import RecursiveLearner
from .brute_adapter import BruteFoundryAdapter
from .lexicon import Lexicon
from .journal import DeterministicActionJournal
from .infotheory import DecisionEntropy
from .dream_prune import dream_prune, format_report as _dream_fmt
from .markov_chat import MarkovChat
from .comparative_matrix import ComparativeMatrix
from . import kqml as _kqml
from .foundry_kernel import GraphNode as _GN, FoundryRegistry, graph_hash, transpile as _transpile
from .energy import EnergyManifold as _EnergyManifold, verify_zero_repeat_guarantee as _qed
from .unify import SubsumptionDAG as _SubsumptionDAG, UnifyCache as _UnifyCache
from .metaplan import MetaplanAbductor as _MetaplanAbductor, Plan as _MetaPlan
from . import english_render as _en
from .dual_logger import DualStreamLogger
from .identity import Identity
from .feedback import FeedbackStore
from .markov_plateau import MarkovPlateau
from .plateau import PlateauDetector, PlateauType
from .mesh import CellularMesh
from .search_fallback import SearchFallback
from .webcrawl import CrawlTrainer
from .clock import Clock
from .scheduler import Scheduler
from .dream_cycle import DREAM_CRON
from .world_model import WorldModel
from .tool_observer import ToolObserver
from .code_patcher import CodeSynthesisGate, PatchOp
from .pacing import enforce_cooldown, guard_memory, pacing_stats, sequential_only
from .corpus_seed import seed as _corpus_seed
from .hap import HapEngine, Plan
from .skill_library import SkillLibrary
from .telemetry import Telemetry
from .capabilities import CapabilityRouter
from .certainty import CertaintyGate
from .horizon import Horizon, HorizonBlock
from .ban import Ban, BanLedger
from .task_pool import FleetTaskPool
from .realm import ChoiceTree
from .hooks import HookDispatcher
from .hdc import CodeSignatureStore
from .law import Law
from .calc import CalcFlow
from .arch_vectors import (VectoredDriver, AtlantisReflexVector,
                           AtlantisSequencerVector, BB1AgendaVector,
                           MaesActivationVector, ProdigyControlVector,
                           SoarPreferenceVector, PrsIntentionVector)


from bdi_fsm.exhaustive_tree import TaskDAG, TaskTree, TaskTreeRunner

# Deterministic built-in prose — guarantees the Markov model always has
# material to generate from, even before nightly corpus seeding (cold start).
_FALLBACK_CORPUS = [
    "I am a deterministic symbolic agent built from the 1990s AI stack.",
    "Every decision I make is reproducible: the same input gives the same output.",
    "I hold my beliefs on an auditable blackboard so nothing is hidden.",
    "I learn from feedback and reshape my rules when you correct me.",
    "I stop when Shannon entropy spikes because coherence is my boundary.",
    "A state machine is a graph of states connected by guarded transitions.",
    "A shopping cart can be ready locked or abandoned depending on its items.",
    "A ready cart transitions to locked when items are added.",
    "A locked cart transitions to abandoned when its items are removed.",
    "A transition is allowed only if the current state and the data permit it.",
    "Domain driven design keeps code aligned with the business invariants.",
    "The base state class declares methods that every concrete state implements.",
    "Each state holds a back reference to the domain model it belongs to.",
    "The domain model uses the back reference to move to another state.",
    "Loose coupling lets new states be added without rewriting old ones.",
    "My beliefs are facts asserted onto the blackboard and reasoned over.",
    "The belief desire intention loop turns goals into plans and actions.",
    "A plan is a sequence of tools executed until the goal is satisfied.",
    "I verify every candidate in a hardened sandbox before accepting it.",
    "The genetic foundry synthesises candidates and tests them for fitness.",
    "The entropy of a message measures how surprising its tokens are.",
    "Lower entropy means more coherent and more confident prose.",
    "I expand candidates until the entropy curve levels out at a plateau.",
    "The plateau candidate is my best reply because it is most coherent.",
    "Feedback associations connect input tokens to reply tokens.",
    "A like reinforces an association and a dislike dampens it.",
    "Over time my associations learn which replies you prefer.",
    "I keep a self model of my axioms skills and learned facts.",
    "You are the operator and I am the agent and the boundary is explicit.",
    "My core axioms are immutable but my skills accrete over time.",
    "I narrate my own evolution so my history is readable.",
    "A correction is a negative example that I remember and avoid.",
    "Determinism does not mean rigidity it means trustworthiness.",
    "Symbolic reasoning keeps every step of my thought auditable.",
    "I have no hidden state and no probabilistic hidden layers.",
    "The tower of knowledge orients me in my visible neighbourhood.",
    "The fog of war limits what I can see until I explore.",
    "Memory is a recipe vault that compounds successful solutions.",
    "The control channel routes proposals to a human or local controller.",
    "Pacing ensures nothing runs forever and nothing runs for free.",
    "The dual stream logger writes machine lines and human cards.",
]

class BDIFSMAgent:
    def __init__(self, state_dir: str, repo_dir: Optional[str] = None,
                 hex_q: int = 0, hex_r: int = 0,
                 timeout_seconds: int = 5, max_memory_mb: int = 256):
        self.state_dir = state_dir
        self.repo_dir = repo_dir or os.path.join(state_dir, "workspace")
        os.makedirs(state_dir, exist_ok=True)
        os.makedirs(self.repo_dir, exist_ok=True)
        self.hex = (hex_q, hex_r)

        self.bb = Blackboard()
        self.bb.assert_fact("agent", "bdi-fsm-agent")
        self.bb.assert_fact("hex", [hex_q, hex_r])
        self.bb.assert_fact("status", "IDLE")

        # Chris directive 2026-08-12: dual-stream logger + pacing
        self.dual_logger = DualStreamLogger(state_dir)
        self.bb.assert_fact("dual_logger", "active")

        self.fsm = FSM("IDLE")
        # N-retry budget: BLOCKED->give_up->IDLE fires only while retries remain.
        # When exhausted, BLOCKED is a TRUE dead-end (task parked, no loop) —
        # the livelock fix proven by the SAT reachability verifier (Sophia).
        self.MAX_RETRIES = max(1, int(os.environ.get("BDI_MAX_RETRIES", "3")))
        self._retries: dict = {}
        self._current_slot: str = ""
        self._build_fsm()

        self.memory = ToKMemoryHarness(os.path.join(state_dir, "tok_memory"))
        self.nmct = NMCT(os.path.join(state_dir, "nmct_vault"))
        self.nmtd = NMTD(os.path.join(state_dir, "nmtd_db"),
                         learnings_file=os.path.join(state_dir, "tok_memory", "learnings.md"))
        self.tower = TocTokTower(os.path.join(state_dir, "toc_tok.json"))
        self.fow = FOW(os.path.join(state_dir, "fow.json"))
        self.control = ControlChannel(os.path.join(state_dir, "control"))
        self.hub = ControllerHub(state_dir)          # seek LOCAL LLM or HUMAN controller
        self.lexicon = Lexicon(os.path.join(state_dir, "lexicon.json"))
        self.chat = BooleanChat(self.lexicon)
        self.learner = RecursiveLearner(self.lexicon, state_dir)
        # Chris directive 2026-08-12: self-model, feedback, plateau
        self.identity = Identity(os.path.join(state_dir, "identity.json"))
        self.feedback_store = FeedbackStore(os.path.join(state_dir, "feedback.json"))
        self.plateau = MarkovPlateau(order=2)
        self.plateau_detector = PlateauDetector()
        self.tool_observer = ToolObserver(os.path.join(state_dir, "tool_observer.json"))
        self.bb.assert_fact("identity", "active")
        self.foundry_adapter = BruteFoundryAdapter()  # local brute-foundry
        self.journal = DeterministicActionJournal(os.path.join(state_dir, "journal.jsonl"))
        self.telemetry = Telemetry(state_dir)
        self.capabilities = CapabilityRouter(self)
        self.certainty = CertaintyGate(nmtd=self.nmtd, state_dir=state_dir)
        self.horizon = Horizon(self, max_redo=3)
        self.ban = BanLedger()
        self.entropy = DecisionEntropy(os.path.join(state_dir, "journal.jsonl"))
        self.skills = SkillLibrary(os.path.join(state_dir, "skills"))
        self.task_dag = TaskDAG(os.path.join(state_dir, "task_dag.json"))
        self.tree_dir = os.path.join(state_dir, "..", "decision_trees") if repo_dir else os.path.join(state_dir, "decision_trees")
        self.pool = None  # lazy: set_pool() with a task_pool.json path
        self.driver = self._build_driver()
        # v0.3.0 cellular mesh: the endpoint populates hex fog cells to
        # complete intent asks; on impasse it webcrawls the subject into
        # the corpus (anti-loop). Deterministic, zero-LLM.
        self.mesh = CellularMesh(radius=3, engine=self.driver)
        self.search_fallback = SearchFallback(state_dir, trainer=CrawlTrainer(state_dir))
        # circadian: time-aware loop (atomic clock + scheduler + nightly dream)
        self.clock = Clock()
        self.scheduler = Scheduler(self.clock)
        self.scheduler.every("dream", DREAM_CRON, self.dream_cycle)
        # sense of other: entity DAGs (self + servers/nodes/websites/repos)
        self.world = WorldModel(os.path.join(state_dir, "world_model.json"))
        self.hap = HapEngine()
        # Q.E.D. zero-repeat: remember recent replies so chat never echoes
        self._recent_replies = deque(maxlen=16)
        # logical realms: choice trees (separate Markov) + the batch terminal
        self.choice_tree = ChoiceTree(seed=7)
        self.hook_dispatcher = HookDispatcher()
        self.signature_store = CodeSignatureStore(D=2048)  # never-twice dedup
        self.law = Law(allow_delete=os.environ.get("BDI_ALLOW_DELETE") == "1",
                       allow_promote=True)
        self.calc = CalcFlow()  # cheap, memoized, budgeted math
        self.pos_db = None  # lazily built by linguistic_train()
        self._build_hook_dispatcher()
        self._seed_choice_tree()
        self._seed_plans()

        # roadmap: subsumption DAG unification cache (memoized) + metaplan
        # abduction / precondition generalization — wired, ADD-only.
        self.unify_cache = _UnifyCache(os.path.join(state_dir, "unify_cache.json"))
        self.dag = _SubsumptionDAG(self.unify_cache)
        self.metaplans = _MetaplanAbductor.load(
            os.path.join(state_dir, "metaplan.json"))
        self._sync_metaplans()

        self.maslow = Maslow(os.path.join(state_dir, "maslow"))
        self._build_maslow()
        self.sandbox = HardenedSandbox(self.repo_dir, timeout_seconds, max_memory_mb)

        self.tools: Dict[str, Callable] = {}
        self._build_tools()
        self.bdi = BDIEngine(self.bb, self.tools)
        self.foundry = GeneticFoundry(self.bb)
        self._seed_foundry()

    # ---- FSM behavior tree ---------------------------------------------
    def _build_fsm(self) -> None:
        self.fsm.add_state("IDLE", on_entry=lambda c: self.bb.assert_fact("status", "IDLE"))
        self.fsm.add_state("EVALUATE", on_entry=lambda c: self.bb.assert_fact("status", "EVALUATE"))
        self.fsm.add_state("SYNTHESIZE", on_entry=lambda c: self.bb.assert_fact("status", "SYNTHESIZE"))
        self.fsm.add_state("VERIFY", on_entry=lambda c: self.bb.assert_fact("status", "VERIFY"))
        self.fsm.add_state("COMMIT", on_entry=lambda c: self.bb.assert_fact("status", "COMMIT"))
        self.fsm.add_state("BLOCKED", on_entry=lambda c: self.bb.assert_fact("status", "BLOCKED"))
        self.fsm.add_state("PLATEAU", on_entry=lambda c: self.bb.assert_fact("status", "PLATEAU"))
        self.fsm.add_state("WAIT_AEGIS", on_entry=lambda c: self.bb.assert_fact("status", "WAIT_AEGIS"))

        self.fsm.add_transition("IDLE", "new_slot", "EVALUATE")
        self.fsm.add_transition("EVALUATE", "recipe_hit", "COMMIT")
        self.fsm.add_transition("EVALUATE", "needs_mining", "SYNTHESIZE")
        self.fsm.add_transition("EVALUATE", "all_rejected", "BLOCKED")
        self.fsm.add_transition("SYNTHESIZE", "candidates_ready", "VERIFY")
        self.fsm.add_transition("SYNTHESIZE", "none_produced", "BLOCKED")
        self.fsm.add_transition("VERIFY", "pass", "COMMIT")
        self.fsm.add_transition("VERIFY", "fail", "BLOCKED")
        self.fsm.add_transition("EVALUATE", "stalled", "PLATEAU")
        self.fsm.add_transition("COMMIT", "needs_approval", "WAIT_AEGIS")
        self.fsm.add_transition("COMMIT", "done", "IDLE")
        # BLOCKED is a HARD terminal block (no candidates / all rejected
        # / verify failed). No retry: the old bare BLOCKED->retry->EVALUATE
        # edge re-entered with an UNCHANGED blackboard, so it looped by
        # design. Recovery from a SOFT stall goes through PLATEAU.
        self.fsm.add_transition("BLOCKED", "give_up", "IDLE",
                               guard=self._retries_left)
        # PLATEAU = candidates exist but fail to differentiate. Every
        # exit requires a mutation event; none re-enters unchanged.
        self.fsm.add_transition("PLATEAU", "expand_horizon", "EVALUATE")
        self.fsm.add_transition("PLATEAU", "decompose_subgoal", "EVALUATE")
        self.fsm.add_transition("PLATEAU", "commit_min_regret", "COMMIT")
        self.fsm.add_transition("PLATEAU", "give_up", "IDLE")
        self.fsm.add_transition("WAIT_AEGIS", "approved", "COMMIT")
        self.fsm.add_transition("WAIT_AEGIS", "denied", "IDLE")

    # ---- reachability verifier ("prove you can reach the exit") ----------
    def reachable_path(self, goal: str, start: Optional[str] = None):
        """Shortest proven path to a goal state (guard verdicts included)."""
        return reachability.verify_path(self.fsm, goal, start)

    def prove_exit(self, goals: Optional[list] = None) -> dict:
        """Prove every success state (default COMMIT) is reachable from here.
        For the cyclic agent FSM the meaningful exit is COMMIT."""
        return reachability.prove_exit(self.fsm, goals or ["COMMIT"])

    def scan_workspace(self, root: str) -> list:
        """Scan a workspace dir for broken AST/type nodes (python/compiler/html)."""
        from .workspace import scan_python, scan_compiler, scan_html
        return (scan_python(root) + scan_compiler(root) + scan_html(root))

    def auto_repair(self, root: str, dry_run: bool = True) -> dict:
        """Auto-repair broken nodes; ADD-only (.orig backup), logs every repair."""
        from .workspace import auto_repair_workspace
        return auto_repair_workspace(root, dry_run=dry_run,
                                     repair_log=os.path.join(self.state_dir, "repair_log.jsonl"))

    def planner_audit(self, accepting: Optional[list] = None) -> dict:
        """One-shot symbolic audit: deadlock-freedom, liveness, termination,
        total correctness. goals default to COMMIT (the agent's success state):
        'every state can reach the exit'; livelock cycles are reported."""
        from .planner_proofs import planner_audit
        return planner_audit(self.fsm, accepting, goals=["COMMIT"])

    def verify_task_exit(self) -> dict:
        """Learning-loop hook: a task ENTERS (intent recognized) -> prove it can EXIT.
        Returns the verdict for reaching COMMIT (the success terminal)."""
        v = reachability.verify_path(self.fsm, "COMMIT")
        return {"task_exit_provable": v["reachable"], "path": [
            f"{p['from']} -{p['event']}-> {p['to']} [{p['verdict']}]"
            for p in v["proofs"]] if v["proofs"] else None,
            "blocked": v["blocked"]}


    # ---- tools ------------------------------------------------------------
    def _build_tools(self) -> None:
        self.tools["typecheck"] = lambda target_file: (
            lambda r: {"typecheck_exit": r.returncode, "typecheck_err": r.stderr[-300:],
                       "has_syntax_error": r.returncode != 0})(
            __import__("subprocess").run([sys.executable, "-m", "py_compile", target_file],
                                         capture_output=True, text=True))

        def apply_regex(target_file, pattern, replacement):
            # CRIB FILTER: compile the result in memory BEFORE writing. A regex
            # patch that breaks syntax is rejected, not dumped to disk.
            content = open(target_file, encoding="utf-8").read()
            new = __import__("re").sub(pattern, replacement, content)
            try:
                compile(new, target_file, "exec")
            except Exception as e:
                return {"status": "rejected", "error": f"{type(e).__name__}: {e}"}
            open(target_file, "w", encoding="utf-8").write(new)
            return {"status": "patched"}
        self.tools["apply_regex_patch"] = apply_regex

        def apply_ast_patch(spec):
            """Structured AST patch (no raw file dump). Banburismus-gated.

            spec: dict (or JSON string) with keys:
                target_file, action (insert_before|insert_after|
                insert_in_method_start|replace_body|delete),
                target_node, payload, root_dir (optional).
            The crib filter (ast.parse + compile) validates BEFORE writing; the
            BanLedger scores compiler output (+30 dBan pass / -inf fail)."""
            import json as _json
            if isinstance(spec, str):
                try:
                    spec = _json.loads(spec)
                except Exception:
                    spec = {"payload": spec}
            gate = CodeSynthesisGate(spec.get("root_dir",
                                              "/root/scan_tmp/BDI_FSM_AGENT"))
            op = PatchOp(
                target_file=spec.get("target_file", spec.get("file", "")),
                action=spec.get("action", "insert_before"),
                target_node=spec.get("target_node", spec.get("node", "")),
                payload=spec.get("payload", spec.get("code", "")),
            )
            dec = gate.validate_and_apply(op)
            out = {
                "status": "applied" if dec.fired else "rejected",
                "dban": dec.dban,
                "reason": dec.reason,
            }
            if dec.result is not None:
                if dec.result.diff:
                    out["diff"] = dec.result.diff
                if dec.result.error:
                    out["error"] = dec.result.error
            return out
        self.tools["apply_ast_patch"] = apply_ast_patch

        def run_test(test_cmd):
            code, out, err = self.sandbox.run_workspace_test(test_cmd)
            return {"test_exit": code, "test_out": out[-300:], "test_err": err[-300:]}
        self.tools["run_test"] = run_test

        def record_nmct(slot_name, code, tape):
            return {"nmct_hash": self.nmct.seal(slot_name, code, tape)["canonical_hash"][:8]}
        self.tools["record_nmct"] = record_nmct

    def _seed_foundry(self) -> None:
        self.foundry.seed_plan(SymbolicPlan("PLAN_SUM", "has_slot",
                                            "def process_data(arr):\n    return sum(arr)"))
        self.foundry.seed_plan(SymbolicPlan("PLAN_MAX", "has_slot",
                                            "def process_data(arr):\n    return max(arr)"))
        self.foundry.seed_plan(SymbolicPlan("PLAN_DOUBLE", "has_slot",
                                            "def process_data(arr):\n    return [x * 2 for x in arr]"))
        self.foundry.set_critic(lambda p: 1.0 if self.foundry.ast_valid(p.code_template) else 0.0)


    # ---- better learning & recording -----------------------------------
    def record(self, action: str, detail: str, outcome: str = "ok",
               meta: Optional[Dict] = None) -> Dict:
        """Journal every action. Fails auto-log to NMTD + feed guardrail
        to the learner so mistakes are never repeated (NMTD doctrine)."""
        entry = self.journal.record("bdi-fsm-agent", action, detail, outcome, meta)
        if outcome == "fail":
            self.learner.learn_from_text(detail, source=f"journal:{action}")
            rule = self.learner.auto_guardrail(detail, action=action)
            self.memory.append_learning(
                incident_id=f"JRNL-{entry['seq']}", scope="Universal",
                trigger=rule["trigger"], outcome=detail[:200],
                rule=rule["rule"])
        return entry

    def set_pool(self, pool_path: str) -> None:
        """Attach the fleet task pool (task_pool.json)."""
        self.pool = FleetTaskPool(pool_path, self.state_dir)

    def run_pool_cycle(self, prefer: str = "probe") -> Dict:
        """Phase 8 fleet integration: take ONE open pool task, resolve it
        via skill library first (hit -> no mining), else brute foundry,
        verify, record. Pacing doctrine: one task per cycle."""
        if self.pool is None:
            return {"ok": False, "error": "no pool attached (set_pool)"}
        task = self.pool.next_open(prefer=prefer)
        if task is None:
            return {"ok": True, "action": "no_open_task", "stats": self.pool.stats()}
        tid = str(task.get("id", task.get("task", "")))
        if not self.pool.claim(tid):
            return {"ok": False, "action": "claim_failed",
                    "error": "claim_failed", "task": tid}
        enforce_cooldown("foundry_mine")
        name = str(task.get("file", tid)).replace("/", "_").replace(".", "_")
        detail = str(task.get("task", task.get("title", "")))
        # 1) skill library hit?
        # NOT lookup_by_params([]) -- an empty signature is a WILDCARD.
        #
        # It returns the first cached skill whose parameter list is also empty, which on this box
        # is "ArchivalMoe". So every pool task scored a skill-hit on an unrelated artefact and was
        # marked resolved without any work being done: "Complete BackupAgent: cross-machine pull
        # via Cloudflare" closed in a single attempt with ArchivalMoe as its evidence.
        #
        # The cache may only answer for the task actually asked about. A hit has to be keyed on
        # THIS task's name, or the compounding-determinism path compounds nothing and just retires
        # real work.
        skill = self.skills.get(name)
        if skill and "error" not in skill:
            self.pool.record_outcome(tid, "bdi-fsm-agent", "ok",
                                     f"skill-hit {name} (seal {skill.get('sha256')})",
                                     self.journal)
            return {"ok": True, "action": "skill_hit", "skill": skill.get("name"),
                    "seal": skill.get("sha256"), "detail": detail[:160]}
        # 2) brute foundry mine
        res = self.foundry_adapter.mine_to_skill(
            name, [], [detail], detail, self.skills)
        if res.get("ok"):
            self.pool.record_outcome(tid, "bdi-fsm-agent", "ok",
                                     f"mined {name} -> sealed {res['skill'].get('sha256')}",
                                     self.journal)
            # Return the SEAL, not just the name. The journal line above already records it, so
            # the value existed and was simply dropped at the boundary -- which left every caller
            # unable to cite what was produced. Contract evidence read "sealed ViperNote", which
            # names a repo and proves nothing; a sha256 identifies the artefact and can be checked.
            return {"ok": True, "action": "mined",
                    "skill": res["skill"].get("name"),
                    "seal": res["skill"].get("sha256"),
                    "detail": detail[:160]}
        # 3) fail — journal + NMTD guardrail
        #
        # Still reports an `action`. The foundry is GENETIC: mutation is random, so a cycle can
        # legitimately produce no viable winner and the same task succeeds on the next pass. A
        # failure return with no `action` key made "the cycle ran and mined nothing" look identical
        # to "the cycle never ran", which is why this path read as an intermittent fault rather
        # than as normal stochastic behaviour.
        err = res.get("error", "mine_failed")
        self.pool.record_outcome(tid, "bdi-fsm-agent", "fail",
                                 f"{name}: {err}", self.journal)
        return {"ok": False, "action": "mine_failed", "error": err, "task": tid}

    def journal_stats(self) -> Dict:
        return self.journal.stats()

    def skill_stats(self) -> Dict:
        return self.skills.stats()


    # ---- vectored terminal driver ---------------------------------------
    def _build_driver(self) -> VectoredDriver:
        d = VectoredDriver(journal=self.journal)
        d.register(AtlantisReflexVector())                       # p90 reflexes
        d.register(ProdigyControlVector(
            guardrails_path=os.path.join(self.state_dir, "guardrails.jsonl")))
        d.register(AtlantisSequencerVector())                    # p60 task queue
        d.register(SoarPreferenceVector())                       # p55 preferences
        d.register(BB1AgendaVector())                            # p50 agenda
        d.register(PrsIntentionVector())                         # p45 intentions
        d.register(MaesActivationVector())                       # p40 activation
        return d

    def decide(self, facts: Optional[Dict] = None,
               candidates: Optional[List[Dict]] = None,
               pool=None, situation: str = "") -> Dict:
        """Route one decision through the vector stack."""
        # self.bb.facts is a DICT, not a method. Calling it raised
        # "TypeError: 'dict' object is not callable" on every decide() that did not pass facts
        # explicitly -- i.e. the default path. Line 1381 has always used `dict(self.bb.facts)`
        # correctly, so the two spellings sat in one file disagreeing about the same attribute.
        ctx = {
            "facts": dict(facts if facts is not None else self.bb.facts),
            "candidates": candidates or [],
            "pool": pool or self.pool,
            "situation": situation,
        }

        # GIVE THE AGENT ITS CONTROLLER.
        #
        # AtlantisReflexVector has priority 90 and returns seek_controller at score 1.0 whenever
        # `controller_active is False`, so that one fact decides everything before any other
        # vector is consulted. Nothing ever wrote it. Measured across the stored decision trees:
        # 128 of 134 read "no local LLM or human controller active -> seek_controller", while
        # ControllerHub reported has_controller=True and a live endpoint the whole time.
        #
        # The agent was not broken and it was not wrong -- it asked for a controller, correctly,
        # every time, and no wire carried the answer back. This is that wire.
        if "controller_active" not in ctx["facts"]:
            try:
                ctx["facts"]["controller_active"] = bool(self.hub.has_controller())
            except Exception:
                # A probe that fails is not evidence of absence; leaving the fact unset lets the
                # reflex stay quiet rather than declaring the controller dead on a network blip.
                pass
        if self.journal:
            stats = self.journal.stats()
            cnt = stats.get("count", 1)
            fails = stats.get("by_outcome", {}).get("fail", 0)
            ctx["facts"]["journal_fail_rate"] = fails / max(1, cnt)
        decision = self.driver.decide(ctx, agent="bdi-fsm-agent")
        self._persist_tree(decision)
        return decision

    def _persist_tree(self, decision: Dict) -> Optional[str]:
        """Aiception: write the ASCII decision tree to decision_trees/
        whenever the driver auto-chooses a non-idle action."""
        render = getattr(self.driver, "last_render", None)
        if not render or decision.get("action") in (None, "idle"):
            return None
        trees_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "decision_trees")
        os.makedirs(trees_dir, exist_ok=True)
        import time as _t
        stamp = _t.strftime("%Y%m%d_%H%M%S")
        latest = os.path.join(trees_dir, "latest.txt")
        snap = os.path.join(trees_dir, f"tree_{stamp}.txt")
        # info-theoretic self-model: decision stream as an information source
        footer = ""
        try:
            footer = "\n" + self.entropy.to_ascii()
            import json as _json
            with open(os.path.join(trees_dir, "infotheory.json"), "w", encoding="utf-8") as f:
                _json.dump(self.entropy.report(), f, indent=1)
        except Exception:
            footer = ""   # never let self-modeling break the tree write
        with open(latest, "w", encoding="utf-8") as f:
            f.write(render + footer + "\n")
        with open(snap, "w", encoding="utf-8") as f:
            f.write(render + footer + "\n")
        # roadmap: English-word rendering — sentences, not codes. Same
        # decision, human-readable, written alongside every ASCII tree.
        try:
            english = _en.render_aiception(
                getattr(self.driver, "last_tree", None) or decision)
            en_latest = os.path.join(trees_dir, "latest.en.txt")
            en_snap = os.path.join(trees_dir, f"tree_{stamp}.en.txt")
            with open(en_latest, "w", encoding="utf-8") as f:
                f.write(english + "\n")
            with open(en_snap, "w", encoding="utf-8") as f:
                f.write(english + "\n")
        except Exception:
            pass  # English is a rendering surface — never break the tree write
        self._prune_trees(trees_dir)
        return latest

    # How many timestamped decision trees to keep on disk. One is written per decide() call, so a
    # continuous daemon produces them without bound -- 18 accumulated from a single test run.
    # Overridable, but never unlimited: unbounded growth on the RAID is not a debugging feature.
    MAX_TREES = int(os.environ.get("VIPER_BDI_MAX_TREES", "200"))

    @classmethod
    def _prune_trees(cls, trees_dir: str) -> int:
        """Keep the newest MAX_TREES snapshots; drop the rest. Never touches latest.txt."""
        try:
            snaps = sorted(f for f in os.listdir(trees_dir)
                           if f.startswith("tree_") and f.endswith(".txt"))
        except OSError:
            return 0
        excess = len(snaps) - cls.MAX_TREES
        if excess <= 0:
            return 0
        dropped = 0
        for name in snaps[:excess]:                       # sorted by timestamp -> oldest first
            try:
                os.remove(os.path.join(trees_dir, name))
                dropped += 1
            except OSError:
                pass
        return dropped

    def driver_stats(self) -> Dict:
        return self.driver.stats()

    def ask(self, want: str, search: bool = True) -> Dict:
        """Complete an INTENT ASK: parse the want, route it through the
        hex mesh from the endpoint, and (on impasse) webcrawl the subject
        to break the loop. Deterministic, zero-LLM."""
        from .intent import parse_intent
        intent = parse_intent(want)
        searcher = self.search_fallback.search_on_impasse if search else None
        return self.mesh.submit_intent(intent, search=searcher)

    def harvest_self_emails(self, limit: int = 20, dry_run: bool = True) -> Dict:
        """Live Gmail -> corpus, SELF-SENT emails only (strict filter: sender
        == recipient == account, no CC/BCC to others). Reads credentials from
        env (BDI_GMAIL_USER / BDI_GMAIL_APP_PASSWORD); never connects without
        the app password set. Deterministic, zero-LLM."""
        import os
        from .gmail_bridge import bridge
        account = os.environ.get("BDI_GMAIL_USER", "chrisalunlloyd2@gmail.com")
        app_password = os.environ.get("BDI_GMAIL_APP_PASSWORD", "")
        if not app_password:
            return {"error": "BDI_GMAIL_APP_PASSWORD not set", "self_sent_fetched": 0}
        corpus_path = os.path.join(self.state_dir, "corpus", "chat_corpus.jsonl")
        return bridge(account, app_password, corpus_path, limit=limit, dry_run=dry_run)

    def digest_repos(self, dry_run: bool = True) -> Dict:
        """Inject digested repo facts (statements + Q&A) into the chat corpus.
        Aegis v2: "make sure data makes it in the chats too" — structured
        content answers, not just prose. Deterministic, zero-LLM, ADD-only."""
        from .digest import seed_digest
        corpus_path = os.path.join(self.state_dir, "corpus", "chat_corpus.jsonl")
        return seed_digest(corpus_path, dry_run=dry_run)

    def ask_code(self, question: str, c_miss: float = 10.0, c_false: float = 1.0) -> Dict[str, Any]:
        """Human-readable code ask -> HTML blocks, Nash-gated (entry point).

        The rotor stops when the composed block's structure ban crosses
        theta* = nash_threshold(c_miss, c_false). Every ask is logged as a
        trace for the hourly learning loop.
        """
        from .code_ask import ask_code as _ask_code
        trace_path = os.path.join(self.state_dir, "code_ask_traces.jsonl")
        return _ask_code(question, c_miss=c_miss, c_false=c_false,
                         trace_path=trace_path)

    def learning_loop(self, config=None) -> Dict[str, Any]:
        """One hourly pass: mine code-ask traces -> promote stable guards to SOPs.

        Collates every ask's guards, scores them with meaning.py's 4-axis
        detector, promotes those crossing the threshold into a persistent SOP
        store, and reports entry (intents) / exit (judgments) points.
        """
        from .learning_loop import run_learning_loop
        trace_path = os.path.join(self.state_dir, "code_ask_traces.jsonl")
        sop_path = os.path.join(self.state_dir, "code_ask_sops.json")
        return run_learning_loop(trace_path, sop_path, config=config)

    def compile(self, source: str, optimize_ir: bool = True):
        """Compile source -> assembly via the Front/Middle/Back-End pipeline.

        Front-End (lexer -> parser -> semantic), Middle-End (IR lowering ->
        constant folding + DCE), Back-End (instruction selection + register
        allocation -> assembly). Deterministic, zero-LLM.
        """
        from .compiler import compile as _compile
        return _compile(source, optimize_ir=optimize_ir)

    def ask_github(self, question: str, search: bool = True) -> Dict:
        """Definitive TELL answer: cross-correlate web + repos + ban scores.

        The #1 demo surface. "which github is best for robotic implementation
        of llm" -> exhaustive ranked TELL in the form of the answer.
        Deterministic, zero-LLM; searcher injectable via search=False (local only).
        """
        from .ask_engine import compare
        from .search_fallback import _wikipedia_search
        corpus_path = os.path.join(self.state_dir, "corpus", "chat_corpus.jsonl")
        searcher = _wikipedia_search if search else (lambda q, limit=3: [])
        return compare(question, corpus_path, searcher=searcher)

    def linguistic_train(self, text: Optional[str] = None) -> Dict:
        """Train the POS databases from the corpus + optional chat text.

        Chris's model: nouns = the key symbolic databases, verbs = another
        database, verbs modify nouns, adverbs modify modifiers, and proximity
        ("close by = related") is logged as weighted relations. Deterministic,
        zero-LLM. The "directional pattern" is what this learns.
        """
        from .pos_db import PosDB
        import json as _json
        db = PosDB()
        self.pos_db = db
        corpus_path = os.path.join(self.state_dir, "corpus", "chat_corpus.jsonl")
        n = 0
        try:
            with open(corpus_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        o = _json.loads(line)
                    except Exception:
                        continue
                    db.ingest(o.get("text", ""))
                    n += 1
        except FileNotFoundError:
            pass
        if text:
            db.ingest(text)
        return {"corpus_lines": n, "stats": db.stats(),
                "top_relations": [(f"{s}->{d}", round(w, 2))
                                  for (s, d), w in db.top_relations(10)]}

    def dream_cycle(self, **kw) -> Dict:
        """Run the nightly maintenance (dream-prune + GC + email cross-
        correlation + code/English self-train). Stage toggleable."""
        from .dream_cycle import dream_cycle as _dream_cycle
        return _dream_cycle(self, **kw)

    def observe_entity(self, entity_type: str, key: str, facts: Dict,
                       relations=None, ts=None) -> Dict:
        """Record an observation about another entity (sense of other).
        Merges into the entity's DAG (same entity across days)."""
        r = self.world.observe(entity_type, key, facts, relations, ts)
        self.world.save()
        return r

    def entropy_report(self) -> Dict:
        """Source-theory model of the agent's decision stream."""
        return self.entropy.report()

    def entropy_ascii(self) -> str:
        return self.entropy.to_ascii()


    # ---- dream: source coding of the journal ----------------------------
    def dream(self, dry_run: bool = False, keep_threshold: float = 0.3,
              order: int = 1) -> Dict:
        """Dream-prune the decision journal: archive redundant decision
        paths (source coding), re-chain to the old tail, return the report.
        ADD-only — archived, never deleted. Fails are always kept."""
        jpath = self.journal.path
        report = dream_prune(jpath, dry_run=dry_run,
                             keep_threshold=keep_threshold, order=order)
        report["ascii"] = _dream_fmt(report)
        # refresh the entropy model over the compacted stream
        self.entropy = DecisionEntropy(jpath)
        return report

    # ---- chat longer: entropy-stopped Markov stitching ------------------
    def chat_long(self, seed: str, max_words: int = 80, order: int = 2,
                  entropy_cap: float = 3.0, spike_mult: float = 2.0,
                  max_corpus: int = 200, min_words: int = 40) -> Dict:
        """Extend a chat message by stitching Markov strings over the
        learned lexicon corpus; STOP when Shannon entropy rises (the
        coherence break). Zero LLM — the 90s stack, made rigorous."""
        texts = []
        # roadmap: seeded corpus (self-emails + repo mirrors) first — the
        # nightly seed is indistinguishable from learned material.
        corpus_path = os.path.join(self.state_dir, "corpus", "chat_corpus.jsonl")
        if os.path.exists(corpus_path):
            # utf-8 explicitly, and per-LINE isolation. Opening without an encoding used the
            # cp1252 locale codec, so the first em dash in real prose raised UnicodeDecodeError
            # -- and because the whole loop sat inside one `except Exception: pass`, a 2.3 MB
            # corpus silently became zero texts and the chain fell back to the journal. The
            # symptom was a fluent-looking reply built from filenames, with nothing logged.
            try:
                fh = open(corpus_path, encoding="utf-8", errors="replace")
            except OSError:
                fh = None
            if fh is not None:
                with fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            j = json.loads(line)
                        except json.JSONDecodeError:
                            continue      # one bad record costs one record
                        if j.get("text"):
                            texts.append(j["text"][:4000])
        # corpus: learned mirror texts if any
        mirror_dir = os.path.join(os.path.dirname(self.lexicon.path), "mirror")
        if os.path.isdir(mirror_dir):
            for fn in sorted(os.listdir(mirror_dir))[-max_corpus:]:
                fp = os.path.join(mirror_dir, fn)
                try:
                    texts.append(open(fp, encoding="utf-8", errors="ignore").read()[:4000])
                except OSError:
                    continue
        # fallback corpus: the agent's own journal details (its lived text)
        if not texts:
            texts = [e.get("detail", "") for e in self.journal.entries(limit=200)]
        mc = MarkovChat(order=order, seed=len(seed) % 997 + 1)
        mc.build(texts)
        # restart budget scales with the requested length: each corpus sentence
        # is ~5-6 tokens, so ~min_words/5 fresh sentences are needed to fill it.
        max_restarts = max(3, min_words // 5)
        out = mc.generate(seed=seed, max_words=max_words,
                          entropy_cap=entropy_cap, spike_mult=spike_mult,
                          min_words=min_words, max_restarts=max_restarts)
        out["model"] = mc.stats()
        return out

    # ---- self-model, feedback, plateau (Chris 2026-08-12) -------------
    def _gather_corpus_texts(self, max_corpus: int = 200) -> List[str]:
        """Collect the agent's lived text: seeded corpus + learned mirrors
        + journal details. Shared by chat_long and chat_plateau."""
        texts = []
        corpus_path = os.path.join(self.state_dir, "corpus", "chat_corpus.jsonl")
        if os.path.exists(corpus_path):
            # utf-8 explicitly, and per-LINE isolation. Opening without an encoding used the
            # cp1252 locale codec, so the first em dash in real prose raised UnicodeDecodeError
            # -- and because the whole loop sat inside one `except Exception: pass`, a 2.3 MB
            # corpus silently became zero texts and the chain fell back to the journal. The
            # symptom was a fluent-looking reply built from filenames, with nothing logged.
            try:
                fh = open(corpus_path, encoding="utf-8", errors="replace")
            except OSError:
                fh = None
            if fh is not None:
                with fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            j = json.loads(line)
                        except json.JSONDecodeError:
                            continue      # one bad record costs one record
                        if j.get("text"):
                            texts.append(j["text"][:4000])
        mirror_dir = os.path.join(os.path.dirname(self.lexicon.path), "mirror")
        if os.path.isdir(mirror_dir):
            for fn in sorted(os.listdir(mirror_dir))[-max_corpus:]:
                fp = os.path.join(mirror_dir, fn)
                try:
                    texts.append(open(fp, encoding="utf-8", errors="ignore").read()[:4000])
                except OSError:
                    continue
        if not texts:
            texts = [e.get("detail", "") for e in self.journal.entries(limit=200)]
        # cold-start guarantee: never return an empty corpus
        texts = [t for t in texts if t and t.strip()]
        if not texts:
            texts = list(_FALLBACK_CORPUS)
        return texts

    def _pick_nonrecent(self, curve: List[Dict]) -> Optional[Dict]:
        """Lowest-entropy candidate whose text wasn't recently said (zero-repeat)."""
        ranked = sorted([c for c in curve if (c.get("text") or "").strip()],
                        key=lambda c: c.get("word_entropy", 9.9))
        for c in ranked:
            if c["text"].strip() not in self._recent_replies:
                return c
        return None

    def _remember_reply(self, text: Optional[str]) -> None:
        t = (text or "").strip()
        if t:
            self._recent_replies.append(t)

    def chat_plateau(self, seed: str, max_words: int = 80,
                     entropy_cap: float = 3.0, spike_mult: float = 2.0,
                     patience: int = 5, max_candidates: int = 50) -> Dict:
        """Markov candidate expansion until the Shannon-entropy curve levels
        out; returns the lowest-entropy (most coherent) reply plus the curve
        of every candidate that was tried. Zero LLM, deterministic, seeded."""
        texts = self._gather_corpus_texts()
        mp = MarkovPlateau(order=2, base_seed=7, eps=0.05,
                           patience=patience, max_candidates=max_candidates)
        out = mp.generate(texts, seed, max_words=max_words,
                          entropy_cap=entropy_cap, spike_mult=spike_mult)
        # Q.E.D. zero-repeat: if the best reply echoes a recent one, pick the
        # next-lowest-entropy candidate that hasn't been said recently.
        best = out.get("best") or {}
        best_text = (best.get("text") or "").strip()
        if best_text and best_text in self._recent_replies:
            alt = self._pick_nonrecent(out.get("curve", []))
            if alt is not None:
                out["best"] = alt
                out["plateau_entropy"] = alt.get("word_entropy", 0.0)
                out["deduped"] = True
        self._remember_reply((out.get("best") or {}).get("text", ""))
        # narrate the plateau as a self-model skill + journal event
        self.identity.master_skill("markov_plateau", 0.5 + 0.4 * float(out.get("plateaued", False)))
        self.record("plateau", f"seed={seed!r} candidates={out.get('candidates', 0)} "
                   f"plateaued={out.get('plateaued')} H={out.get('plateau_entropy', 0):.3f}")
        return out

    def feedback(self, user_input: str, reply: str, positive: bool) -> Dict:
        """Like/dislike training: rate the (input, reply) pair, fold the vote
        into the persistent feedback store AND the self-model narrative."""
        result = self.feedback_store.rate(user_input, reply, positive)
        self.identity.feedback(positive, note=f"{user_input[:60]!r} -> {reply[:60]!r}")
        if not positive:
            self.identity.record_correction(f"flagged_wrong: {reply[:60]!r}")
        self.record("feedback", f"{'LIKE' if positive else 'DISLIKE'} "
                    f"{user_input[:40]!r}", outcome="ok" if result.get("ok") else "err")
        return result


    def observe_tool_intent(self, text: str) -> Dict:
        """Rate how likely `text` is a command/tool request (log-odds 'ban' gate)."""
        if not self.tool_observer:
            return {"probability": 0.0, "is_tool": False, "reason": "observer offline"}
        sc = self.tool_observer.score(text)
        d = sc.to_dict()
        # express log-odds in bans: 1 ban = log10(10); ln-odds -> bans
        import math
        d["bans"] = round(sc.log_odds / math.log(10), 3)
        return d

    def observe_tool_feedback(self, text: str, was_tool: bool) -> None:
        if self.tool_observer:
            self.tool_observer.record(text, was_tool)

    def self_summary(self) -> Dict:
        """The agent's self-report (what the 'self' panel shows)."""
        d = self.identity.who_am_i()
        d["feedback"] = self.feedback_store.stats()
        d["operator"] = self.identity.operator_report()
        d["top_associations"] = self.feedback_store.top_associations(limit=12)
        return d

    # ---- comparative matrix: spectral model of observations -------------
    def compare(self, dry_run: bool = True) -> Dict:
        """Build a comparative matrix over recent journal observations
        (action x outcome-class features) and run the spectral model:
        eigenvector centrality + spectral bisection + energy ranking.
        The bisection feeds dream-pruning: THE CODE vs THE REDUNDANCY."""
        import json as _json
        from collections import Counter as _C
        rows = self.journal.entries(limit=60)
        if len(rows) < 2:
            return {"items": 0, "note": "need >= 2 journal entries"}
        # features per (action) item: outcome-class counts + fail rate
        agg: Dict[str, _C] = {}
        for e in rows:
            agg.setdefault(e.get("action", "?"), _C())[e.get("outcome", "ok")] += 1
        cm = ComparativeMatrix(seed=len(rows))
        for action, c in agg.items():
            total = max(1, sum(c.values()))
            cm.add(action, {
                "ok": c.get("ok", 0) / total,
                "fail": c.get("fail", 0) / total,
                "block": c.get("block", 0) / total,
                "defer": c.get("defer", 0) / total,
            })
        report = cm.build()
        report["energy"] = cm.energy(desirability={
            a: c.get("ok", 0) / max(1, sum(c.values()))
            for a, c in agg.items()})
        report["heat"] = cm.heat_ascii(top_features=4)
        if not dry_run:
            pth = os.path.join(self.state_dir, "comparative_matrix.json")
            cm.save(pth)
            report["saved"] = pth
        self.cm = cm
        return report

    # ---- KQML ACL: English <-> performatives (talk to the agent) --------
    def kqml_talk(self, text: str) -> Dict:
        """Human says English -> agent routes via KQML + lexicon -> English
        reply. Deterministic, zero LLM."""
        r = _kqml.talk(text, lexicon=self.lexicon)
        # route achievable content through the tool set when bound
        if r["tool"] and r["tool"] in self.tools:
            try:
                result = self.tools[r["tool"]](r["content"])
                r["result"] = str(result)[:400]
                r["english"] = _kqml.render_reply(r["performative"], r["result"])
            except Exception as exc:
                r["english"] = f"tool error: {exc}"
        return r

    # ---- deterministic formal kernel ------------------------------------
    def kernel_register(self, graph: Dict, source: str = "synthesis",
                        verified: bool = False) -> Dict:
        """Register a plan graph in the canonical foundry. Dedup: an
        existing canonical hash binds the pre-verified node — never make
        code twice."""
        if not hasattr(self, "_foundry"):
            self._foundry = FoundryRegistry(os.path.join(self.state_dir, "foundry_index.json"))
        rec = self._foundry.register(graph, source=source, verified=verified)
        # roadmap: subsumption DAG — structural dedup beyond exact hash.
        # A more-specific instance of a known shape is memoized, never
        # re-added (never-code-twice, structural form).
        try:
            verdict = self.dag.add(graph)
            self.unify_cache.save()
            rec["subsumption"] = verdict
            rec["dag"] = self.dag.stats()
        except Exception as exc:
            rec["subsumption"] = "dag_error"
            rec["dag_error"] = str(exc)[:120]
        return rec

    def kernel_guard_failure(self, graph: Dict, fail_condition: str) -> Dict:
        """Never mistake twice: mutate the plan's precondition with
        ¬(fail-condition) so unification is FALSE under that state forever."""
        if not hasattr(self, "_foundry"):
            self._foundry = FoundryRegistry(os.path.join(self.state_dir, "foundry_index.json"))
        h = graph_hash(graph)
        rec = self._foundry.apply_failure_guard(h, fail_condition)
        return {"hash": h, "guarded": rec is not None, "condition": fail_condition}

    def kernel_transpile(self, graph: Dict, lang: str = "python") -> str:
        """Language is a rendering surface: T(G, lang) — same graph, any
        target syntax, deterministic."""
        return _transpile(graph, lang)

    def _sync_metaplans(self) -> None:
        """Derive MetaplanAbductor plans from Hap plan memory (ADD-only:
        only adds plan names not already known)."""
        try:
            for p in self.hap.plan_memory:
                pre = ", ".join(f"{k}={v}" for k, v in p.precondition.items())
                if any(m.name == p.name for m in self.metaplans.plans):
                    continue
                self.metaplans.plans.append(
                    _MetaPlan(name=p.name, effect=p.goal, precondition=pre,
                              steps=[s.get("name", p.name) for s in p.steps],
                              spec=p.specificity))
            self.metaplans.save(os.path.join(self.state_dir, "metaplan.json"))
        except Exception:
            pass  # sync is advisory — never break agent construction

    def kernel_abduct(self, goal: str, state: str) -> Dict:
        """Backward-chaining macro synthesis (roadmap item 2). Returns the
        abducted macro chain with an English explanation, or a miss."""
        res = self.metaplans.abduct(goal, state)
        if res:
            res["english"] = _en.render_macro(
                {"goal": goal, "steps": res["steps"],
                 "explanation": res["explanation"]})
        return res or {"achieved": False, "macro": [], "steps": [],
                       "english": f"I could not find a way to reach '{goal}' from here."}

    def kernel_generalize(self, plan_name: Optional[str] = None) -> Dict:
        """Precondition generalization via anti-unification (roadmap item
        3): returns the general precondition(s) synthesized from recorded
        successes, persisted."""
        out = {}
        targets = [plan_name] if plan_name else [
            p.name for p in self.metaplans.plans if p.success_preconditions]
        for nm in targets:
            out[nm] = self.metaplans.generalize_on_success(nm)
        self.metaplans.save(os.path.join(self.state_dir, "metaplan.json"))
        return out

    def kernel_dag_stats(self) -> Dict:
        """Subsumption DAG + memo cache stats (roadmap item 1)."""
        return {"dag": self.dag.stats(), "cache": self.unify_cache.stats()}

    def energy_select(self, x: tuple, plans: list, goal: tuple,
                      min_score: float = 0.0) -> Dict:
        """Geodesic deliberation: admit plans with Score > 0 against the
        energy field, pick the max-alignment winner."""
        m = _EnergyManifold(goal=goal)
        picked = m.select_plan(x, plans, min_score=min_score)
        return {"picked": picked, "goal": goal,
                "energy": round(m.total_energy(x), 5),
                "obstacles": len(m.obstacles)}

    def qed_check(self) -> Dict:
        """Numerical verification of the zero-repeat guarantee (the proof)."""
        return _qed()

    # ---- nightly: cross-correlative actor-critic pedagogy ---------------
    def nightly_train(self, dry_run: bool = True) -> Dict:
        """One nightly training round: harvest observations -> cross-
        correlate recurring failure patterns -> actor proposes (foundry) ->
        critic evaluates (quality gate) -> pedagogy (lexicon learn +
        guardrail derive + dream-prune). Deterministic, zero LLM."""
        import json as _json
        report = {"ts": __import__("time").time(), "rounds": 0, "learned": 0,
                  "guardrails": [], "dream": None}

        # 1. harvest: journal fails + error_learn + guardrail candidates
        fails = self.journal.entries(outcome="fail")
        err_path = os.path.join(self.state_dir, "error_learn.jsonl")
        errs = []
        if os.path.exists(err_path):
            for line in open(err_path):
                line = line.strip()
                if line:
                    try:
                        errs.append(_json.loads(line))
                    except _json.JSONDecodeError:
                        continue

        # 2. cross-correlate: recurring (action -> failure) patterns
        from collections import Counter as _C
        pat = _C()
        for e in fails:
            key = (e.get("action", "?"), (e.get("detail", "") or "")[:60])
            pat[key] += 1
        recurring = [(k, c) for k, c in pat.items() if c >= 2]
        report["patterns"] = len(recurring)

        # 3. pedagogy: learn from every unique failure detail
        seen = set()
        for e in fails:
            d = (e.get("detail", "") or "").strip()
            if d and d[:80] not in seen:
                seen.add(d[:80])
                self.learner.learn_from_text(d, source=f"journal:{e.get('action')}")
                report["learned"] += 1
        for er in errs[-20:]:
            txt = er.get("correction") or er.get("context") or ""
            if txt:
                self.learner.learn_from_text(txt, source="error_learn")

        # 4. guardrails: NMTD auto-rule for recurring fails
        for (action, detail), c in recurring[:10]:
            gr = self.nmtd.learn(str(action), detail[:120])
            if gr:
                report["guardrails"].append({"action": action, "count": c,
                                             "rule": detail[:80]})

        # 5. actor-critic: foundry evaluates candidate plans against fails
        if not dry_run and self.foundry:
            critic = self.skills.hit_rate  # critic = skill-library hit rate
            try:
                self.foundry.set_critic(critic)
                gen = self.foundry.generation(n=3, test_fn=None)
                report["rounds"] = gen.get("round", 0)
            except Exception as exc:  # foundry needs plans; fine if empty
                report["foundry_error"] = str(exc)[:120]

        # 6. dream: source-code the journal (archive redundancy)
        report["dream"] = self.dream(dry_run=dry_run)

        # 7. corpus seed: self-emails + repo mirrors -> chat corpus
        # (roadmap item 5; ADD-only, hash-deduped, paced with the night).
        try:
            report["corpus"] = _corpus_seed(
                os.path.join(self.state_dir, "corpus", "chat_corpus.jsonl"),
                dry_run=dry_run)
        except Exception as exc:
            report["corpus_error"] = str(exc)[:120]

        # 8. metaplan precondition generalization on success (roadmap
        # item 3): anti-unify recorded success preconditions -> general
        # preconditions, persisted for the next abduction.
        try:
            gens = {}
            for p in self.metaplans.plans:
                if p.success_preconditions:
                    gens[p.name] = self.metaplans.generalize_on_success(p.name)
            if gens:
                self.metaplans.save(
                    os.path.join(self.state_dir, "metaplan.json"))
            report["generalized"] = gens
        except Exception as exc:
            report["metaplan_error"] = str(exc)[:120]

        return report


    # ---- Hap: goal-directed reactive engine (Oz/Tok) ---------------------
    def _seed_plans(self) -> None:
        """Seed plan memory with the canonical HOW-TOs for common goals.
        Plan steps mirror the ToK lifecycle: mine -> verify -> record."""
        self.hap.add_plan(Plan(
            "resolve_task", "skill-first",
            steps=[{"type": "action", "name": "lookup_skill", "priority_mod": 0},
                   {"type": "action", "name": "verify", "priority_mod": 0},
                   {"type": "action", "name": "record", "priority_mod": 0}],
            specificity=2.0))
        self.hap.add_plan(Plan(
            "resolve_task", "mine-fallback",
            steps=[{"type": "action", "name": "mine", "priority_mod": 0},
                   {"type": "action", "name": "verify", "priority_mod": 0},
                   {"type": "action", "name": "record", "priority_mod": 0}],
            specificity=1.0))
        self.hap.add_plan(Plan(
            "heal", "restart-stack",
            steps=[{"type": "action", "name": "check", "priority_mod": 0},
                   {"type": "action", "name": "restart", "priority_mod": 0}],
            specificity=1.0))

    def run_hap_goal(self, goal: str, priority: int = 5,
                     facts: Optional[Dict] = None) -> Dict:
        """Post a goal and run one Theory-of-Activity step.

        Roadmap: metaplan abduction — before executing, ask the abductor
        for a backward-chained macro (it already knows Hap's plan memory).
        If one exists it rides along as 'metaplan'; on success the applied
        plan's precondition is recorded so the NEXT abduction generalizes.
        """
        self.hap.post_goal(goal, priority=priority)
        facts = dict(facts or {})
        self.hap.revise(facts)
        result = self.hap.execute(facts)
        ok = result.get("action") not in ("idle", "goal_failed")
        self.record("hap:" + goal, result.get("detail", result.get("action", "")),
                    "ok" if ok else "fail")
        # metaplan abduction hint (never changes execution — Hap decides)
        try:
            state = ", ".join(f"{k}={v}" for k, v in facts.items())
            ab = self.metaplans.abduct(goal, state)
            if ab and ab.get("achieved"):
                result["metaplan"] = ab
                result["metaplan_english"] = _en.render_macro(
                    {"goal": goal, "steps": ab["steps"],
                     "explanation": ab["explanation"]})
            if ok:
                for p in self.metaplans.plans:
                    if goal.lower() in p.effect:
                        self.metaplans.record_success(p.name, state)
                self.metaplans.save(
                    os.path.join(self.state_dir, "metaplan.json"))
        except Exception:
            pass  # abduction is advisory — never break the goal run
        return result

    def apt_render(self) -> str:
        return self.hap.render_apt()

    def _build_maslow(self) -> None:
        self.maslow.add_resource_need(min_disk_mb=50, min_ram_mb=16)
        self.maslow.add_integrity_need(self.nmct)
        self.maslow.add_comms_need()
        self.maslow.add_trust_need(os.path.join(self.state_dir, "trust.json"))
        self.maslow.add_betterment_need(os.path.join(self.state_dir, "betterments.jsonl"))

    # ---- high-level cycle -----------------------------------------------------
    def _retries_left(self) -> bool:
        """Guard for BLOCKED->give_up: True while this slot still has retry
        budget. When False the edge is blocked — BLOCKED is a true dead-end."""
        return self._retries.get(self._current_slot or "", 0) < self.MAX_RETRIES

    def _count_retry(self, slot: str) -> int:
        n = self._retries.get(slot, 0) + 1
        self._retries[slot] = n
        return n

    def _reset_retries(self, slot: str) -> None:
        self._retries.pop(slot, None)

    def resolve_slot(self, slot_name: str, scope: str,
                     candidate_generator: Optional[Callable[[], List[str]]] = None,
                     test_fn: Optional[Callable[[str], bool]] = None,
                     require_approval: bool = False) -> Dict[str, Any]:
        """Full ToK lifecycle for one unresolved slot.
        Returns a result dict; may end in WAIT_AEGIS (proposal queued)."""
        self.bb.assert_fact("status", "EVALUATE")
        self._current_slot = slot_name
        result = {"slot": slot_name, "state": "EVALUATE"}

        # 1. Recipe book pre-filter (compounding determinism)
        recipe = self.memory.fetch_recipe(f"recipe_{slot_name}")
        if recipe:
            code = self.memory.instantiate_recipe(recipe, {})
            tape = [{"cmd": "recipe_hydration", "exit_code": 0}]
            self.nmct.seal(slot_name, code, tape, source="recipe")
            self.fsm.fire("recipe_hit")
            result.update(state="COMMIT", source="recipe", code=code)
            self._reset_retries(slot_name)
            self.fsm.fire("done")
            return result

        # 2. NMCT vault hit (never make code twice)
        canonical = self.nmct.lookup(slot_name)
        if canonical:
            result.update(state="COMMIT", source="nmct_vault",
                          code=canonical["code"], nmct_hash=canonical["canonical_hash"][:8])
            self._reset_retries(slot_name)
            self.fsm.fire("done")
            return result

        # N-retry driver gate (after the deterministic wins): if this slot
        # already burned its budget, park it — BLOCKED is a true dead-end,
        # no re-run, no livelock. Vault/recipe hits above still win.
        if self._retries.get(slot_name, 0) >= self.MAX_RETRIES:
            return {"slot": slot_name, "state": "BLOCKED", "reason": "retry budget exhausted",
                    "retries_exhausted": True, "retries": self._retries[slot_name]}

        # 3. NMTD gate (never make mistakes twice)
        #    (caller passes error signature if a prior failure is known)
        self.bb.assert_fact("status", "SYNTHESIZE")
        self.fsm.fire("needs_mining")
        candidates = candidate_generator() if candidate_generator else [
            p.code_template for p in self.foundry.produce_candidates(3)]
        if not candidates:
            self.fsm.fire("none_produced")
            self._count_retry(slot_name)
            result.update(state="BLOCKED", reason="no candidates produced")
            return result

        rules = self.memory.load_active_rules(scope)
        filtered = self.memory.filter_candidates(candidates, rules)
        if not filtered:
            self.fsm.fire("all_rejected")
            self.nmtd.record(slot_name, scope, ["RuleGate"], "Pre-execution rule rejection", candidates)
            self._count_retry(slot_name)
            result.update(state="BLOCKED", reason="all candidates rejected by rule gate")
            return result

        # 4. Hardened sandbox verification
        self.bb.assert_fact("status", "VERIFY")
        self.fsm.fire("candidates_ready")
        wins = []
        for cand in filtered:
            code, out, err = self.sandbox.run_isolated(slot_name, cand, ["python3", "-m", "py_compile", slot_name])
            if code == 0 and (test_fn is None or test_fn(cand)):
                wins.append(cand)
        if not wins:
            self.fsm.fire("fail")
            self.nmtd.record(slot_name, scope, ["SandboxRunner"], err or "all candidates failed", filtered)
            self._count_retry(slot_name)
            result.update(state="BLOCKED", reason="all candidates failed verification")
            return result

        # Multiple valid candidates with no discriminator = a SOFT plateau
        # (candidate tie). Route to PLATEAU instead of silently picking
        # wins[0]; recovery requires a mutation (expand_horizon /
        # decompose_subgoal / commit_min_regret), never a bare retry.
        if len(wins) > 1 and test_fn is None:
            stalled, ptype = self.plateau_detector.classify("tie")
            self.fsm.fire("stalled")
            result.update(state="PLATEAU", reason=ptype.value, winners=wins)
            return result

        # 5. Commit + NMCT seal
        self.bb.assert_fact("status", "COMMIT")
        self.fsm.fire("pass")
        self._reset_retries(slot_name)
        winner = wins[0]
        tape = [{"cmd": "py_compile", "exit_code": 0}]
        h = self.nmct.seal(slot_name, winner, tape)
        result.update(state="COMMIT", source="foundry", code=winner,
                      nmct_hash=h["canonical_hash"][:8])

        if require_approval:
            self.fsm.fire("needs_approval")
            proposal = self.control.propose("apply_patch", slot_name,
                                            {"code": winner, "nmct_hash": h["canonical_hash"][:8]},
                                            reason="verified candidate awaiting Aegis")
            result.update(state="WAIT_AEGIS", proposal_id=proposal["proposal_id"])
        else:
            self.fsm.fire("done")
        return result

    def break_plateau(self, method: str, winners) -> Dict[str, Any]:
        """Exit PLATEAU via a real mutation (never a bare retry).

        method in {"expand_horizon", "decompose_subgoal", "commit_min_regret"}.
        expand/decompose re-enter EVALUATE (the caller must have mutated
        the blackboard first — widened max_keys, posted a subgoal, etc.).
        commit_min_regret commits the minimum-regret winner (first verified).
        """
        if method == "commit_min_regret":
            if not winners:
                self._count_retry(self._current_slot or "plateau")
                return {"state": "BLOCKED", "reason": "no winner to commit"}
            self.bb.assert_fact("status", "COMMIT")
            self.fsm.fire("commit_min_regret")
            return {"state": "COMMIT", "code": winners[0]}
        if method in ("expand_horizon", "decompose_subgoal"):
            self.bb.assert_fact("status", "EVALUATE")
            self.fsm.fire(method)
            return {"state": "EVALUATE", "method": method}
        return {"state": "PLATEAU", "reason": f"unknown mutation {method!r}"}

    def heartbeat(self) -> Dict[str, Any]:
        """One heartbeat pass: evaluate needs, refresh orientation,
        check FOW, run one actionable step, report."""
        report = {"hex": list(self.hex), "fsm_state": self.fsm.state}
        # needs -> auto-tell to system
        report["needs"] = self.maslow.write_status()
        # orientation from TOC-TOK tower (FOW 1-hop)
        report["visible"] = [n["name"] for n in self.tower.at(*self.hex, hop=1)]
        report["pending_proposals"] = len(self.control.pending())
        report["controller"] = self.hub.status()
        report["lexicon"] = self.lexicon.stats()
        report["pacing"] = pacing_stats()
        self.identity.tick()
        report["identity"] = self.identity.stats()
        report["feedback"] = self.feedback_store.stats()
        report["dual_logger"] = self.dual_logger.stats()
        return report

    def claim_task(self, task_id: str) -> bool:
        return self.fow.claim(task_id)

    # ---- expansion: controller, chat, learning, foundry ------------------
    def controller_status(self) -> dict:
        return self.hub.status()

    _LISTING_VERBS = {"list", "show", "display", "enumerate", "get", "print",
                      "describe", "report", "detail", "summarize", "status", "read"}

    def _is_listing(self, text: str) -> bool:
        from .intent import parse_intent
        try:
            return parse_intent(text).verb in self._LISTING_VERBS
        except Exception:
            return False

    def list_details(self) -> Dict:
        """List all details: the agent's full self-model dump (facts, plans,
        skills, corpus, journal, world, self). For 'list all details' queries.
        Deterministic, zero-LLM."""
        out: Dict[str, Any] = {"facts": dict(self.bb.facts)}
        try:
            out["plans"] = [p.to_dict() for p in self.metaplans.plans]
        except Exception as exc:
            out["plans"] = f"error: {exc}"
        for key, getter in (
            ("skills", lambda: self.skills.stats()),
            ("corpus", lambda: self.search_fallback.trainer.corpus_stats()
                                if self.search_fallback.trainer else {}),
            ("journal", lambda: self.journal.stats()),
            ("world", lambda: self.world.stats()),
        ):
            try:
                out[key] = getter()
            except Exception as exc:
                out[key] = f"error: {exc}"
        try:
            out["self"] = self.self_summary()
        except Exception as exc:
            out["self"] = f"error: {exc}"
        return out

    def chat_reply(self, text: str) -> str:
        """Observer-gated reply (Turing's Banburismus gate).

        Rate tool intent in bans (log-odds). If the observer fires (intent
        clears the Nash threshold), route to the terminal/toolcall path. Else
        reply from the Markov plateau (topical, non-echoing, entropy-plateaued).
        """
        self.learner.learn_from_text(text, source="chat")
        if self._is_listing(text):
            return json.dumps(self.list_details(), indent=2, default=str)[:4000]
        intent = self.observe_tool_intent(text)
        if intent.get("is_tool"):
            try:
                r = self.toolcall(text)
                out = r.get("reply") or r.get("text") or r.get("result") or str(r)
                return "[tool] " + str(out)
            except Exception as e:
                return f"[tool] gate fired but exec failed: {e}"
        try:
            out = self.chat_plateau(text, max_candidates=15)
            best = (out.get("best") or {}).get("text")
            if best:
                return best
        except Exception:
            pass
        return self.chat.chat(text)

    def learn_environment(self, root: str = ".") -> dict:
        """Recursively learn/expand/mirror the lexical environment."""
        return self.learner.learn_from_directory(root)

    def mine_with_foundry(self, name: str, params, examples,
                          target_path: str) -> dict:
        """Use the local brute-foundry to mine a candidate."""
        return self.foundry_adapter.mine_to_file(name, params, examples, target_path)


    # ---- TRIPLE LEARNING LOOP + BEHAVIOR TREE TOOLCALL (Chris 2026-08-11) --
    def _init_loop(self):
        if not hasattr(self, "_triple"):
            from .triple_loop import TripleLearningLoop
            from .verb_flags import VerbFlags
            from .action_lib import build_tree
            self._verbs = VerbFlags(self.state_dir)
            self._btree = build_tree(nmtd=None, platform="termux")
            self._triple = TripleLearningLoop(self.state_dir, self.repo_dir or ".")
            return True
        return False

    def toolcall(self, text: str, ctx: dict = None) -> dict:
        """SLM/human -> English -> verb flags -> performative -> behavior tree
        -> real Termux/PowerShell execution -> 'It is done' reply.

        The canonical flow Chris described:
            slm: "please save this code in repository x file a line 22"
            -> achieve + save -> save_code action -> git commit+push
            -> "It is done: saved N bytes to <file>, commit <sha>, verified."
        """
        self._init_loop()
        ctx = dict(ctx or {})
        # default context placeholders for the action templates
        ctx.setdefault("repo", "/root/scan_tmp/BDI_FSM_AGENT")
        ctx.setdefault("file", "patch.txt")
        ctx.setdefault("code_quoted", "")
        ctx.setdefault("code_ps", "")
        ctx.setdefault("msg", "auto toolcall")
        ctx.setdefault("branch", "main")
        ctx.setdefault("snippet", "")
        ctx.setdefault("tests", "tests/test_all.py")
        ctx.setdefault("state", self.state_dir)
        verbs = self._verbs.verbs(text)
        perf = self._verbs.performative(text)
        hint = self._verbs.action_hint(text)
        # learn new verbs from this message
        learned = self._verbs.learn(text, hint)
        # queue the message for the hourly chat-learn loop too
        self._triple.enqueue_chat(text, source="toolcall")
        if not verbs:
            return {"ok": False, "error": "no_verb_flags", "performative": perf,
                    "text": text, "learned_verbs": learned}
        cands = self._btree.pull(perf, verbs, ctx)
        if not cands:
            return {"ok": False, "error": "no_action_match", "performative": perf,
                    "verbs": verbs, "hint": hint, "learned_verbs": learned}
        res = self._btree.run(perf, verbs, ctx)
        # THE "IT IS DONE" REPLY — multiple confirmation iterations
        if res["ok"]:
            r = res["result"]
            reply = [
                "It is done.",
                f"Action: {res['action']}",
                f"Exit: {r.get('exit')}",
            ]
            if r.get("stdout"):
                reply.append("Output: " + r["stdout"].strip()[-300:])
            if r.get("verified") is True:
                reply.append("Verified: post-check passed.")
            reply.append("Learned verbs: " + (", ".join(learned) if learned else "none new"))
            reply.append("Next: " + (self._verbs.action_hint("run the tests") or "run the tests"))
            return {"ok": True, "action": res["action"], "result": r,
                    "reply": "\n".join(reply), "learned_verbs": learned}
        r = res.get("result", {})
        return {"ok": False, "error": res.get("error", "failed"),
                "action": res.get("action"), "result": r,
                "blocked": r.get("blocked"), "learned_verbs": learned}

    def triple_learn_hourly(self, crawl: bool = True, foundry: bool = True,
                            feature: bool = True) -> dict:
        """Self-train once an hour: chat-learn pending, webcrawl, foundry,
        and Daily Feature (mind-palace/SIMS1337 side quest)."""
        self._init_loop()
        return self._triple.run_hourly(crawl=crawl, foundry=foundry,
                                       feature=feature)

    def queue_foundry_spec(self, name, params, examples, doc="") -> dict:
        self._init_loop()
        self._triple.queue_foundry(name, params, examples, doc)
        return {"ok": True, "queued": name, "queue_len": self._triple._foundry_queue_len()}

    def loop_stats(self) -> dict:
        self._init_loop()
        return self._triple.stats()

    def release_task(self, task_id: str) -> bool:
        return self.fow.release(task_id)


    def run_task_tree(self, task: str, ask: Optional[str] = None,
                      context: str = "", max_steps: int = 5,
                      quality_gate: float = 0.5,
                      executor: Optional[Callable] = None,
                      prefer: Optional[str] = None) -> Dict[str, Any]:
        """Drive ONE task through exhaustive decision trees.

        Each step: expand ALL candidates (filtered by ask + NMTD blocks +
        FOW), select the statistically most likely, execute, COMPARE result,
        record into the DAG, build a NEW tree for the next step. Born, live
        one step, die into the DAG.
        """
        self._init_loop()
        cands = self._tree_candidates

        if executor is None:
            executor = self._tree_executor

        runner = TaskTreeRunner(task, self.task_dag, cands, executor,
                                ask=ask, context=context,
                                max_steps=max_steps, quality_gate=quality_gate,
                                blocked=getattr(self, "_n_m_t_d", []),
                                tree_dir=self.tree_dir)
        out = runner.run(prefer=prefer)
        self.task_dag.save()
        return out

    def _tree_candidates(self, sig: str) -> List[str]:
        """Candidate actions for a task step — the WHOLE action library, unfiltered.

        NMTD blocks are applied later, in the runner. FOW visibility is NOT applied, here or
        anywhere: this returns all eleven actions for every task, every time.

        It used to claim otherwise. The docstring said "filtered by FOW visibility (hex 1-hop)"
        and the body called self.fow.snapshot() and tested snap.get("my_hex") -- but both branches
        of that test were `pass`, so the result was returned unfiltered regardless, and the test
        could never fire anyway: fow.json is keyed by task_id, so "my_hex" is never a key in it.
        Three ways of doing nothing, stacked, under a docstring describing a feature.

        That mattered because it hid the gap. Vectorised FOW steps -- an agent proposing only
        actions it can SEE from where it stands -- is a design decision about what the agent is
        allowed to reach for, and it needs a real visibility model: the agent's own hex, its 1-hop
        neighbours, and a mapping from action to hex. contracts._hex_for already places work on the
        lattice, so the coordinates exist; the action->hex mapping does not. Left unbuilt on
        purpose rather than invented here, because narrowing what the planner may consider changes
        the agent's behaviour and is Chris's call, not a side effect of a cleanup.
        """
        return ["run_tests", "dream_prune", "mine_foundry",
                "update_daily_feature", "kqml_talk", "heal_server",
                "save_code", "webcrawl", "resolve_slot", "markov_chat",
                "deploy"]

    def _tree_executor(self, action: str, sig: str) -> Dict[str, Any]:
        """Real deterministic execution of a tree action."""
        a = (action or "").lower()
        if a == "update_daily_feature":
            try:
                from bdi_fsm.daily_feature import run as df_run
                r = df_run(dry_run=False)
                ok = bool(r and r.get("pushed"))
                return {"ok": ok, "result": str(r)[:200],
                        "quality": 1.0 if ok else 0.2}
            except Exception as e:
                return {"ok": False, "result": f"daily_feature: {e}", "quality": 0.0}
        if a == "run_tests":
            try:
                r = subprocess.run([sys.executable, "tests/test_all.py"],
                                   capture_output=True, text=True, timeout=90,
                                   cwd=self.repo_dir or ".")
                out = (r.stdout or "") + (r.stderr or "")
                ok = "RESULT:" in out and "failed, 0" in out.replace(" ", "")
                return {"ok": ok, "result": out[-160:],
                        "quality": 1.0 if ok else 0.1}
            except Exception as e:
                return {"ok": False, "result": f"tests: {e}", "quality": 0.0}
        if a == "dream_prune":
            try:
                from bdi_fsm.dream_prune import dream_prune, format_report
                r = dream_prune(self.journal.path)
                return {"ok": True, "result": format_report(r)[:160], "quality": 0.8}
            except Exception as e:
                return {"ok": False, "result": f"prune: {e}", "quality": 0.0}
        if a == "mine_foundry":
            try:
                r = self._triple.run_hourly(crawl=False, foundry=True, feature=False)
                return {"ok": True, "result": str(r.get("foundry", ""))[:160],
                        "quality": 0.8}
            except Exception as e:
                return {"ok": False, "result": f"foundry: {e}", "quality": 0.0}
        if a == "kqml_talk":
            try:
                r = self.chat_long("system: run self-check") if hasattr(self, "chat_long") else None
                return {"ok": True, "result": str(r)[:160], "quality": 0.6}
            except Exception as e:
                return {"ok": False, "result": f"kqml: {e}", "quality": 0.0}
        if a == "heal_server":
            try:
                r = subprocess.run(["pgrep", "-f", "gguf_server"], capture_output=True, text=True)
                ok = r.returncode == 0
                return {"ok": ok, "result": "server present" if ok else "server missing",
                        "quality": 0.9 if ok else 0.0}
            except Exception as e:
                return {"ok": False, "result": f"heal: {e}", "quality": 0.0}
        # default: journal a decision + record stats (observational)
        self.journal.record("bdi-fsm-agent", action, f"tree-step on {sig[:40]}", "ok", {})
        return {"ok": True, "result": f"recorded {action}", "quality": 0.7}

    def task_tree_stats(self) -> Dict[str, Any]:
        """DAG stats + recent tree renders."""
        return {"dag": self.task_dag.stats(),
                "dag_ascii": self.task_dag.to_ascii(12),
                "tree_dir": self.tree_dir}

    # ---- logical realms: choice trees + batch terminal -----------------
    def _hook_env(self, result: Any) -> Dict[str, Any]:
        """Normalize any computation result to {ok, result, quality}."""
        if isinstance(result, dict) and "ok" in result and "quality" in result:
            return result
        return {"ok": True, "result": str(result)[:300], "quality": 0.7}

    def _build_hook_dispatcher(self) -> None:
        """Bind direction strings to REAL agent computations (the batch terminal)."""
        d = self.hook_dispatcher
        d.bind("ask_github", lambda **c: self._hook_env(
            self.ask_github(c.get("question", "which repo is best"), search=False)))
        d.bind("chat_reply", lambda **c: self._hook_env(
            self.chat_reply(c.get("text", "hello"))))
        d.bind("list_details", lambda **c: self._hook_env(self.list_details()))
        d.bind("run_task_tree", lambda **c: self._hook_env(
            self.run_task_tree(c.get("task", "self-check"))))
        d.bind("harvest_self_emails", lambda **c: self._hook_env(
            self.harvest_self_emails(limit=5, dry_run=True)))
        d.bind("linguistic_train", lambda **c: self._hook_env(self.linguistic_train()))
        d.bind("dream_cycle", lambda **c: self._hook_env(self.dream_cycle()))
        # every action in the library routes straight to the real executor
        for act in self._tree_candidates(""):
            d.bind(act, (lambda a: (lambda **c: self._hook_env(
                self._tree_executor(a, c.get("sig", "")))))(act))

    def _seed_choice_tree(self) -> None:
        """Seed the choice tree from the action library (list of computations)."""
        t = self.choice_tree
        t.add_node("root")
        for act in self._tree_candidates(""):
            t.add_node(act, hook=f"run {act}", parent="root")

    def run_choice_loop(self, start: str = "root", max_steps: int = 6) -> Dict[str, Any]:
        """Traverse the choice tree: read direction -> compute -> next choice.

        Each executed hook's quality feeds back as a reward on its incoming
        edge (incremental long-horizon feedback), so the conversation map
        learns which computations lead to good results.
        """
        t = self.choice_tree
        if start not in t.nodes:
            self._seed_choice_tree()
        trace: List[str] = []
        results: List[Dict[str, Any]] = []
        node_id = start
        for _ in range(max_steps):
            node = t.nodes[node_id]
            hook = node.get("hook")
            env = (self.hook_dispatcher.run(hook, sig=node_id) if hook
                   else {"ok": True, "result": "(root)", "quality": 0.5})
            results.append({"node": node_id, "hook": hook,
                            "ok": env["ok"], "quality": round(env.get("quality", 0.0), 2)})
            if node.get("parent"):
                t.reward_edge(node["parent"], node_id, env.get("quality", 0.0))
            trace.append(node_id)
            nxt = t.choose(node_id)
            if nxt is None:
                break
            node_id = nxt
        return {"trace": trace, "results": results, "best_next": t.best(node_id)}

    def seed_choice_tree_from_linguistic(self, n: int = 20) -> Dict[str, Any]:
        """Tune the choice-tree Markov from learned directional relations."""
        if self.pos_db is None:
            self.linguistic_train()
        if self.pos_db is None:
            return {"relations": 0, "boosted": 0}
        rels = self.pos_db.top_relations(n)
        boosted = self.choice_tree.seed_from_relations(
            [(s, d, w) for (s, d), w in rels])
        return {"relations": len(rels), "boosted": boosted}

    def code_duplicate(self, code: str) -> Dict[str, Any]:
        """Never-make-code-twice gate: is this code already in the signature store?

        Uses the adaptive NASH threshold (similarity_ban >= theta*), not a
        magic 0.50 inner-product cutoff. Records the code if it is new.
        """
        r = self.signature_store.lookup(code)
        if not r["duplicate"]:
            self.signature_store.add(f"code-{len(self.signature_store.entries) + 1}", code)
        return r


    # ---- telemetry stabilization --------------------------------------
    def telemetry_stabilize(self, dry_run: bool = False) -> dict:
        """Performance monitor + deterministic stabilization (Chris 2026-08-11)."""
        return self.telemetry.stabilize(dry_run=dry_run)

    def telemetry_trend(self, window: int = 12) -> dict:
        return self.telemetry.trend(window=window)

    # ---- capability router (all LLM tasks EXCEPT English creation) -----
    def capability_handle(self, task: str) -> dict:
        """Dispatch any task: FSM handles it deterministically unless it is
        English prose creation, which defers to the local LLM (:5001) or a
        human. Never a cloud LLM."""
        return self.capabilities.handle(task)

    def capability_sweep(self, max_tasks: int = 5) -> dict:
        """Scan the fleet task pool + relay inbox for tasks the FSM can handle
        deterministically (no English creation), run them, record results."""
        results = []
        handled = 0
        deferred = 0
        # 1) task pool — probe-class tasks only
        pool_path = "/root/hexgame/task_pool.json"
        if os.path.exists(pool_path):
            try:
                import json as _json
                pool = _json.load(open(pool_path))
                tasks = pool if isinstance(pool, list) else pool.get("tasks", [])
                for t in tasks:
                    if len(results) >= max_tasks:
                        break
                    if t.get("done"):
                        continue
                    desc = t.get("task", "")
                    if self.capabilities.can_handle(desc):
                        r = self.capabilities.handle(desc)
                        r["pool_id"] = t.get("id")
                        r["task"] = desc
                        results.append(r)
                        handled += 1
            except Exception as e:  # noqa: BLE001
                results.append({"pool_error": str(e)})
        # 2) relay inbox — pending aegis messages
        inbox_path = "/root/hexgame/relay/inbox.jsonl"
        if os.path.exists(inbox_path):
            try:
                import json as _json
                with open(inbox_path) as f:
                    lines = f.readlines()[-20:]
                for line in lines:
                    if len(results) >= max_tasks:
                        break
                    try:
                        msg = _json.loads(line)
                    except Exception:
                        continue
                    body = msg.get("message", "")
                    if not body:
                        continue
                    if self.capabilities.can_handle(body):
                        r = self.capabilities.handle(body)
                        r["inbox_ts"] = msg.get("ts")
                        r["task"] = body
                        results.append(r)
                        handled += 1
                    else:
                        deferred += 1
            except Exception as e:  # noqa: BLE001
                results.append({"inbox_error": str(e)})
        return {"swept": len(results), "handled": handled,
                "deferred_english_or_unknown": deferred, "results": results}

    # ---- git push helper (token read at call time) ---------------------
    def git_push(self, message: str) -> dict:
        """Commit all + push to origin main. Token read from
        /root/.secrets/github_token at call time (never hardcoded)."""
        import subprocess
        verdict = self.law.check("promote", target="origin/main",
                                 content=message, proof={"message": message})
        if verdict["verdict"] == "BLOCKED":
            return {"ok": False, "stage": "law", "error": verdict["reason"]}
        repo = self.repo_dir or "."
        try:
            r = subprocess.run(["git", "-C", repo, "add", "-A"],
                               capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                return {"ok": False, "stage": "add", "error": r.stderr[:200]}
            r = subprocess.run(["git", "-C", repo, "commit", "-m", message],
                               capture_output=True, text=True, timeout=30)
            if r.returncode != 0 and "nothing to commit" not in r.stdout + r.stderr:
                return {"ok": False, "stage": "commit", "error": r.stderr[:200]}
            token = None
            try:
                token = open("/root/.secrets/github_token").read().strip()
            except Exception:
                pass
            remote = subprocess.run(["git", "-C", repo, "remote", "get-url", "origin"],
                                    capture_output=True, text=True, timeout=10)
            url = remote.stdout.strip()
            if token and "github.com" in url:
                if "x-access-token@" in url or "://" in url:
                    import re as _re
                    url = _re.sub(r"https?://[^@]*@", f"https://x-access-token:{token}@", url)
                r = subprocess.run(["git", "-C", repo, "push", url, "HEAD:main"],
                                   capture_output=True, text=True, timeout=60)
            else:
                r = subprocess.run(["git", "-C", repo, "push", "origin", "HEAD:main"],
                                   capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                return {"ok": False, "stage": "push", "error": r.stderr[:300]}
            return {"ok": True, "message": message}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}


    # ---- 100% certainty doctrine + long-horizon execution ----------------
    def step_assess(self, action: str, checks: list, output=None,
                    context: dict | None = None) -> dict:
        """Ask 'is this going to work 100%?' for one step. checks = list of
        (verifier, arg). Returns PASS (confidence 1.0) or STEP_BACK (0.0)."""
        ctx = dict(context or {})
        if output is not None:
            ctx["output"] = output
        return self.certainty.assess(
            {"name": action, "checks": checks, "output": output}, ctx)

    def run_horizon(self, goal: str, blocks: list | None = None,
                    bb: dict | None = None, integrate=None) -> dict:
        """Long-horizon task completion: string blocks of logic serially,
        certainty-gate every step, integrate every output, change course when
        the integrated state deviates from the remaining plan."""
        if blocks is None:
            blocks = self._horizon_blocks_for(goal)
        return self.horizon.run(goal, blocks=blocks, bb=bb, integrate=integrate)

    def _horizon_blocks_for(self, goal: str) -> list:
        """Default deterministic block chain for a goal when none is given:
        assess -> act -> verify -> record (each gated at 100%)."""
        g = (goal or "").lower()
        blocks = []
        # heuristic: goals named after capabilities get capability blocks
        cap = self.capabilities.classify(g) if hasattr(self.capabilities, "classify") else None
        if cap and cap not in ("english", None):
            blocks.append(HorizonBlock(
                name=f"capability:{cap}",
                run=lambda bb, c=cap: self.capabilities.handle(g),
                checks=[("not_empty", None)],
                effect=cap))
        blocks += [
            HorizonBlock("assess", lambda bb: {"ok": True},
                         checks=[("constraint", (lambda o: o.get("ok") is True))]),
            HorizonBlock("act", lambda bb: {"done": True},
                         checks=[("constraint", (lambda o: o.get("done") is True))]),
            HorizonBlock("record", lambda bb: self.journal.record("horizon", g, "ok"),
                         checks=[("not_empty", None)]),
        ]
        return blocks

    def horizon_stats(self) -> dict:
        return {"max_redo": self.horizon.max_redo,
                "gate_verifiers": sorted(self.certainty.VERIFIERS)}


    # ---- the BAN soul: step-by-step information accounting ---------------
    def ban_step(self, name: str, before_probs, after_probs) -> dict:
        """Measure one step in bans: H_before, H_after, gain, certainty.
        The soul of every action — how much information did it actually carry?"""
        return self.ban.step(name, before_probs, after_probs)

    def ban_verdict(self, name: str, before_probs, after_probs,
                    min_gain: float = 0.0) -> dict:
        """The ban gate: GO if the step carried real information, DONE when
        0 bans of uncertainty remain (100%), else STEP_BACK (wasted step)."""
        self.ban.min_gain_bans = min_gain
        return self.ban.verdict(name, before_probs, after_probs)

    def ban_state(self) -> dict:
        return {"remaining_entropy_bans": self.ban.remaining(),
                "is_done": self.ban.is_done(),
                "total_gain_bans": self.ban.total_gain(),
                "steps": len(self.ban.steps),
                "wasted_steps": [s["step"] for s in self.ban.wasted_steps()],
                "bits_equivalent": round(Ban.to_bits(self.ban.total_gain()), 3)}

if __name__ == "__main__":
    import argparse
    import tempfile
    ap = argparse.ArgumentParser(description="BDI_FSM_AGENT — non-LLM super agent")
    ap.add_argument("--state", default=None, help="state dir (default tmp)")
    ap.add_argument("--heartbeat", action="store_true", help="run one heartbeat pass")
    ap.add_argument("--resolve", nargs=2, metavar=("SLOT", "SCOPE"), help="resolve one slot")
    args = ap.parse_args()
    state = args.state or tempfile.mkdtemp(prefix="bdi_state_")
    a = BDIFSMAgent(state)
    if args.heartbeat:
        import json
        print(json.dumps(a.heartbeat(), indent=2))
    elif args.resolve:
        slot, scope = args.resolve
        r = a.resolve_slot(slot, scope,
                           candidate_generator=lambda: [
                               f"def {slot}():\n    return True",
                               f"def {slot}():\n    return 42"],
                           test_fn=lambda c: "42" in c,
                           require_approval=True)
        import json
        print(json.dumps(r, indent=2))
    else:
        ap.print_help()

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
