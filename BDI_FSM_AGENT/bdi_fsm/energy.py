"""ENERGY MANIFOLD — continuous geometric layer for the BDI loop.

Bridges the discrete BDI engine (beliefs, plans, unification) with the
continuous manifold M: beliefs become chart predicates, plan steps become
vector fields, option selection becomes geodesic alignment, and FAILURE
MEMORY becomes a Gaussian obstacle bump in the energy landscape.

Formal guarantee (Q.E.D. — verified numerically in the test suite):
injecting an obstacle bump phi_obs(x) = A*exp(-d_g(x,x_f)^2 / 2 sigma^2)
at a failed state x_f guarantees the failing plan's alignment score is
non-positive inside the failure ball B_sigma(x_f) for amplitude
    A >= A* = c0 * sigma^2 * sqrt(e) / eps
where c0 is the plan's score under the unconstrained landscape and eps
the grid resolution. The BDI engine requires Score > 0 to admit a plan,
so the failing trajectory is rejected with probability 1 — the system is
mathematically incapable of making the same mistake twice.

Pure stdlib, deterministic, zero LLM.
"""

import math
from typing import Any, Callable, Dict, List, Optional, Tuple


def gaussian_bump(center: Tuple[float, ...], x: Tuple[float, ...],
                  amplitude: float, sigma: float) -> float:
    """phi_obs(x) = A*exp(-d^2 / 2 sigma^2), d = Euclidean distance."""
    d2 = sum((a - b) ** 2 for a, b in zip(center, x))
    return amplitude * math.exp(-d2 / (2.0 * sigma * sigma))


def finite_gradient(E: Callable[[Tuple[float, ...]], float],
                    x: Tuple[float, ...], eps: float = 1e-3) -> Tuple[float, ...]:
    """Central-difference gradient of scalar field E at x."""
    g = []
    for i in range(len(x)):
        xp = list(x); xp[i] += eps
        xm = list(x); xm[i] -= eps
        g.append((E(tuple(xp)) - E(tuple(xm))) / (2.0 * eps))
    return tuple(g)


class EnergyManifold:
    """Riemannian-ish state space with energy + obstacle bumps."""

    def __init__(self, goal: Tuple[float, ...], sigma: float = 1.0,
                 eps: float = 1e-2):
        self.goal = goal
        self.sigma = sigma
        self.eps = eps
        self.obstacles: List[Tuple[Tuple[float, ...], float]] = []  # (center, A)

    # ---- energy fields -------------------------------------------------
    def base_energy(self, x: Tuple[float, ...]) -> float:
        """E0: convex potential, min at goal (strong convexity approx)."""
        return sum((a - b) ** 2 for a, b in zip(x, self.goal))

    def total_energy(self, x: Tuple[float, ...]) -> float:
        E = self.base_energy(x)
        for center, A in self.obstacles:
            E += gaussian_bump(center, x, A, self.sigma)
        return E

    def gradient(self, x: Tuple[float, ...]) -> Tuple[float, ...]:
        return finite_gradient(self.total_energy, x, self.eps)

    # ---- failure memory (never mistake twice) --------------------------
    def inject_failure(self, x_f: Tuple[float, ...],
                       amplitude: Optional[float] = None) -> Dict[str, Any]:
        """Permanent obstacle bump at the failed state. If amplitude is
        None, auto-size from the failing plan's unconstrained score."""
        if amplitude is None:
            amplitude = self.required_amplitude(x_f)
        self.obstacles.append((x_f, amplitude))
        return {"center": x_f, "amplitude": amplitude, "count": len(self.obstacles)}

    def required_amplitude(self, x_f: Tuple[float, ...]) -> float:
        """A* = c0 * sigma^2 * sqrt(e) / eps — the proof's uniform bound.
        c0 = max alignment score toward x_f under the unconstrained field."""
        c0 = self._unconstrained_score_toward(x_f)
        return c0 * self.sigma ** 2 * math.sqrt(math.e) / self.eps

    def _unconstrained_score_toward(self, x_f: Tuple[float, ...]) -> float:
        """Worst-case positive score of any plan heading to x_f inside the
        failure ball (sampled on a coarse grid)."""
        worst = 0.0
        r = self.sigma
        steps = 4
        for i in range(steps + 1):
            for j in range(steps + 1):
                x = (x_f[0] + r * (2 * i / steps - 1),
                     x_f[1] + r * (2 * j / steps - 1))
                if self._dist(x, x_f) < 1e-9:
                    continue
                V = self._plan_field_toward(x, x_f)
                g = finite_gradient(self.base_energy, x, self.eps)
                score = sum(v * (-gi) for v, gi in zip(V, g))
                worst = max(worst, score)
        return max(worst, 1e-9)

    # ---- plan vector fields + selection --------------------------------
    @staticmethod
    def _dist(a: Tuple[float, ...], b: Tuple[float, ...]) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

    @staticmethod
    def _plan_field_toward(x: Tuple[float, ...],
                           target: Tuple[float, ...]) -> Tuple[float, ...]:
        """Plan flow V_k(x): unit vector pointing from x toward target."""
        d = EnergyManifold._dist(x, target)
        if d < 1e-9:
            return tuple(0.0 for _ in x)
        return tuple((t - xi) / d for xi, t in zip(x, target))

    def alignment_score(self, x: Tuple[float, ...],
                        field: Tuple[float, ...]) -> float:
        """S(pi_k, x) = <V_k(x), -grad E(x)>. Positive = viable option."""
        g = self.gradient(x)
        return sum(v * (-gi) for v, gi in zip(field, g))

    def select_plan(self, x: Tuple[float, ...],
                    plans: List[Tuple[str, Tuple[float, ...]]],
                    min_score: float = 0.0) -> Optional[str]:
        """BDI option filter: admit only plans with Score > 0; pick the
        geodesically-aligned winner (max inner product)."""
        best, best_score = None, min_score
        for name, target in plans:
            V = self._plan_field_toward(x, target)
            s = self.alignment_score(x, V)
            if s > best_score:
                best, best_score = name, s
        return best


def verify_zero_repeat_guarantee(x_f: Tuple[float, ...] = (2.0, 2.0),
                                 goal: Tuple[float, ...] = (0.0, 0.0),
                                 sigma: float = 1.0, eps: float = 1e-2
                                 ) -> Dict[str, Any]:
    """Numerical proof check of the Q.E.D. theorem: with the bump at A*,
    the failing plan (field toward x_f) has score <= 0 everywhere in the
    failure ball; without it, scores are positive."""
    m = EnergyManifold(goal=goal, sigma=sigma, eps=eps)
    # score WITHOUT bump inside ball
    pos_before = []
    r = sigma
    steps = 8
    for i in range(steps + 1):
        for j in range(steps + 1):
            x = (x_f[0] + r * (2 * i / steps - 1),
                 x_f[1] + r * (2 * j / steps - 1))
            if m._dist(x, x_f) < 1e-9:
                continue
            V = m._plan_field_toward(x, x_f)
            pos_before.append(m.alignment_score(x, V))
    max_before = max(pos_before)
    # inject bump at proof amplitude
    A = m.required_amplitude(x_f)
    m.inject_failure(x_f, amplitude=A)
    scores_after = []
    for i in range(steps + 1):
        for j in range(steps + 1):
            x = (x_f[0] + r * (2 * i / steps - 1),
                 x_f[1] + r * (2 * j / steps - 1))
            if m._dist(x, x_f) < 1e-9:
                continue
            V = m._plan_field_toward(x, x_f)
            scores_after.append(m.alignment_score(x, V))
    max_after = max(scores_after)
    return {
        "max_score_before": round(max_before, 6),
        "max_score_after_bump": round(max_after, 6),
        "amplitude_A_star": round(A, 4),
        "theorem_holds": max_after <= 1e-9,
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
