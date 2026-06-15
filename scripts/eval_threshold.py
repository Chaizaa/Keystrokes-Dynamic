"""Keystroke-dynamics threshold evaluation for the thesis.

READ-ONLY analysis tool. It never modifies the app, its models, or the database
— it only reads collected samples and computes metrics. Running it changes
nothing about the live system.

It mirrors how the PRODUCTION system actually decides a threshold for each
backend:

  statistical (template distance):
      A single GLOBAL threshold (production uses a fixed 0.70). This tool sweeps
      every threshold and reports the optimal one (EER + min-DCF) so the global
      number can be chosen by calculation instead of guessed.
      Protocol: leave-one-out genuine + cross-subject impostor.

  rf / svm (two-class target-vs-rest):
      Production computes a PER-USER threshold during training (EER on a
      validation split) and stores it per user. This tool REPLICATES that exact
      training procedure offline (60/20/20 stratified split, random_state=42,
      same model params, EER threshold from the validation ROC) for each
      subject, and reports each subject's threshold + held-out test EER, plus the
      aggregate. No models are written to the DB.

Usage
-----
Self-test on synthetic data (no DB):
    venv/Scripts/python.exe scripts/eval_threshold.py --synthetic 10 15

Real data collected via /dataset:
    PYTHONPATH=. venv/Scripts/python.exe scripts/eval_threshold.py --source dataset

Dump the REAL per-user thresholds/EER already trained in the DB (read-only):
    PYTHONPATH=. venv/Scripts/python.exe scripts/eval_threshold.py --dump-trained
"""
from __future__ import annotations

import argparse
import json
import math
import statistics

import numpy as np

# 27 features used by the rf/svm backends (mirrors base_model_service.FEATURE_COLUMNS)
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
    """LOO genuine + cross-subject impostor -> (genuine_scores, impostor_scores)."""
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
# RF / SVM — replicate the production PER-USER training + threshold exactly
# ===========================================================================
def make_svm():
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC
    return Pipeline([
        ("scaler", StandardScaler()),
        ("svc", SVC(kernel="rbf", C=10.0, gamma="scale", class_weight="balanced",
                    probability=True, random_state=42)),
    ])


def make_rf():
    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(
        n_estimators=200, max_depth=None, min_samples_leaf=2, max_features="sqrt",
        class_weight="balanced", random_state=42, n_jobs=-1,
    )


def _eer_threshold(y_true, probs):
    """(eer, threshold) at the ROC equal-error point — copy of production."""
    from sklearn.metrics import roc_curve
    fpr, tpr, thr = roc_curve(y_true, probs)
    fnr = 1.0 - tpr
    idx = int(np.argmin(np.abs(fpr - fnr)))
    return float((fpr[idx] + fnr[idx]) / 2.0), float(thr[idx])


def evaluate_classifier_peruser(subjects, make_model):
    """For each subject, replicate production training and return its per-user
    threshold (from val EER) and held-out test EER. Returns list of dicts."""
    from sklearn.model_selection import train_test_split
    feats = {s: np.array([smp["featvec"] for smp in reps], dtype=float)
             for s, reps in subjects.items()}
    subs = list(subjects)
    out, skipped = [], 0
    for u in subs:
        Xpos = feats[u]
        Xneg = np.vstack([feats[o] for o in subs if o != u])
        X_all = np.vstack([Xpos, Xneg])
        y_all = np.r_[np.ones(len(Xpos), int), np.zeros(len(Xneg), int)]
        try:
            X_tr, X_tmp, y_tr, y_tmp = train_test_split(
                X_all, y_all, test_size=0.4, stratify=y_all, random_state=42)
            X_val, X_te, y_val, y_te = train_test_split(
                X_tmp, y_tmp, test_size=0.5, stratify=y_tmp, random_state=42)
            model = make_model()
            model.fit(X_tr, y_tr)
            i1 = list(model.classes_).index(1)
            val_eer, thr = _eer_threshold(y_val, model.predict_proba(X_val)[:, i1])
            test_eer, _ = _eer_threshold(y_te, model.predict_proba(X_te)[:, i1])
            out.append({"subject": u, "threshold": thr, "val_eer": val_eer, "test_eer": test_eer})
        except Exception:
            skipped += 1
    return out, skipped


# ===========================================================================
# Global-threshold metrics (statistical)
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


def dump_trained():
    """Read-only: print the REAL per-user thresholds + test EER already stored
    by production training in user_ml_models. Touches nothing."""
    from sqlalchemy import select
    from app import create_app
    app = create_app()
    with app.app_context():
        from app.models import db
        from app.models.user_ml_model import UserMLModel
        rows = db.session.execute(select(UserMLModel)).scalars().all()
        if not rows:
            print("No trained per-user models found in user_ml_models.")
            return
        print(f"{'username':24} {'type':18} {'threshold':>10} {'test_EER%':>10}")
        for r in rows:
            eer = ""
            try:
                m = json.loads(r.metrics_json or "{}")
                e = (m.get("test") or {}).get("EER")
                eer = f"{e*100:.2f}" if e is not None else ""
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
            print(f"{(r.username or ''):24} {(r.model_type or ''):18} "
                  f"{float(r.threshold):10.4f} {eer:>10}")


# ===========================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", choices=["dataset", "users"])
    ap.add_argument("--synthetic", nargs=2, type=int, metavar=("SUBJECTS", "REPS"))
    ap.add_argument("--dump-trained", action="store_true",
                    help="read-only: print real per-user thresholds/EER from the DB and exit")
    ap.add_argument("--sep", type=float, default=1.0, help="synthetic separability")
    ap.add_argument("--cfa", type=float, default=1.0, help="cost of a false accept (statistical DCF)")
    ap.add_argument("--cfr", type=float, default=1.0, help="cost of a false reject (statistical DCF)")
    ap.add_argument("--ptarget", type=float, default=0.5, help="prior P(genuine)")
    ap.add_argument("--backends", default="statistical,rf,svm")
    args = ap.parse_args()

    if args.dump_trained:
        dump_trained()
        return 0

    if args.synthetic:
        subjects = make_synthetic(*args.synthetic, sep=args.sep)
        print(f"[synthetic] {args.synthetic[0]} subjects x {args.synthetic[1]} reps (sep={args.sep})")
    elif args.source:
        subjects = load_from_db(args.source)
        print(f"[db:{args.source}] loaded {len(subjects)} subjects")
    else:
        ap.error("provide --synthetic SUBJECTS REPS, or --source {dataset,users}, or --dump-trained")

    subjects = {k: v for k, v in subjects.items() if len(v) >= 2}
    if len(subjects) < 3:
        print("ERROR: need >=3 subjects with >=2 reps each (rf/svm need negatives). Collect more.")
        return 1
    rp = [len(v) for v in subjects.values()]
    print(f"subjects={len(subjects)}  reps/subject min={min(rp)} max={max(rp)} total={sum(rp)}\n")

    summary = []  # (backend, eer, how, threshold_desc)
    for name in [b.strip() for b in args.backends.split(",") if b.strip()]:

        # ---- statistical: single GLOBAL threshold (sweep) -----------------
        if name == "statistical":
            print("--- statistical (global threshold) ---")
            genuine, impostor = evaluate_statistical(subjects)
            if genuine.size == 0 or impostor.size == 0:
                print("  not enough comparable samples\n"); continue
            taus, far, frr = sweep(genuine, impostor)
            t_eer, eer, far_e, frr_e = find_eer(taus, far, frr)
            t_dcf, far_d, frr_d = find_min_dcf(taus, far, frr, args.cfa, args.cfr, args.ptarget)
            auc = roc_auc(far, frr)
            n_imp, n_gen = impostor.size, genuine.size
            _, fa_lo, fa_hi = wilson(int(round(far_e * n_imp)), n_imp)
            _, fr_lo, fr_hi = wilson(int(round(frr_e * n_gen)), n_gen)
            print(f"  genuine n={n_gen} | impostor n={n_imp} | AUC={auc:.4f}")
            print(f"  EER={eer*100:.2f}%  global tau*={t_eer:.3f}")
            print(f"     FAR@EER={far_e*100:.2f}% (95%CI {fa_lo*100:.1f}-{fa_hi*100:.1f}%) | "
                  f"FRR@EER={frr_e*100:.2f}% (95%CI {fr_lo*100:.1f}-{fr_hi*100:.1f}%)")
            print(f"  min-DCF tau*={t_dcf:.3f}  FAR={far_d*100:.2f}%  FRR={frr_d*100:.2f}%")
            with open("threshold_eval_statistical.csv", "w", encoding="utf-8") as fh:
                fh.write("tau,FAR,FRR\n")
                for t, a, b in zip(taus, far, frr):
                    fh.write(f"{t:.4f},{a:.6f},{b:.6f}\n")
            print("  curve -> threshold_eval_statistical.csv\n")
            summary.append((name, eer, "global", f"tau*={t_eer:.3f}"))
            continue

        # ---- rf / svm: PER-USER threshold (replicate production training) --
        if name in ("rf", "svm"):
            print(f"--- {name} (per-user threshold, production-replica) ---")
            maker = make_rf if name == "rf" else make_svm
            per, skipped = evaluate_classifier_peruser(subjects, maker)
            if not per:
                print(f"  could not train any subject (skipped={skipped})\n"); continue
            test_eers = [p["test_eer"] for p in per]
            thrs = [p["threshold"] for p in per]
            print(f"  trained {len(per)} subjects (skipped={skipped})")
            print(f"  {'subject':18} {'thr(per-user)':>14} {'test_EER%':>10}")
            for p in per:
                print(f"  {p['subject']:18} {p['threshold']:14.4f} {p['test_eer']*100:10.2f}")
            mean_eer = float(np.mean(test_eers))
            print(f"  --> mean per-user test EER = {mean_eer*100:.2f}%  "
                  f"(median {np.median(test_eers)*100:.2f}%)")
            print(f"  --> per-user thresholds: mean={np.mean(thrs):.4f} "
                  f"min={min(thrs):.4f} max={max(thrs):.4f}  (each user keeps its OWN)")
            with open(f"threshold_eval_{name}.csv", "w", encoding="utf-8") as fh:
                fh.write("subject,threshold,val_eer,test_eer\n")
                for p in per:
                    fh.write(f"{p['subject']},{p['threshold']:.4f},{p['val_eer']:.6f},{p['test_eer']:.6f}\n")
            print(f"  per-user table -> threshold_eval_{name}.csv\n")
            summary.append((name, mean_eer, "per-user", f"per-user (mean {np.mean(thrs):.3f})"))
            continue

        print(f"  (skip unknown backend '{name}')")

    if summary:
        print("================ SUMMARY (lower EER = better separability) ================")
        print(f"{'backend':12} {'EER%':>7}  {'threshold':<26} note")
        for name, eer, how, desc in sorted(summary, key=lambda r: r[1]):
            note = "global, tunable" if how == "global" else "auto per-user at training"
            print(f"{name:12} {eer*100:7.2f}  {desc:<26} {note}")
        print("\nNotes:")
        print(" - statistical: ONE global threshold -> set it (production hardcodes 0.70).")
        print(" - rf/svm: threshold is computed PER USER at training; not a single global value.")
        print(" - VERIFICATION_THRESHOLD in .env is currently NOT read by the app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
