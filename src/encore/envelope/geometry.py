"""Phase 2 — envelope geometry on the lifted system (guide 6.3).

- F(x, c) = max{q : (x, q) deliverable} — a single LP (constraints affine in q), with
  membership monotone in q (verified numerically in tests/experiments).
- Fixed-q slices of the deliverable set in the x_0-plane: exact 2D projections via
  pypoman's Bretl–Lall algorithm (D-022) for the 2-state model.
- TabulatedEnvelope: the guide-6.3 runtime lookup — polygon family over a
  (q, T_dew, d) grid with nearest-*conservative*-neighbor semantics off-grid.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linprog
from scipy.spatial import ConvexHull, QhullError

from ..plant.params import PlantParams
from .reachability import EnvelopeSpec, Lifted, build_lifted


# ----------------------------------------------------------- LP-level queries

def _bounds(L: Lifted):
    return [(None, None)] * L.nz


def max_q(L: Lifted, x0: np.ndarray) -> float:
    """F(x_0, c): maximum deliverable offer [W]; -inf if nothing (not even q=0) is."""
    c = np.zeros(L.nz)
    c[L.iq] = -1.0
    A_eq = np.zeros((L.n, L.nz))
    A_eq[:, : L.n] = np.eye(L.n)
    res = linprog(c, A_ub=L.G, b_ub=L.h, A_eq=A_eq, b_eq=np.asarray(x0, dtype=float),
                  bounds=_bounds(L), method="highs")
    return float(res.x[L.iq]) if res.status == 0 else float("-inf")


def is_member(L: Lifted, x0: np.ndarray, q: float) -> bool:
    """Brute-force membership: open-loop feasibility LP at fixed (x_0, q)."""
    A_eq = np.zeros((L.n + 1, L.nz))
    A_eq[: L.n, : L.n] = np.eye(L.n)
    A_eq[L.n, L.iq] = 1.0
    b_eq = np.concatenate([np.asarray(x0, dtype=float), [q]])
    res = linprog(np.zeros(L.nz), A_ub=L.G, b_ub=L.h, A_eq=A_eq, b_eq=b_eq,
                  bounds=_bounds(L), method="highs")
    return res.status == 0


def extract_trajectory(L: Lifted, x0: np.ndarray, q: float):
    """A feasible (X, U) at (x_0, q), or None. X from the exact state maps."""
    A_eq = np.zeros((L.n + 1, L.nz))
    A_eq[: L.n, : L.n] = np.eye(L.n)
    A_eq[L.n, L.iq] = 1.0
    b_eq = np.concatenate([np.asarray(x0, dtype=float), [q]])
    res = linprog(np.zeros(L.nz), A_ub=L.G, b_ub=L.h, A_eq=A_eq, b_eq=b_eq,
                  bounds=_bounds(L), method="highs")
    if res.status != 0:
        return None
    z = res.x
    X = np.array([L.X_coef[t] @ z + L.X_const[t] for t in range(L.N + 1)])
    U = z[L.n + 1:].reshape(L.N, L.m)
    return X, U


# ------------------------------------------------------- exact 2D projections

def project_slice(L: Lifted, q: float) -> np.ndarray:
    """Exact x_0-plane polygon of the deliverable set at offer q (2-state only).

    Returns vertex array (k, 2); shape (0, 2) if the slice is empty.
    Bretl–Lall needs >=1 equality, so we append a dummy variable pinned to zero.
    """
    from pypoman import project_polytope

    if L.n != 2:
        raise ValueError("exact polygon slices implemented for the 2-state model")
    # variables v = (x0, u, dummy); q substituted into the RHS
    keep = [i for i in range(L.nz) if i != L.iq]
    A = L.G[:, keep]
    b = L.h - L.G[:, L.iq] * q
    A = np.hstack([A, np.zeros((A.shape[0], 1))])
    nv = A.shape[1]
    E = np.zeros((2, nv)); E[0, 0] = 1.0; E[1, 1] = 1.0
    C = np.zeros((1, nv)); C[0, -1] = 1.0
    try:
        verts = project_polytope((E, np.zeros(2)), (A, b), eq=(C, np.zeros(1)),
                                 method="bretl")
    except Exception:
        return np.zeros((0, 2))
    return np.array(verts) if len(verts) else np.zeros((0, 2))


def poly_halfspaces(verts: np.ndarray):
    """H-rep (A, b): A x <= b from a vertex set; None if degenerate/empty."""
    if verts.shape[0] < 3:
        return None
    try:
        hull = ConvexHull(verts)
    except QhullError:
        return None
    return hull.equations[:, :2].copy(), -hull.equations[:, 2].copy()


def poly_contains(hs, x, tol: float = 1e-7) -> bool:
    if hs is None:
        return False
    A, b = hs
    return bool(np.all(A @ np.asarray(x, dtype=float) <= b + tol))


def poly_area(verts: np.ndarray) -> float:
    if verts.shape[0] < 3:
        return 0.0
    hull = ConvexHull(verts)
    return float(hull.volume)        # 2-D: volume == area


def support_width(verts: np.ndarray, other: np.ndarray, n_dir: int = 64) -> float:
    """Max support-function gap between two convex vertex sets (convergence metric)."""
    if verts.shape[0] == 0 or other.shape[0] == 0:
        return float("inf") if verts.shape[0] != other.shape[0] else 0.0
    th = np.linspace(0, 2 * np.pi, n_dir, endpoint=False)
    D = np.stack([np.cos(th), np.sin(th)], axis=1)
    h1 = (D @ verts.T).max(axis=1)
    h2 = (D @ other.T).max(axis=1)
    return float(np.abs(h1 - h2).max())


# ----------------------------------------------------------- tabulated lookup

class TabulatedEnvelope:
    """Guide-6.3 runtime object: polygon family over a (d, T_dew, q) grid.

    Off-grid queries snap to the nearest *conservative* neighbor: T_dew up (envelopes
    shrink as dew point rises), q up (envelopes shrink as the offer deepens), d must be
    a tabulated product duration. Membership is therefore an inner (safe) approximation
    of the exact deliverable set; cross-validation quantifies the conservatism.
    """

    def __init__(self, p: PlantParams, d_values, T_dew_grid, q_grid, n_states: int = 2,
                 spec_kwargs: dict | None = None):
        self.p = p
        self.d_values = sorted(d_values)
        self.T_dew_grid = sorted(T_dew_grid)
        self.q_grid = np.sort(np.asarray(q_grid, dtype=float))
        self.spec_kwargs = spec_kwargs or {}
        self.n_states = n_states
        self.cells: dict[tuple, object] = {}     # (d, T_dew, iq) -> halfspaces or None

    def build(self, log=None):
        for d in self.d_values:
            for T_dew in self.T_dew_grid:
                spec = EnvelopeSpec(n_states=self.n_states, T_dew=T_dew, d_min=d,
                                    **self.spec_kwargs)
                L = build_lifted(self.p, spec)
                for iq, q in enumerate(self.q_grid):
                    verts = project_slice(L, q)
                    self.cells[(d, T_dew, iq)] = poly_halfspaces(verts)
                if log:
                    log(f"tabulated d={d} T_dew={T_dew}")
        return self

    def member(self, x, q: float, T_dew: float, d: float) -> bool:
        if d not in self.d_values:
            raise KeyError(f"duration {d} not tabulated")
        dews = [v for v in self.T_dew_grid if v >= T_dew - 1e-9]
        if not dews:
            return False                          # beyond tabulated humidity: refuse
        T_snap = dews[0]
        iq = int(np.searchsorted(self.q_grid, q - 1e-9))
        if iq >= len(self.q_grid):
            return False
        return poly_contains(self.cells[(d, T_snap, iq)], x)
