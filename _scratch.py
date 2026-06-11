import numpy as np
from encore.control.fallback import certified_max_q
from encore.data.residuals import RealRecordPool
from encore.envelope.reachability import EnvelopeSpec
from encore.market.offering import ready_state_for
from encore.plant.params import load_params
from encore.tighten.quantile_boxes import Box, ConditionalBoxes
from encore.tighten.tube import build_tube, lqr_gain

p = load_params()
K = lqr_gain(p, 3, r_u=1.0 / (10e3) ** 2)
pool = RealRecordPool(p.Q_IT_nom, seed=20260610, role="fit", source="alibaba")
feats, recs = pool.features_records()
cb = ConditionalBoxes(feats, recs, eps=0.1, k=80, k_cal=150)
b = cb.box(RealRecordPool.hour_features(14))
print(f"alibaba hod14 box: w_Q {b.w_Q_sym/1e3:.0f} kW  E {b.E_hi/1e6:.0f} MJ  w_D {b.w_D:.2f} K")


def F(box, d=30.0, T_dew=12.0):
    spec = EnvelopeSpec(n_states=3, T_dew=T_dew, d_min=d)
    x = ready_state_for(p, T_dew + box.w_D, 3)
    tube = build_tube(p, 3, 12, box.w_Q_sym, box.w_D, K=K, E_budget=box.E_hi)
    return max(certified_max_q(p, spec, tube, x), 0) / 1e3


print(f"full box:        F30 {F(b):6.1f}  F15 {F(b, 15.0):6.1f} kW")
print(f"dew face -> 1K:  F30 {F(Box(b.w_Q_hi, b.E_hi, 1.0)):6.1f} kW")
print(f"dew face -> 0:   F30 {F(Box(b.w_Q_hi, b.E_hi, 0.0)):6.1f} kW")
print(f"heat halved:     F30 {F(Box(b.w_Q_hi*0.5, b.E_hi*0.5, b.w_D_hi)):6.1f} kW")
# alloc rebalance test: more eps to dew
for alloc in ((0.35, 0.35, 0.30), (0.25, 0.25, 0.50)):
    cb2 = ConditionalBoxes(feats, recs, eps=0.1, k=80, k_cal=150, face_alloc=alloc)
    b2 = cb2.box(RealRecordPool.hour_features(14))
    print(f"alloc {alloc}: w_Q {b2.w_Q_sym/1e3:.0f} E {b2.E_hi/1e6:.0f} w_D {b2.w_D:.2f} "
          f"-> F30 {F(b2):6.1f}  F15 {F(b2, 15.0):6.1f} kW")
