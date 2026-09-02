"""LANG DB — code organised by programming language (timestamped, dedup).

Chris directive (2026-08-13): three memory systems —
  1. organise code by programming language,
  2. never make code twice (timestamped database),
  3. never make mistakes twice (record STEPS that do not work so they can't
     be retried).

LangDB is the unified LANGUAGE-INDEXED view over the NMCT code vault and the
NMTD step recorder. Every sealed code entry and every failed step carries a
`language` tag + `ts` timestamp; this module scans them and answers
`by_language(lang)` / `languages()` / `stats()`. Pure stdlib. Zero LLM.
"""
import json
import os
from typing import Any, Dict, List, Optional

from .langdetect import detect_language
from .nmct import NMCT
from .nmtd import NMTD


class LangDB:
    """Language-organized index over the code vault + mistake recorder."""

    def __init__(self, nmct: Optional[NMCT] = None, nmtd: Optional[NMTD] = None,
                 skills_dir: Optional[str] = None):
        self.nmct = nmct
        self.nmtd = nmtd
        self.skills_dir = skills_dir

    def _nmct_entries(self) -> List[Dict[str, Any]]:
        if self.nmct is None:
            return []
        out = []
        vdir = getattr(self.nmct, "vault_dir", None)
        if not vdir or not os.path.isdir(vdir):
            return out
        for fn in sorted(os.listdir(vdir)):
            if not fn.endswith(".json"):
                continue
            try:
                out.append(json.load(open(os.path.join(vdir, fn))))
            except (json.JSONDecodeError, OSError):
                continue
        return out

    def _skill_entries(self) -> List[Dict[str, Any]]:
        if not self.skills_dir or not os.path.isdir(self.skills_dir):
            return []
        out = []
        for fn in sorted(os.listdir(self.skills_dir)):
            if not fn.endswith(".json"):
                continue
            try:
                out.append(json.load(open(os.path.join(self.skills_dir, fn))))
            except (json.JSONDecodeError, OSError):
                continue
        return out

    def _tag(self, entry: Dict[str, Any]) -> str:
        lang = entry.get("language")
        if lang and lang != "unknown":
            return lang
        return detect_language(code=entry.get("code", ""),
                               filename=entry.get("filename", ""),
                               slot=entry.get("slot_name", entry.get("name", "")))

    def index(self) -> Dict[str, List[Dict[str, Any]]]:
        """{language: [entries]} across the code vault, skills, and failed steps."""
        idx: Dict[str, List[Dict[str, Any]]] = {}
        for e in self._nmct_entries():
            idx.setdefault(self._tag(e), []).append({"kind": "code", **e})
        for e in self._skill_entries():
            idx.setdefault(self._tag(e), []).append({"kind": "skill", **e})
        if self.nmtd is not None:
            for s in self.nmtd.failed_steps():
                idx.setdefault(s.get("language", "unknown"),
                               []).append({"kind": "step", **s})
        return idx

    def languages(self) -> List[str]:
        return sorted(self.index().keys())

    def by_language(self, lang: str) -> List[Dict[str, Any]]:
        return self.index().get(lang, [])

    def stats(self) -> Dict[str, int]:
        return {lang: len(entries) for lang, entries in self.index().items()}

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
