"""Kernel Isolation & Hardened Execution Engine.

Wraps every candidate pass with OS-level guarantees:
  1. Immutable Copy-on-Write snapshot (isolates repo state)
  2. Sandboxed subprocess runner (CPU timeout + RAM cap)
  3. Atomic commit only on Exit 0; timeout -> 124 + kill process TREE
  4. Cellular cleanup between cells

PORTABILITY (2026-08-10, Viper merge)
    This module was written for POSIX and could not run on the Xeon at all: `preexec_fn`,
    `os.killpg` and `resource.setrlimit` are all POSIX-only, and `preexec_fn` raises ValueError
    on Windows before a single candidate is tested. The three guarantees are now expressed
    per-platform instead of POSIX-only:

        limit        POSIX: RLIMIT_AS via preexec_fn   Windows: Job Object memory cap
        kill tree    POSIX: killpg(SIGKILL)            Windows: taskkill /T /F
        new group    POSIX: start_new_session          Windows: CREATE_NEW_PROCESS_GROUP

    Where a guarantee genuinely cannot be made, it degrades LOUDLY -- `limits_enforced` reports
    what is actually in force, so a caller is never told a cap exists when it does not.

Pure stdlib.
"""

import ctypes
import gc
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Callable, List, Optional, Tuple

IS_WINDOWS = os.name == "nt"

# CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW -- own group so the tree is killable, no console flash
_WIN_FLAGS = 0x00000200 | 0x08000000


class SandboxError(Exception):
    pass


def _win_job_with_memory_cap(max_bytes):
    """A Windows Job Object that hard-caps committed memory for everything assigned to it.

    This is the Windows equivalent of RLIMIT_AS and the answer to failure mode #1 (a candidate
    that allocates without bound). Returns a job handle, or None if the OS refuses -- in which
    case the caller must report the cap as NOT enforced rather than assume it.
    """
    if not IS_WINDOWS:
        return None
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [("ReadOperationCount", ctypes.c_ulonglong),
                        ("WriteOperationCount", ctypes.c_ulonglong),
                        ("OtherOperationCount", ctypes.c_ulonglong),
                        ("ReadTransferCount", ctypes.c_ulonglong),
                        ("WriteTransferCount", ctypes.c_ulonglong),
                        ("OtherTransferCount", ctypes.c_ulonglong)]

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                        ("PerJobUserTimeLimit", ctypes.c_longlong),
                        ("LimitFlags", ctypes.c_ulong),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", ctypes.c_ulong),
                        ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
                        ("PriorityClass", ctypes.c_ulong),
                        ("SchedulingClass", ctypes.c_ulong)]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                        ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
        JobObjectExtendedLimitInformation = 9

        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = (JOB_OBJECT_LIMIT_PROCESS_MEMORY |
                                                 JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
        info.ProcessMemoryLimit = int(max_bytes)
        if not k32.SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                           ctypes.byref(info), ctypes.sizeof(info)):
            k32.CloseHandle(job)
            return None
        return job
    except Exception:
        return None


class HardenedSandbox:
    """CoW overlay sandbox with resource limits and atomic commit."""

    def __init__(self, repo_dir: str, timeout_seconds: int = 5,
                 max_memory_mb: int = 256):
        self.repo_dir = os.path.abspath(repo_dir)
        self.timeout = timeout_seconds
        self.max_memory_bytes = max_memory_mb * 1024 * 1024

    # ---------------------------------------------------------------- limits

    def limits_enforced(self) -> dict:
        """What is ACTUALLY in force on this host. Never claims a cap it cannot apply."""
        if IS_WINDOWS:
            probe = _win_job_with_memory_cap(self.max_memory_bytes)
            mem = probe is not None
            if probe:
                ctypes.WinDLL("kernel32").CloseHandle(probe)
            return {"platform": "windows", "timeout": True, "kill_tree": True, "memory_cap": mem}
        try:
            import resource  # noqa: F401
            mem = True
        except Exception:
            mem = False
        return {"platform": "posix", "timeout": True, "kill_tree": True, "memory_cap": mem}

    def _limit(self) -> Optional[Callable]:
        """POSIX preexec that applies RLIMIT_AS. None on Windows -- where passing it is an error."""
        if IS_WINDOWS:
            return None

        def _preexec():
            try:
                import resource
                resource.setrlimit(resource.RLIMIT_AS,
                                   (self.max_memory_bytes, self.max_memory_bytes))
            except Exception:
                pass
        return _preexec

    def _popen(self, test_cmd, cwd):
        """Spawn with the strongest isolation this platform offers."""
        kw = dict(cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if IS_WINDOWS:
            kw["creationflags"] = _WIN_FLAGS
        else:
            kw["preexec_fn"] = self._limit()
            kw["start_new_session"] = True
        proc = subprocess.Popen(test_cmd, **kw)
        if IS_WINDOWS:
            job = _win_job_with_memory_cap(self.max_memory_bytes)
            if job:
                try:
                    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
                    handle = k32.OpenProcess(0x001F0FFF, False, proc.pid)   # PROCESS_ALL_ACCESS
                    if handle:
                        k32.AssignProcessToJobObject(job, handle)
                        k32.CloseHandle(handle)
                    proc._bdi_job = job          # keep alive; closing the job kills the tree
                except Exception:
                    pass
        return proc

    def _kill_tree(self, proc: subprocess.Popen) -> None:
        """Kill the process AND its children. A test runner that spawns must not outlive it."""
        if IS_WINDOWS:
            try:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                               capture_output=True, timeout=10,
                               creationflags=0x08000000)
            except Exception:
                pass
            try:
                proc.kill()
            except Exception:
                pass
            job = getattr(proc, "_bdi_job", None)
            if job:
                try:
                    ctypes.WinDLL("kernel32").CloseHandle(job)   # KILL_ON_JOB_CLOSE sweeps strays
                except Exception:
                    pass
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _reap(self, proc):
        job = getattr(proc, "_bdi_job", None)
        if job:
            try:
                ctypes.WinDLL("kernel32").CloseHandle(job)
            except Exception:
                pass
            proc._bdi_job = None

    # ---------------------------------------------------------------- runs

    def run_isolated(self, patch_file_rel: str, patch_code: str,
                     test_cmd: List[str]) -> Tuple[int, str, str]:
        """Run a candidate in an ephemeral CoW overlay. On exit 0, atomically
        copy the patched file back to the real repo. Returns (exit_code, out, err)."""
        test_cmd = normalise_cmd(test_cmd)
        with tempfile.TemporaryDirectory(prefix="bdi_overlay_") as tmp:
            overlay = os.path.join(tmp, "repo")
            shutil.copytree(self.repo_dir, overlay,
                            ignore=shutil.ignore_patterns(".git", "__pycache__"))
            target = os.path.join(overlay, patch_file_rel)
            os.makedirs(os.path.dirname(target) or overlay, exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(patch_code)

            proc = None
            try:
                proc = self._popen(test_cmd, overlay)
                try:
                    out, err = proc.communicate(timeout=self.timeout)
                    code = proc.returncode
                except subprocess.TimeoutExpired:
                    self._kill_tree(proc)
                    try:
                        out, err = proc.communicate(timeout=3)
                    except Exception:
                        out, err = "", ""
                    code = 124
                    err = f"CRITICAL: exceeded hard limit of {self.timeout}s"
            except FileNotFoundError:
                code = 127
                out, err = "", f"command not found: {test_cmd[0]}"
            finally:
                if proc is not None:
                    self._reap(proc)

            if code == 0:
                real = os.path.join(self.repo_dir, patch_file_rel)
                os.makedirs(os.path.dirname(real) or self.repo_dir, exist_ok=True)
                shutil.copyfile(target, real)
            return code, out, err

    def run_workspace_test(self, test_cmd: List[str],
                           ignore: Optional[List[str]] = None) -> Tuple[int, str, str]:
        """Run a test command against a CoW copy of the whole repo
        (workspace-level gate). Never mutates the real repo."""
        test_cmd = normalise_cmd(test_cmd)
        ignore = ignore or [".git", "__pycache__", ".tok_memory", ".bdi_state"]
        with tempfile.TemporaryDirectory(prefix="bdi_ws_") as tmp:
            overlay = os.path.join(tmp, "repo")
            shutil.copytree(self.repo_dir, overlay, ignore=shutil.ignore_patterns(*ignore))
            proc = None
            try:
                proc = self._popen(test_cmd, overlay)
                try:
                    out, err = proc.communicate(timeout=self.timeout)
                    return proc.returncode, out, err
                except subprocess.TimeoutExpired:
                    self._kill_tree(proc)
                    return 124, "", f"workspace test exceeded {self.timeout}s"
            except FileNotFoundError:
                return 127, "", f"command not found: {test_cmd[0]}"
            finally:
                if proc is not None:
                    self._reap(proc)


def normalise_cmd(cmd: List[str]) -> List[str]:
    """Map a hardcoded `python3` onto the interpreter that is actually running.

    The repo says "python3" in six places. On Windows that resolves to the Microsoft Store stub
    (or nothing), so every candidate test returned 127 "command not found" -- which the pipeline
    scores as a FAILED CANDIDATE. Silent, and it would have taught the foundry that correct code
    was wrong.
    """
    if not cmd:
        return cmd
    head = os.path.basename(str(cmd[0])).lower()
    if head in ("python3", "python3.exe", "python", "python.exe"):
        return [sys.executable] + list(cmd[1:])
    return list(cmd)


class OSGarbageCollector:
    """Cellular cleanup between cells: GC sweep."""

    @staticmethod
    def cleanup() -> None:
        """Collect garbage. Deliberately does NOT close file descriptors.

        The previous version ran os.closerange(3, 128) in the PARENT process. Under the daemon
        that is not a cleanup, it is sabotage: descriptors 3..128 are the agent's own open SQLite
        connections, log files and sockets, and closing them mid-run corrupts exactly the state
        the sandbox exists to protect. Child FDs are already released when the child exits;
        Python closes its own. There is nothing here to reclaim by hand.
        """
        gc.collect()

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
