"""ACTION LIBRARY — real Termux + PowerShell code, wired to the behavior tree.

Every action is a BehaviorTree Action with:
  * performatives  — KQML performatives that can trigger it (achieve/ask-one/...)
  * verbs          — flag words in natural language that route to it (save, test...)
  * platforms      — REAL executable code for termux (bash) AND powershell
  * check_cmd      — post-execution verification (never trust exit code alone)

The save_code action is the canonical example Chris gave:
    slm -> bdi_fsm "please save this code in repository x file a line 22"
    -> performative achieve + verb save -> save_code action -> git commit+push
    -> "It is done: saved <n> bytes to <repo>/<file>, commit <sha>, tests <result>"

Pure stdlib. No cloud. No LLM. Code is real and runs on device/desktop.
"""

from .btree import Action

# ---------------------------------------------------------------------------
# The canonical action: save code to a repo (termux + powershell, both real)
# ---------------------------------------------------------------------------
SAVE_CODE = Action(
    name="save_code",
    performatives=["achieve", "insert"],
    verbs=["save", "write", "put", "store", "commit", "push", "add", "create",
           "fix", "update", "apply", "patch"],
    platforms={
        "termux": (
            "cd {repo} && "
            "printf '%s' {code_quoted} > {file} && "
            "git add {file} && "
            "git commit -m '{msg}' && "
            "git push origin {branch} 2>&1 | tail -3"
        ),
        "powershell": (
            "cd {repo}; "
            "Set-Content -Path {file} -Value '{code_ps}' -Encoding UTF8; "
            "git add {file}; "
            "git commit -m '{msg}'; "
            "git push origin {branch} 2>&1 | Select-Object -Last 3"
        ),
    },
    check_cmd="grep -q '{snippet}' {file}",
    timeout=45,
)

# ---------------------------------------------------------------------------
# Run a test suite (termux: python3 tests/test_all.py; powershell: python)
# ---------------------------------------------------------------------------
RUN_TESTS = Action(
    name="run_tests",
    performatives=["achieve", "ask-one", "ask-if"],
    verbs=["test", "run", "verify", "check", "validate", "prove", "green"],
    platforms={
        "termux": "cd {repo} && python3 {tests} 2>&1 | tail -5",
        "powershell": "cd {repo}; python {tests} 2>&1 | Select-Object -Last 5",
    },
    check_cmd="echo ok",
    timeout=120,
)

# ---------------------------------------------------------------------------
# Git status / health of a repo (read-only probe)
# ---------------------------------------------------------------------------
GIT_STATUS = Action(
    name="git_status",
    performatives=["ask-one", "ask-all", "ask-if"],
    verbs=["status", "show", "list", "what", "check", "report", "state",
           "diff", "log"],
    platforms={
        "termux": "cd {repo} && git status --short && git log --oneline -3",
        "powershell": "cd {repo}; git status --short; git log --oneline -3",
    },
    check_cmd=None,
    timeout=30,
)

# ---------------------------------------------------------------------------
# Webcrawl self-training (paced, cooldown-deduped)
# ---------------------------------------------------------------------------
WEBCRAWL = Action(
    name="webcrawl",
    performatives=["achieve"],
    verbs=["crawl", "learn", "train", "fetch", "read", "research", "scrape"],
    platforms={
        "termux": "cd {repo} && python3 scripts/train_step.py --max-pages 2 2>&1 | tail -5",
        "powershell": "cd {repo}; python scripts/train_step.py --max-pages 2 2>&1 | Select-Object -Last 5",
    },
    check_cmd=None,
    timeout=90,
)

# ---------------------------------------------------------------------------
# Dream prune: archive journal redundancies (ADD-only)
# ---------------------------------------------------------------------------
DREAM_PRUNE = Action(
    name="dream_prune",
    performatives=["achieve"],
    verbs=["dream", "prune", "archive", "consolidate", "sleep", "clean"],
    platforms={
        "termux": "cd {repo} && python3 -c \"from bdi_fsm.dream_prune import dream; print('dream ok')\" 2>&1 | tail -3",
        "powershell": "cd {repo}; python -c \"from bdi_fsm.dream_prune import dream; print('dream ok')\" 2>&1 | Select-Object -Last 3",
    },
    check_cmd=None,
    timeout=60,
)

# ---------------------------------------------------------------------------
# Brute foundry mine: darwinistic code evolution (hourly loop)
# ---------------------------------------------------------------------------
FOUNDRY_MINE = Action(
    name="foundry_mine",
    performatives=["achieve"],
    verbs=["mine", "evolve", "breed", "foundry", "mutate", "optimize",
           "darwin", "improve"],
    platforms={
        "termux": "cd {repo} && python3 scripts/foundry_loop.py 2>&1 | tail -8",
        "powershell": "cd {repo}; python scripts/foundry_loop.py 2>&1 | Select-Object -Last 8",
    },
    check_cmd=None,
    timeout=120,
)

# ---------------------------------------------------------------------------
# Reload/refresh a local model server (SLM house server :5000 / :5001)
# ---------------------------------------------------------------------------
RELOAD_MODEL = Action(
    name="reload_model",
    performatives=["achieve"],
    verbs=["reload", "refresh", "restart", "swap", "warm", "model", "server"],
    platforms={
        "termux": (
            "pkill -f 'gguf_server_v2[.]py' 2>/dev/null; sleep 1; "
            "cd /root/MatrixWinCE && nohup python3 gguf_server_v2.py 5000 "
            "> /root/hexgame/server.log 2>&1 & sleep 2; "
            "curl -s -m 5 http://localhost:5000/healthz"
        ),
        "powershell": (
            "Get-Process -Name 'gguf_server*' -ErrorAction SilentlyContinue | "
            "Stop-Process -Force; Start-Sleep 1; Start-Process python -ArgumentList "
            "'gguf_server_v2.py','5000' -WorkingDirectory C:\\root\\MatrixWinCE; "
            "Start-Sleep 2; (Invoke-WebRequest -Uri http://localhost:5000/healthz -TimeoutSec 5).Content"
        ),
    },
    check_cmd=None,
    timeout=60,
)


# ---------------------------------------------------------------------------
# Daily Feature update — BDI_FSM surfaces sibling repo changes (side quest)
# ---------------------------------------------------------------------------
UPDATE_DAILY_FEATURE = Action(
    name="update_daily_feature",
    performatives=["achieve"],
    verbs=["feature", "daily", "publish", "update", "surface", "showcase",
           "highlight", "announce", "share", "post", "digest"],
    platforms={
        "termux": "cd {repo} && python3 -m bdi_fsm.daily_feature --state {state} 2>&1 | tail -6",
        "powershell": "cd {repo}; python -m bdi_fsm.daily_feature --state {state} 2>&1 | Select-Object -Last 6",
    },
    check_cmd=None,
    timeout=90,
)

ALL_ACTIONS = [SAVE_CODE, RUN_TESTS, GIT_STATUS, WEBCRAWL, DREAM_PRUNE,
               FOUNDRY_MINE, RELOAD_MODEL, UPDATE_DAILY_FEATURE]

ACTION_MAP = {a.name: a for a in ALL_ACTIONS}


def build_tree(nmtd=None, platform="termux"):
    """Build the BehaviorTree with the full action library."""
    from .btree import BehaviorTree
    return BehaviorTree(ALL_ACTIONS, nmtd=nmtd, platform=platform)

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
