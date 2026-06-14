"""Keystroke-dynamics threshold evaluation for the thesis — ALL 3 backends.

Computes FAR / FRR / EER and the optimal threshold (tau*) for each backend
(statistical, rf, svm), faithfully replicating the production scorers, using a
leakage-free protocol:

  statistical (template distance):
      genuine  -> leave-one-out within each subject
      impostor -> every other subject's reps vs the subject's templates

  rf / svm (two-class target-vs-rest, exactly like the app):
      genuine  -> 2-fold within each subject (held-out reps never in training)
      impostor -> leave-one-SUBJECT-out (the test impostor is removed from the
                  negatives, so it is never seen in training)

Usage
-----
Self-test on synthetic data (run right now, no DB):
    venv/Scripts/python.exe scripts/eval_threshold.py --synthetic 10 15

Real data collected via /dataset:
    PYTHONPATH=. venv/Scripts/python.exe scripts/eval_threshold.py --source dataset

Real data from account enrollment:
    PYTHONPATH=. venv/Scripts/python.exe scripts/eval_threshold.py --source users

Outputs a per-backend summary + threshold_eval_<backend>.csv (tau,FAR,FRR).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics

import numpy as np

# 27 features used by the rf/svm backends (must match base_model_service.FEATURE_COLUMNS)
FEATURE_COLUMNS = [
    "H_mean", "H_std", "H_min", "H_max", "H_cv",
    "DD_mean", "DD_std", "DD_min", "DD_max", "DD_cv",
    "UD_mean", "UD_std", "UD_min", "UD_max", "UD_cv",
    "UU_mean", "UU_std", "UU_min", "UU_max", "UU_cv",
    "DU_mean", "DU_std", "DU_min", "DU_max", "DU_cv",
    "total_duration", "typing_speed",
]


# ===========================================================================
# Statistical scorer — faithful copy of production _verify_via_template_distance
# ===========================================================================
def _euclid(a, b):
    return float(np.linalg.norm(np.asarray(a, float) - np.asarray(b, float)))


def _cos(a, b):
    va, vb = np.asarray(a, float), np.asarray(b, float)
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))


def _stat_sim(sample_h, templates):
    rows = []
    for t in templates:
        hv = t.get("H") or []
        try:
            rows.append([float(x) for x in hv])
        except (TypeError, ValueError):
            continue
    if not sample_h or not rows:
        return 0.0
    min_len = min(len(sample_h), min(len(r) for r in rows))
    if min_len == 0:
        return 0.0
    st = sample_h[:min_len]
    tt = [r[:min_len] for r in rows]
    means = [statistics.mean(col) for col in zip(*tt)]
    diffs = [abs(a - b) for a, b in zip(st, means)]
    return float(1.0 / (1.0 + statistics.mean(diffs) * 2.0))


def score_statistical(sample, templates):
    lh, ldd = sample.get("H") or [], sample.get("DD") or []
    if not lh or not ldd:
        return None
    eus, coss = [], []
    for t in templates:
        tH, tDD = t.get("H") or [], t.get("DD") or []
        if len(tH) != len(lh) or len(tDD) != len(ldd):
            continue
        eus.append((1.0 / (1.0 + _euclid(lh, tH)) + 1.0 / (1.0 + _euclid(ldd, tDD))) / 2.0)
        coss.append((((_cos(lh, tH) + 1) / 2) + ((_cos(ldd, tDD) + 1) / 2)) / 2.0)
    if not eus:
        return None
    eu_s, cos_s = float(np.mean(eus)), float(np.mean(coss))
    stat_s = _stat_sim(lh, templates)
    base = max(0.0, min(1.0, 0.5 * eu_s + 0.3 * cos_s + 0.2 * stat_s))
    return max(0.0, min(1.0, base * stat_s))


def evaluate_statistical(subjects):
    genuine, impostor = [], []
    subs = list(subjects)
    for s in subs:
        reps = subjects[s]
        for i in range(len(reps)):
            templates = [reps[j] for j in range(len(reps)) if j != i]
            if templates:
                sc = score_statistical(reps[i], templates)
                if sc is not None:
                    genuine.append(sc)
        for o in subs:
            if o == s:
                continue
            for r in subjects[o]:
                sc = score_statistical(r, reps)
                if sc is not None:
                    impostor.append(sc)
    return np.array(genuine), np.array(impostor)


# ===========================================================================
# RF / SVM scorers — replicate the app's two-class target-vs-rest models
# ===========================================================================
def make_svm():
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    return Pipeline([
        ("scaler", StandardScaler()),
        ("svc", SVC(kernel="rbf", C=10.0, gamma="scale", probability=True, random_state=42)),
    ])


def make_rf():
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(
        n_estimators=200, max_depth=None, min_samples_leaf=2, max_features="sqrt",
        class_weight="balanced", random_state=42, n_jobs=-1,
    )


def _fit_score(make_model, pos, neg, test):
    """Train target(1)-vs-rest(0) and return P(target) for each test row."""
    X = np.vstack([pos, neg])
    y = np.r_[np.ones(len(pos)), np.zeros(len(neg))]
    model = make_model()
    model.fit(X, y)
    proba = model.predict_proba(test)
    idx = list(model.classes_).index(1)
    return proba[:, idx]


def evaluate_classifier(subjects, make_model):
    feats = {s: np.array([smp["featvec"] for smp in reps], dtype=float)
             for s, reps in subjects.items()}
    subs = list(subjects)
    genuine, impostor = [], []
    for u in subs:
        Xu = feats[u]
        nu = len(Xu)
        others = [o for o in subs if o != u]
        neg_all = np.vstack([feats[o] for o in others])
        # genuine: 2-fold within u (held-out reps never in positives/negatives)
        half = nu // 2
        if half >= 1:
            for tr, te in ((slice(0, half), slice(half, nu)), (slice(half, nu), slice(0, half))):
                pos_tr, te_x = Xu[tr], Xu[te]
                if len(pos_tr) and len(te_x):
                    genuine.extend(_fit_score(make_model, pos_tr, neg_all, te_x).tolist())
        # impostor: leave-one-subject-out (test impostor removed from negatives)
        for v in others:
            neg = np.vstack([feats[o] for o in others if o != v])
            impostor.extend(_fit_score(make_model, Xu, neg, feats[v]).tolist())
    return np.array(genuine), np.array(impostor)


# ===========================================================================
# Metrics
# ===========================================================================
def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 1.0
    p = k / n
    d = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    return p, max(0.0, center - half), min(1.0, center + half)


def sweep(genuine, impostor, grid=1001):
    taus = np.linspace(0.0, 1.0, grid)
    far = np.array([float(np.mean(impostor >= t)) if impostor.size else 0.0 for t in taus])
    frr = np.array([float(np.mean(genuine < t)) if genuine.size else 0.0 for t in taus])
    return taus, far, frr


def find_eer(taus, far, frr):
    i = int(np.argmin(np.abs(far - frr)))
    return taus[i], (far[i] + frr[i]) / 2.0, far[i], frr[i]


def find_min_dcf(taus, far, frr, cfa, cfr, ptar):
    cdet = cfr * frr * ptar + cfa * far * (1 - ptar)
    norm = min(cfr * ptar, cfa * (1 - ptar)) or 1.0
    i = int(np.argmin(cdet / norm))
    return taus[i], far[i], frr[i]


def roc_auc(far, frr):
    order = np.argsort(far)
    trap = getattr(np, "trapezoid", None) or np.trapz
    return float(trap((1.0 - frr)[order], far[order]))


# ===========================================================================
# Data
# ===========================================================================
def _stats(vec):
    a = np.asarray(vec, float)
    if a.size == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    mean = float(a.mean())
    std = float(a.std())
    cv = float(std / mean) if mean else 0.0
    return mean, std, float(a.min()), float(a.max()), cv


def _featvec_from_vectors(vecs):
    """Build the 27-dim FEATURE_COLUMNS vector from raw H/DD/UD/UU/DU lists."""
    f = {}
    for name in ("H", "DD", "UD", "UU", "DU"):
        m, s, lo, hi, cv = _stats(vecs.get(name, []))
        f[f"{name}_mean"], f[f"{name}_std"] = m, s
        f[f"{name}_min"], f[f"{name}_max"], f[f"{name}_cv"] = lo, hi, cv
    total = float(np.sum(vecs.get("H", [])) + np.sum(vecs.get("DD", [])))
    f["total_duration"] = total
    f["typing_speed"] = (len(vecs.get("H", [])) / (total / 1000.0)) if total else 0.0
    return [f[c] for c in FEATURE_COLUMNS]


def make_synthetic(n_subjects, n_reps, plen=10, sep=1.0, seed=42):
    rng = np.random.default_rng(seed)
    subjects = {}
    for s in range(n_subjects):
        sig = {
            "H": rng.uniform(80, 130, plen),
            "DD": rng.uniform(120, 220, plen - 1),
            "UD": rng.uniform(40, 120, plen - 1),
            "UU": rng.uniform(120, 220, plen - 1),
            "DU": rng.uniform(80, 160, plen - 1),
        }
        reps = []
        for _ in range(n_reps):
            vecs = {k: (v + rng.normal(0, 0.15 * np.mean(v) / sep, len(v))).tolist()
                    for k, v in sig.items()}
            reps.append({"H": vecs["H"], "DD": vecs["DD"], "featvec": _featvec_from_vectors(vecs)})
        subjects[f"subj{s:02d}"] = reps
    return subjects


def load_from_db(source):
    from sqlalchemy import select
    from app import create_app
    app = create_app()
    subjects = {}
    with app.app_context():
        from app.models import db
        if source == "dataset":
            from app.models import DatasetEntry as M
            rows = db.session.execute(select(M)).scalars().all()
            keyfn = lambda r: f"subject_{r.subject_id}"
        else:
            from app.models import UsersVector as M
            rows = db.session.execute(
                select(M).where(M.event_type == "enrollment")
            ).scalars().all()
            keyfn = lambda r: (r.username or f"user_{r.user_id}")
        for r in rows:
            vecs = {}
            for name in ("H", "DD", "UD", "UU", "DU"):
                try:
                    raw = getattr(r, f"{name}_vector", None)
                    vecs[name] = json.loads(raw) if raw else []
                except (TypeError, ValueError, json.JSONDecodeError):
                    vecs[name] = []
            if not vecs.get("H") or not vecs.get("DD"):
                continue
            subjects.setdefault(keyfn(r), []).append(
                {"H": vecs["H"], "DD": vecs["DD"], "featvec": _featvec_from_vectors(vecs)}
            )
    return subjects


BACKENDS = {
    "statistical": evaluate_statistical,
    "rf": lambda subj: evaluate_classifier(subj, make_rf),
    "svm": lambda subj: evaluate_classifier(subj, make_svm),
}


# ===========================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["dataset", "users"])
    ap.add_argument("--synthetic", nargs=2, type=int, metavar=("SUBJECTS", "REPS"))
    ap.add_argument("--sep", type=float, default=1.0, help="synthetic separability (higher=easier)")
    ap.add_argument("--cfa", type=float, default=1.0, help="cost of a false accept (DCF)")
    ap.add_argument("--cfr", type=float, default=1.0, help="cost of a false reject (DCF)")
    ap.add_argument("--ptarget", type=float, default=0.5, help="prior P(genuine)")
    ap.add_argument("--backends", default="statistical,rf,svm", help="comma list to evaluate")
    args = ap.parse_args()

    if args.synthetic:
        subjects = make_synthetic(*args.synthetic, sep=args.sep)
        print(f"[synthetic] {args.synthetic[0]} subjects x {args.synthetic[1]} reps (sep={args.sep})")
    elif args.source:
        subjects = load_from_db(args.source)
        print(f"[db:{args.source}] loaded {len(subjects)} subjects")
    else:
        ap.error("provide --synthetic SUBJECTS REPS, or --source {dataset,users}")

    subjects = {k: v for k, v in subjects.items() if len(v) >= 2}
    if len(subjects) < 3:
        print("ERROR: need >=3 subjects with >=2 reps each (rf/svm need negatives). Collect more.")
        return 1
    rp = [len(v) for v in subjects.values()]
    print(f"subjects={len(subjects)}  reps/subject min={min(rp)} max={max(rp)} total={sum(rp)}\n")

    rows = []
    for name in [b.strip() for b in args.backends.split(",") if b.strip()]:
        if name not in BACKENDS:
            print(f"  (skip unknown backend '{name}')"); continue
        print(f"--- evaluating {name} ... ---")
        genuine, impostor = BACKENDS[name](subjects)
        if genuine.size == 0 or impostor.size == 0:
            print(f"  [{name}] not enough comparable samples\n"); continue
        taus, far, frr = sweep(genuine, impostor)
        t_eer, eer, far_e, frr_e = find_eer(taus, far, frr)
        t_dcf, far_d, frr_d = find_min_dcf(taus, far, frr, args.cfa, args.cfr, args.ptarget)
        auc = roc_auc(far, frr)
        n_imp, n_gen = impostor.size, genuine.size
        _, fa_lo, fa_hi = wilson(int(round(far_e * n_imp)), n_imp)
        _, fr_lo, fr_hi = wilson(int(round(frr_e * n_gen)), n_gen)

        print(f"  genuine n={n_gen} mean={genuine.mean():.3f} | impostor n={n_imp} mean={impostor.mean():.3f}")
        print(f"  AUC={auc:.4f}  EER={eer*100:.2f}%  tau*(EER)={t_eer:.3f}")
        print(f"     FAR@EER={far_e*100:.2f}% (95%CI {fa_lo*100:.1f}-{fa_hi*100:.1f}%) | "
              f"FRR@EER={frr_e*100:.2f}% (95%CI {fr_lo*100:.1f}-{fr_hi*100:.1f}%)")
        print(f"  min-DCF tau*={t_dcf:.3f}  FAR={far_d*100:.2f}%  FRR={frr_d*100:.2f}%")
        csv = f"threshold_eval_{name}.csv"
        with open(csv, "w", encoding="utf-8") as fh:
            fh.write("tau,FAR,FRR\n")
            for t, a, b in zip(taus, far, frr):
                fh.write(f"{t:.4f},{a:.6f},{b:.6f}\n")
        print(f"  curve -> {csv}\n")
        rows.append((name, auc, eer, t_eer, far_e, frr_e))

    if rows:
        print("================ SUMMARY (pick lowest EER) ================")
        print(f"{'backend':12} {'AUC':>7} {'EER%':>7} {'tau*':>7} {'FAR%':>7} {'FRR%':>7}")
        for name, auc, eer, t, fa, fr in sorted(rows, key=lambda r: r[2]):
            print(f"{name:12} {auc:7.4f} {eer*100:7.2f} {t:7.3f} {fa*100:7.2f} {fr*100:7.2f}")
        best = min(rows, key=lambda r: r[2])
        print(f"\n  -> BEST: ML_BACKEND={best[0]}  VERIFICATION_THRESHOLD={best[3]:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
