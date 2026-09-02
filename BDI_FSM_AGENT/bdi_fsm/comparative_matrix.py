"""COMPARATIVE MATRIX — spectral analysis over comparative observations.

Correlate with continuous-math AI (the pedagogy curriculum): where the
LLM path models data on a smooth manifold and runs diffusion sampling,
we compute the DISCRETE ANALOGS deterministically, pure stdlib, zero LLM:

* SIMILARITY GRAPH   — items (decisions/plans/lexicon entries) are nodes;
                       edge weight = cosine similarity of their feature
                       vectors. This is our manifold: the graph geodesic
                       between two items approximates distance on the
                       underlying data manifold.
* NORMALIZED LAPLACIAN — L = I - D^-1/2 A D^-1/2. Spectral analysis of L
                       gives the structural topology of the decision space
                       (same object as spectral graph convolution, but we
                       never need a GPU — power iteration suffices).
* EIGENVECTOR CENTRALITY — dominant eigenpair of A (Perron vector):
                       which decisions are most structurally influential.
* SPECTRAL BISECTION  — the second eigenvector's sign pattern partitions
                       the matrix into two coherent clusters (the
                       Fiedler-vector cut) — used to separate THE CODE
                       (novel, keep) from THE REDUNDANCY (archive) during
                       dream-pruning.
* ENERGY LANDSCAPE    — E(item) = -desirability; gradient flow = discrete
                       steepest descent over graph neighbors toward the
                       lowest-energy (most desirable) decision.

Pure stdlib (power iteration, no numpy). Deterministic (seeded).
"""

import json
import math
import random
from typing import Any, Dict, List, Optional, Sequence


def cosine_sim(a: List[float], b: List[float]) -> float:
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (na * nb)


def _mat_vec(A: List[List[float]], v: List[float]) -> List[float]:
    return [sum(A[i][j] * v[j] for j in range(len(v))) for i in range(len(A))]


def power_iteration(A: List[List[float]], n_iter: int = 200,
                    tol: float = 1e-10, seed: int = 42) -> tuple:
    """Dominant eigenpair (lambda, v) of symmetric A via power iteration."""
    n = len(A)
    rng = random.Random(seed)
    v = [rng.random() for _ in range(n)]
    nrm = math.sqrt(sum(x * x for x in v)) or 1.0
    v = [x / nrm for x in v]
    lam = 0.0
    for _ in range(n_iter):
        w = _mat_vec(A, v)
        nrm = math.sqrt(sum(x * x for x in w))
        if nrm < 1e-12:
            break
        v = [x / nrm for x in w]
        lam_new = sum(w[i] * v[i] for i in range(n))
        if abs(lam_new - lam) < tol:
            lam = lam_new
            break
        lam = lam_new
    return lam, v


def second_eigenpair(A: List[List[float]], lam1: float, v1: List[float],
                     n_iter: int = 200, seed: int = 7) -> tuple:
    """Approximate 2nd eigenpair via deflation: A' = A - lam1 v1 v1^T."""
    n = len(A)
    B = [[A[i][j] - lam1 * v1[i] * v1[j] for j in range(n)] for i in range(n)]
    return power_iteration(B, n_iter=n_iter, seed=seed)


class ComparativeMatrix:
    """Build a similarity graph + spectral model over comparative observations."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.items: List[str] = []
        self.features: Dict[str, Dict[str, float]] = {}
        self.A: List[List[float]] = []
        self._spec = None

    def add(self, item_id: str, features: Dict[str, float]) -> None:
        self.items.append(item_id)
        self.features[item_id] = dict(features)

    @staticmethod
    def _normalize(feats: Dict[str, Dict[str, float]]) -> Dict[str, List[float]]:
        keys = sorted({k for f in feats.values() for k in f})
        cols = {k: [f.get(k, 0.0) for f in feats.values()] for k in keys}
        out = {}
        for i, item in enumerate(feats):
            vec = []
            for k in keys:
                c = cols[k]
                lo, hi = min(c), max(c)
                vec.append((c[i] - lo) / (hi - lo) if hi > lo else 0.0)
            out[item] = vec
        return out

    def build(self) -> Dict[str, Any]:
        """Normalize features, build cosine-similarity graph, run spectral model."""
        n = len(self.items)
        if n < 2:
            return {"items": n, "note": "need >= 2 items"}
        vecs = self._normalize(self.features)
        self.A = [[cosine_sim(vecs[a], vecs[b]) for b in self.items]
                  for a in self.items]
        lam1, v1 = power_iteration(self.A, seed=self.seed)
        lam2, v2 = second_eigenpair(self.A, lam1, v1, seed=self.seed + 1)
        # normalized graph Laplacian L = I - D^-1/2 A D^-1/2
        deg = [sum(row) for row in self.A]
        d_inv = [1.0 / math.sqrt(d) if d > 1e-12 else 0.0 for d in deg]
        L = [[(1.0 if i == j else 0.0) - d_inv[i] * self.A[i][j] * d_inv[j]
              for j in range(n)] for i in range(n)]
        # spectral bisection: sign of 2nd eigenvector (Fiedler-style cut)
        bisect = [1 if x >= 0 else 0 for x in v2]
        self._spec = {
            "lambda1": round(lam1, 6),
            "lambda2": round(lam2, 6),
            "centrality": {it: round(abs(v1[i]), 5) for i, it in enumerate(self.items)},
            "bisection": {it: bisect[i] for i, it in enumerate(self.items)},
            "laplacian_smallest_est": round(min(sum(L[i][j] for j in range(n))
                                                for i in range(n)) / n, 6),
        }
        return self.report()

    def energy(self, desirability: Optional[Dict[str, float]] = None,
               n_steps: int = 10) -> Dict[str, Any]:
        """Energy landscape: E = -desirability; steepest descent over
        graph neighbors (gradient flow, discrete)."""
        if not self.A:
            return {}
        des = desirability or {it: 0.0 for it in self.items}
        pos = {it: i for i, it in enumerate(self.items)}
        start = min(self.items, key=lambda it: -des.get(it, 0.0))  # lowest E
        cur = start
        path = [cur]
        for _ in range(n_steps):
            nbrs = [self.items[j] for j in range(len(self.items))
                    if self.A[pos[cur]][j] > 0.05 and j != pos[cur]]
            if not nbrs:
                break
            best = min(nbrs, key=lambda nb: -des.get(nb, 0.0))
            if -des.get(best, 0.0) >= -des.get(cur, 0.0) - 1e-12:
                break
            cur = best
            path.append(cur)
        return {"start": start, "basin": cur, "path": path,
                "energy": round(-des.get(cur, 0.0), 5)}

    def heat_ascii(self, top_features: int = 8) -> str:
        """ASCII heat render: rows=items, cols=top features."""
        if not self.features:
            return "(empty matrix)"
        vecs = self._normalize(self.features)
        keys = sorted({k for f in self.features.values() for k in f})
        # pick top features by spread
        spread = {}
        for k in keys:
            vals = [f.get(k, 0.0) for f in self.features.values()]
            spread[k] = max(vals) - min(vals)
        keys = sorted(keys, key=lambda k: -spread[k])[:top_features]
        ramp = " .:-=+*#%@"
        lines = ["  " + "".join(f"{k[:3]:>4}" for k in keys)]
        for it in self.items:
            v = vecs[it]
            idx = {k: i for i, k in enumerate(sorted({k for f in self.features.values() for k in f}))}
            row = "".join(f"{ramp[min(9, int(v[idx[k]] * 10))]:>4}" for k in keys)
            lines.append(f"{it[:10]:>10} {row}")
        return "\n".join(lines)

    def report(self) -> Dict[str, Any]:
        return {"items": len(self.items),
                "spectral": self._spec or {},
                "clusters": self._cluster_counts() if self._spec else {}}

    def _cluster_counts(self) -> Dict[str, int]:
        c0 = sum(1 for x in self._spec["bisection"].values() if x == 0)
        c1 = sum(1 for x in self._spec["bisection"].values() if x == 1)
        return {"cluster_0": c0, "cluster_1": c1}

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump({"items": self.items,
                       "features": self.features,
                       "A": self.A,
                       "spectral": self._spec}, f, indent=1)

    @classmethod
    def load(cls, path: str) -> "ComparativeMatrix":
        cm = cls()
        data = json.load(open(path))
        cm.items = data["items"]
        cm.features = data["features"]
        cm.A = data["A"]
        cm._spec = data["spectral"]
        return cm


def archive_split_by_spectrum(cm: ComparativeMatrix, keep_cluster: int = 0
                              ) -> Dict[str, Any]:
    """Dream-prune tie-in: spectral bisection separates THE CODE (keep
    cluster) from THE REDUNDANCY (archive cluster) — the comparative-matrix
    version of source coding. ADD-only: the archive side is never deleted,
    just marked."""
    if not cm._spec:
        cm.build()
    split = cm._spec["bisection"]
    keep = [it for it, c in split.items() if c == keep_cluster]
    archive = [it for it, c in split.items() if c != keep_cluster]
    return {"keep": keep, "archive": archive,
            "spectral_gap": round(abs(cm._spec["lambda1"] - cm._spec["lambda2"]), 5)}
