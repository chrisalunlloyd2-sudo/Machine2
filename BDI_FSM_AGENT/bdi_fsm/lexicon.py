"""LEXICON — boolean chat vocabulary + toolcalling dictionary.

A ≥5,000-token English lexicon, deterministically seeded from a base
word list + morphological derivation (plurals, tenses, adverbs,
comparatives, negation prefixes). Domain tokens are added from the
agent's world (bdi, fsm, nmct, nmtd, hex, maslow, ...).

Recursive learning: the lexicon MIRRORS its environment — every token
seen in logs / tool output / chat is added (mirror()), and expansion
derives new forms (expand()). This is the "learns, expands and mirrors
the lexical environment" pattern.

Toolcalling by lexicon: a word (or phrase) maps to a registered tool —
the boolean bot dispatches deterministically on lexicon match.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple

# Base English word list (common core) — derivation multiplies this past 5k.
BASE_WORDS = [
    "a","about","above","accept","account","across","act","action","active","add",
    "address","agent","ago","agree","air","all","allow","almost","along","already",
    "also","always","am","among","an","and","answer","any","app","apply","are","area",
    "arm","around","art","as","ask","at","attack","attempt","attention","authority",
    "auto","available","avoid","away","back","bad","bag","balance","ball","band",
    "bank","bar","base","be","bear","beat","because","become","bed","before","begin",
    "behavior","behind","believe","bell","belong","below","best","better","between",
    "big","bill","bird","bit","black","block","blood","blue","board","boat","body",
    "book","border","both","box","boy","branch","break","bridge","bright","bring",
    "broad","brother","brown","build","burn","business","busy","but","buy","by",
    "call","came","camp","can","capital","car","card","care","carry","case","cat",
    "catch","cause","cell","center","century","certain","chair","chance","change",
    "character","charge","check","chief","child","choose","church","circle","city",
    "class","clean","clear","close","cloud","coast","cold","color","come","common",
    "community","company","compare","complete","condition","connect","consider",
    "contain","continue","control","cook","cool","copy","corner","cost","could",
    "count","country","course","court","cover","create","cross","crowd","cry",
    "current","cut","dark","data","daughter","day","dead","deal","dear","death",
    "decide","deep","degree","design","desire","desk","detail","develop","die",
    "difference","different","difficult","direction","dirt","discover","discuss",
    "distance","divide","do","doctor","dog","door","double","doubt","down","draw",
    "dream","drive","drop","dry","during","each","early","earth","east","easy",
    "eat","edge","education","effect","effort","eight","either","electric","else",
    "empty","end","enemy","energy","engine","enough","enter","entire","environment",
    "equal","escape","even","evening","event","ever","every","exact","example",
    "excellent","except","exchange","excuse","exercise","expect","experience",
    "explain","eye","face","fact","fail","fair","fall","false","family","famous",
    "far","farm","fast","father","favor","fear","feed","feel","fellow","few","field",
    "fight","figure","fill","film","final","find","fine","finger","finish","fire",
    "first","fish","fit","five","floor","flow","flower","fly","follow","food","foot",
    "for","force","foreign","forget","form","forward","four","free","friend","from",
    "front","full","function","fund","future","gain","game","garden","gas","gate",
    "gather","general","gentle","get","girl","give","glass","global","go","goal",
    "god","gold","good","government","great","green","ground","group","grow","guard",
    "guess","gun","hair","half","hand","hang","happen","happy","hard","has","hat",
    "have","he","head","health","hear","heart","heat","heavy","help","her","here",
    "herself","high","hill","him","himself","his","history","hit","hold","home",
    "hope","horse","hospital","hot","hour","house","how","however","huge","human",
    "hundred","hunt","hurry","husband","i","ice","idea","if","image","imagine",
    "important","in","include","increase","indeed","industry","information","inside",
    "instead","interest","into","involve","is","island","issue","it","its","itself",
    "job","join","jump","just","keep","key","kid","kill","kind","king","kitchen",
    "know","lady","land","language","large","last","late","laugh","law","lay","lead",
    "learn","leave","left","leg","legal","less","let","letter","level","lie","life",
    "light","like","likely","line","list","listen","little","live","local","long",
    "look","lose","lot","love","low","machine","main","major","make","man","many",
    "map","mark","market","marry","material","matter","may","maybe","me","meal",
    "mean","measure","meet","member","men","mental","mention","message","method",
    "middle","might","mile","military","million","mind","mine","minute","miss",
    "mission","model","moment","money","month","moon","more","morning","most",
    "mother","motion","mountain","move","movie","much","music","must","my","myself",
    "name","nation","natural","near","necessary","need","never","new","news","next",
    "nice","night","nine","no","nobody","noise","north","nose","not","note","nothing",
    "notice","now","number","object","occur","ocean","of","off","offer","office",
    "often","oil","old","on","once","one","only","open","operation","opinion","or",
    "order","other","our","out","outside","over","own","page","pain","paint","paper",
    "parent","part","particular","party","pass","past","path","pay","peace","people",
    "per","perform","perhaps","period","person","picture","piece","place","plan",
    "plane","plant","play","point","police","policy","political","poor","popular",
    "population","position","possible","post","power","practice","prepare","present",
    "president","press","pretty","prevent","price","private","probably","problem",
    "process","produce","product","program","project","protect","provide","public",
    "pull","purpose","push","put","quality","question","quick","quiet","quite",
    "race","radio","rain","raise","range","rate","rather","reach","read","ready",
    "real","reason","receive","recent","record","red","reduce","remain","remember",
    "remove","report","represent","require","research","respect","rest","result",
    "return","rich","right","ring","rise","river","road","rock","role","room",
    "rule","run","same","sand","save","say","scene","school","science","sea",
    "season","seat","second","section","see","seek","seem","sell","send","sense",
    "sentence","separate","serve","service","set","seven","several","shake","shall",
    "shape","share","she","ship","shoe","short","should","shoulder","show","side",
    "sign","simple","since","sing","single","sister","sit","site","situation",
    "six","size","skill","skin","sky","sleep","small","smile","snow","so","social",
    "soldier","solution","some","somebody","something","sometimes","son","song",
    "soon","sound","source","south","space","speak","special","specific","speech",
    "speed","spend","sport","spring","stand","standard","star","start","state",
    "station","stay","step","still","stone","stop","store","story","straight",
    "strange","street","strength","strike","strong","student","study","subject",
    "success","such","sudden","suggest","summer","sun","support","sure","surface",
    "system","table","take","talk","task","tax","teach","team","technology","tell",
    "ten","tend","term","test","than","thank","that","the","their","them","themselves",
    "then","there","these","they","thing","think","third","this","those","though",
    "thought","thousand","three","through","throw","thus","tie","time","to","today",
    "together","tomorrow","too","tool","top","total","touch","toward","town","trade",
    "train","travel","tree","trip","trouble","true","trust","truth","try","turn",
    "two","type","under","understand","unit","until","up","upon","us","use","usually",
    "value","various","very","view","village","visit","voice","wait","walk","wall",
    "want","war","warm","was","wash","watch","water","way","we","weapon","wear",
    "weather","week","weight","well","west","what","whatever","when","where",
    "whether","which","while","white","who","whole","whom","why","wide","wife",
    "wild","will","win","wind","window","wish","with","within","without","woman",
    "wonder","wood","word","work","world","worry","would","write","wrong","yard",
    "year","yes","yet","you","young","your","yourself",
]

# morphological derivation rules: suffix -> (pos pattern)
_SUFFIXES = ["s", "es", "ed", "ing", "ly", "er", "est", "tion", "ness", "ment", "ful", "less"]
_PREFIXES = ["un", "re", "dis", "pre", "over", "under", "non", "auto", "sub", "inter", "anti", "co"]

# domain lexicon (the agent's world — mirrors the lexical environment)
DOMAIN_WORDS = [
    "bdi", "fsm", "blackboard", "belief", "desire", "intention", "subsumption",
    "nmct", "nmtd", "vault", "incident", "guardrail", "learnings", "recipe",
    "foundry", "brute", "mine", "harden", "candidate", "sandbox", "overlay",
    "rlmit", "timeout", "atomic", "commit", "seal", "verify", "audit", "tamper",
    "hex", "fow", "tower", "toc", "tok", "maslow", "need", "physiological",
    "safety", "belonging", "esteem", "self", "actualization", "heartbeat",
    "betterment", "cron", "task", "agent", "aegis", "control", "channel",
    "proposal", "approve", "deny", "defer", "veto", "lexicon", "token",
    "boolean", "chat", "english", "openrouter", "llm", "slm", "model",
    "deterministic", "symbolic", "planner", "mesh", "cellular", "fastmem",
    "workspace", "heuristic", "repair", "governance", "policy", "rollback",
    "backtrack", "race", "exit", "code", "stdout", "stderr", "python", "json",
    "yaml", "file", "dir", "path", "repo", "git", "push", "pull", "branch",
    "merge", "diff", "hash", "sha", "signature", "tape", "trace", "log", "event",
    "fact", "plan", "goal", "state", "status", "idle", "evaluate", "synthesize",
    "verify", "commit", "blocked", "wait", "active", "inactive", "discover",
    "seek", "controller", "human", "powershell", "terminal", "power", "shell",
]


class Lexicon:
    """≥5k token English lexicon with morphological derivation +
    recursive mirroring of the environment."""

    def __init__(self, path: Optional[str] = None, min_tokens: int = 5000):
        self.path = path
        self.min_tokens = min_tokens
        self._tokens: Set[str] = set(BASE_WORDS)
        self._domain: Set[str] = set(DOMAIN_WORDS)
        self._tool_bindings: Dict[str, str] = {}   # token -> tool name
        self._freq: Dict[str, int] = {}
        self._expand_morphology()
        self._tokens |= self._domain
        if self.path and os.path.exists(self.path):
            self._load()

    # ---- seeding --------------------------------------------------------
    def _expand_morphology(self) -> None:
        """Derive new forms so the lexicon exceeds min_tokens."""
        base = list(BASE_WORDS)
        for w in base:
            if len(w) < 3:
                continue
            for suf in _SUFFIXES:
                self._tokens.add(w + suf)
            for pre in _PREFIXES:
                self._tokens.add(pre + w)

    def size(self) -> int:
        return len(self._tokens)

    def ensure_min(self) -> int:
        """Guarantee ≥ min_tokens (should already be true)."""
        i = 0
        while len(self._tokens) < self.min_tokens:
            self._tokens.add(f"tok{i:04d}")   # safe filler (never matches chat)
            i += 1
        return len(self._tokens)

    # ---- mirroring (recursive lexical learning) --------------------------
    def mirror(self, text: str) -> List[str]:
        """Learn new tokens from the environment. Returns newly added."""
        added = []
        for t in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text):
            t = t.lower()
            if t not in self._tokens and not t.startswith("tok"):
                self._tokens.add(t)
                self._domain.add(t)
                added.append(t)
            self._freq[t] = self._freq.get(t, 0) + 1
        return added

    def mirror_file(self, path: str) -> List[str]:
        try:
            return self.mirror(open(path, errors="ignore", encoding="utf-8").read())
        except Exception:
            return []

    def expand(self) -> int:
        """Derive new morphological forms from the grown domain set."""
        before = len(self._tokens)
        for w in list(self._domain):
            for suf in _SUFFIXES:
                self._tokens.add(w + suf)
            for pre in _PREFIXES:
                self._tokens.add(pre + w)
        return len(self._tokens) - before

    # ---- toolcalling by lexicon -------------------------------------------
    def bind(self, token: str, tool: str) -> None:
        self._tool_bindings[token.lower()] = tool

    def lookup_tool(self, text: str) -> Optional[str]:
        """Deterministic dispatch: first lexicon token bound to a tool wins."""
        for t in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text.lower()):
            if t in self._tool_bindings:
                return self._tool_bindings[t]
        return None

    # ---- tokenization --------------------------------------------------------
    def tokenize(self, text: str) -> List[str]:
        return [t.lower() for t in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text)]

    def is_known(self, token: str) -> bool:
        return token.lower() in self._tokens

    # ---- persistence ---------------------------------------------------------
    def save(self) -> None:
        if not self.path:
            return
        data = {"tokens": sorted(self._tokens),
                "domain": sorted(self._domain),
                "bindings": self._tool_bindings,
                "freq": dict(sorted(self._freq.items(), key=lambda x: -x[1])[:1000])}
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, self.path)

    def _load(self) -> None:
        try:
            data = json.load(open(self.path, encoding="utf-8"))
            self._tokens |= set(data.get("tokens", []))
            self._domain |= set(data.get("domain", []))
            self._tool_bindings.update(data.get("bindings", {}))
            self._freq = data.get("freq", {})
        except Exception:
            pass

    def stats(self) -> Dict[str, Any]:
        self.ensure_min()
        return {"tokens": self.size(), "domain": len(self._domain),
                "bindings": len(self._tool_bindings),
                "known_rate": round(len(self._freq) / max(1, len(self._freq)), 3)}
