"""Finite State Machine behavior engine.

Deterministic FSM with named states, guarded transitions, entry/exit
callbacks and a step() loop. No LLM — transitions are pure functions
of blackboard facts.
"""

from typing import Callable, Dict, List, Optional, Any
import threading


class FSMError(Exception):
    pass


class FSM:
    def __init__(self, initial_state: str = "IDLE"):
        self.state = initial_state
        self.initial_state = initial_state
        # state -> {event: (next_state, guard)}
        self._transitions: Dict[str, Dict[str, tuple]] = {}
        self._entry: Dict[str, List[Callable]] = {}
        self._exit: Dict[str, List[Callable]] = {}
        self.transition_log: List[Dict[str, Any]] = []
        self._lock = threading.RLock()   # reentrant: fire() calls can()

    def add_state(self, state: str, on_entry: Optional[Callable] = None,
                  on_exit: Optional[Callable] = None) -> "FSM":
        self._transitions.setdefault(state, {})
        self._entry.setdefault(state, [])
        self._exit.setdefault(state, [])
        if on_entry:
            self._entry[state].append(on_entry)
        if on_exit:
            self._exit[state].append(on_exit)
        return self

    def add_transition(self, state: str, event: str, next_state: str,
                       guard: Optional[Callable] = None) -> "FSM":
        if state not in self._transitions:
            self.add_state(state)
        if next_state not in self._transitions:
            self.add_state(next_state)
        self._transitions[state][event] = (next_state, guard)
        return self

    def can(self, event: str) -> bool:
        with self._lock:
            table = self._transitions.get(self.state, {})
            if event not in table:
                return False
            _, guard = table[event]
            if guard is not None:
                try:
                    return bool(guard())
                except Exception:
                    return False
            return True

    def fire(self, event: str, ctx: Optional[Any] = None) -> bool:
        """Attempt a transition. Returns True if fired. Thread-safe: the whole
        read-evaluate-write of self.state is atomic (RLock)."""
        with self._lock:
            if not self.can(event):
                return False
            table = self._transitions[self.state]
            next_state, _ = table[event]
            for fn in self._exit.get(self.state, []):
                fn(ctx)
            old = self.state
            self.state = next_state
            for fn in self._entry.get(next_state, []):
                fn(ctx)
            self.transition_log.append({"from": old, "event": event, "to": next_state})
            return True

    def reset(self) -> None:
        self.state = self.initial_state

    def is_state(self, *states: str) -> bool:
        return self.state in states
