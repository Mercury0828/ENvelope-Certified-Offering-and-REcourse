"""Phase 2 — readiness sets (guide 6.3).

R(q, d) = the set of states from which the committed offer (q, d) is deliverable hour
after hour: the fixed point of

    R_{k+1} = proj_x { x : (x, q) deliverable over one hour with terminal x_N in R_k },

started from R_0 = the safety/operating box. R_{k+1} is subset of R_k by construction
(terminal sets only shrink), so the iteration converges monotonically; we stop when the
max support-function gap falls below a tolerance. This replaces the slides' ad-hoc
quadratic terminal penalty with the same geometric toolset as the envelope itself.

Implemented exactly (polygon projections) for the 2-state model.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from ..plant.params import PlantParams
from .geometry import poly_halfspaces, project_slice, support_width
from .reachability import EnvelopeSpec, build_lifted


def safety_box_polygon(p: PlantParams, spec: EnvelopeSpec) -> np.ndarray:
    """R_0: operating box intersected with the safety limit T_j <= T_max (vertices)."""
    (jlo, jhi), (wlo, whi) = spec.x_box[0], spec.x_box[1]
    jhi = min(jhi, p.T_max)
    return np.array([[jlo, wlo], [jlo, whi], [jhi, wlo], [jhi, whi]])


def readiness_iteration(p: PlantParams, spec: EnvelopeSpec, q: float,
                        max_iter: int = 10, tol_K: float = 0.05):
    """Iterate to the readiness fixed point at committed offer q [W].

    Returns dict with the polygon sequence (vertex arrays), the converged flag, and the
    support-gap history. spec.terminal is overridden internally.
    """
    if spec.n_states != 2:
        raise ValueError("exact readiness iteration implemented for the 2-state model")
    polys = [safety_box_polygon(p, spec)]
    gaps = []
    converged = False
    for _ in range(max_iter):
        hs = poly_halfspaces(polys[-1])
        if hs is None:                       # readiness collapsed to (near-)nothing
            polys.append(np.zeros((0, 2)))
            break
        L = build_lifted(p, replace(spec, terminal=hs))
        verts = project_slice(L, q)
        polys.append(verts)
        gap = support_width(polys[-1], polys[-2])
        gaps.append(gap)
        if gap < tol_K:
            converged = True
            break
    return {"polygons": polys, "converged": converged, "gaps": gaps,
            "fixed_point": polys[-1]}
