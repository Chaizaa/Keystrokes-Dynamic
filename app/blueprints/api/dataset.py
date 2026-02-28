"""
Dataset collection endpoints.

Routes
------
POST /api/dataset/register           — register new respondent, set their password
POST /api/dataset/submit             — submit one keystroke sample
GET  /api/dataset/status/<code>      — get progress for a subject
GET  /api/dataset/export             — download full dataset as CSV or JSON (protected by EXPORT_KEY)
"""

import csv
import hashlib
import io
import os
import traceback

from flask import Response, jsonify, request

from app.models import db
from app.utils.keystroke_processor import process_web_events

from ._shared import api_bp


# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/dataset/export", methods=["GET"])
def dataset_export():
    """
    Download the full collected dataset.

    Query params
    ------------
    key     : (required) must match EXPORT_KEY env var
    format  : "csv" (default) | "json"

    Examples
    --------
    /api/dataset/export?key=mysecret
    /api/dataset/export?key=mysecret&format=json
    """
    export_key = os.environ.get("EXPORT_KEY", "")
    if not export_key or request.args.get("key") != export_key:
        return jsonify({"error": "Unauthorized"}), 401

    from app.models.dataset import DatasetEntry, DatasetSubject

    rows = (
        db.session.query(DatasetEntry, DatasetSubject)
        .join(DatasetSubject, DatasetEntry.subject_id == DatasetSubject.id)
        .order_by(DatasetSubject.subject_code, DatasetEntry.repetition)
        .all()
    )

    fmt = request.args.get("format", "csv").lower()

    if fmt == "json":
        data = []
        for entry, subj in rows:
            data.append({
                "subject_code":  subj.subject_code,
                "name_initial":  subj.name_initial,
                "device_info":   subj.device_info,
                "repetition":    entry.repetition,
                "H_vector":      entry.H_vector,
                "DD_vector":     entry.DD_vector,
                "UD_vector":     entry.UD_vector,
                "UU_vector":     entry.UU_vector,
                "DU_vector":     entry.DU_vector,
                "H_mean":        entry.H_mean,  "H_std":   entry.H_std,
                "H_min":         entry.H_min,   "H_max":   entry.H_max,  "H_cv":  entry.H_cv,
                "DD_mean":       entry.DD_mean, "DD_std":  entry.DD_std,
                "DD_min":        entry.DD_min,  "DD_max":  entry.DD_max, "DD_cv": entry.DD_cv,
                "UD_mean":       entry.UD_mean, "UD_std":  entry.UD_std,
                "UD_min":        entry.UD_min,  "UD_max":  entry.UD_max, "UD_cv": entry.UD_cv,
                "UU_mean":       entry.UU_mean, "UU_std":  entry.UU_std,
                "UU_min":        entry.UU_min,  "UU_max":  entry.UU_max, "UU_cv": entry.UU_cv,
                "DU_mean":       entry.DU_mean, "DU_std":  entry.DU_std,
                "DU_min":        entry.DU_min,  "DU_max":  entry.DU_max, "DU_cv": entry.DU_cv,
                "total_duration": entry.total_duration,
                "typing_speed":  entry.typing_speed,
                "created_at":    entry.created_at.isoformat() if entry.created_at else None,
            })
        return jsonify(data)

    # Default: CSV
    fieldnames = [
        "subject_code", "name_initial", "device_info", "repetition",
        "H_vector", "DD_vector", "UD_vector", "UU_vector", "DU_vector",
        "H_mean", "H_std", "H_min", "H_max", "H_cv",
        "DD_mean", "DD_std", "DD_min", "DD_max", "DD_cv",
        "UD_mean", "UD_std", "UD_min", "UD_max", "UD_cv",
        "UU_mean", "UU_std", "UU_min", "UU_max", "UU_cv",
        "DU_mean", "DU_std", "DU_min", "DU_max", "DU_cv",
        "total_duration", "typing_speed", "created_at",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for entry, subj in rows:
        writer.writerow({
            "subject_code":   subj.subject_code,
            "name_initial":   subj.name_initial,
            "device_info":    subj.device_info,
            "repetition":     entry.repetition,
            "H_vector":       entry.H_vector,
            "DD_vector":      entry.DD_vector,
            "UD_vector":      entry.UD_vector,
            "UU_vector":      entry.UU_vector,
            "DU_vector":      entry.DU_vector,
            "H_mean":  entry.H_mean,  "H_std":  entry.H_std,
            "H_min":   entry.H_min,   "H_max":  entry.H_max,  "H_cv":  entry.H_cv,
            "DD_mean": entry.DD_mean, "DD_std": entry.DD_std,
            "DD_min":  entry.DD_min,  "DD_max": entry.DD_max, "DD_cv": entry.DD_cv,
            "UD_mean": entry.UD_mean, "UD_std": entry.UD_std,
            "UD_min":  entry.UD_min,  "UD_max": entry.UD_max, "UD_cv": entry.UD_cv,
            "UU_mean": entry.UU_mean, "UU_std": entry.UU_std,
            "UU_min":  entry.UU_min,  "UU_max": entry.UU_max, "UU_cv": entry.UU_cv,
            "DU_mean": entry.DU_mean, "DU_std": entry.DU_std,
            "DU_min":  entry.DU_min,  "DU_max": entry.DU_max, "DU_cv": entry.DU_cv,
            "total_duration": entry.total_duration,
            "typing_speed":   entry.typing_speed,
            "created_at":     entry.created_at.isoformat() if entry.created_at else None,
        })
    csv_bytes = buf.getvalue().encode("utf-8")
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=dataset_export.csv"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_device_info(user_agent: str) -> str:
    """Extract a concise device/browser label from a User-Agent string."""
    ua = user_agent.lower()

    if "android" in ua:
        os_label = "Android"
    elif "iphone" in ua or "ipad" in ua:
        os_label = "iOS"
    elif "windows" in ua:
        os_label = "Windows"
    elif "mac os" in ua or "macintosh" in ua:
        os_label = "macOS"
    elif "linux" in ua:
        os_label = "Linux"
    else:
        os_label = "Unknown OS"

    if "edg/" in ua or "edge/" in ua:
        browser = "Edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"
    elif "chrome/" in ua and "chromium" not in ua:
        browser = "Chrome"
    elif "firefox/" in ua:
        browser = "Firefox"
    elif "safari/" in ua and "chrome" not in ua:
        browser = "Safari"
    else:
        browser = "Other"

    return f"{browser}/{os_label}"


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.route("/dataset/register", methods=["POST"])
def dataset_register():
    """Register a new dataset respondent.

    Request JSON:
        name_initial  str   (optional)
        password      str   (required) Password the subject will type 100 times

    Response JSON:
        subject_code   str
        subject_id     int
        collected      int   Always 0 for new subjects
        total_samples  int
    """
    try:
        from app.models.dataset import (
            DATASET_TOTAL_SAMPLES,
            DatasetSubject,
        )

        data = request.get_json(silent=True) or {}
        name_initial = (data.get("name_initial") or "").strip() or None
        password     = (data.get("password") or "").strip()
        device_info  = _parse_device_info(request.headers.get("User-Agent", ""))

        if not password:
            return jsonify({"success": False, "error": "Password wajib diisi."}), 400
        if len(password) < 6:
            return jsonify({"success": False, "error": "Password minimal 6 karakter."}), 400

        pw_hash = hashlib.sha256(password.encode()).hexdigest()

        subject_code = DatasetSubject.next_subject_code()
        subject = DatasetSubject(
            subject_code  = subject_code,
            name_initial  = name_initial,
            device_info   = device_info,
            password_hash = pw_hash,
        )
        db.session.add(subject)
        db.session.commit()

        return jsonify({
            "success":       True,
            "subject_code": subject.subject_code,
            "subject_id":   subject.id,
            "collected":    0,
            "total_samples": DATASET_TOTAL_SAMPLES,
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] dataset_register: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/dataset/submit", methods=["POST"])
def dataset_submit():
    """Submit one keystroke sample.

    The global repetition number is computed server-side from entry count,
    so the client does not need to track position.

    Request JSON:
        subject_code  str   (required)
        raw_events    list  (required)

    Response JSON:
        success        bool
        collected      int   Samples saved so far (after this one)
        total_samples  int
        all_done       bool
        progress       dict  {collected, total}
    """
    try:
        from app.models.dataset import (
            DATASET_TOTAL_SAMPLES,
            DatasetEntry,
            DatasetSubject,
        )

        data = request.get_json(silent=True) or {}
        subject_code = data.get("subject_code", "").strip()
        raw_events   = data.get("raw_events", [])

        if not subject_code:
            return jsonify({"success": False, "error": "subject_code wajib disertakan."}), 400
        if not raw_events:
            return jsonify({"success": False, "error": "raw_events wajib disertakan."}), 400

        subject = DatasetSubject.query.filter_by(subject_code=subject_code).first()
        if subject is None:
            return jsonify({"success": False, "error": "Subjek tidak ditemukan. Silakan daftar terlebih dahulu."}), 404

        # Compute next global rep server-side
        collected_so_far = subject.total_entries()
        if collected_so_far >= DATASET_TOTAL_SAMPLES:
            return jsonify({"success": False, "error": "Semua sampel sudah selesai."}), 400

        global_rep = collected_so_far + 1

        # Process keystroke events
        result = process_web_events(raw_events, username=f"dataset::{subject_code}")
        if result["status"] != "success":
            return jsonify({"success": False, "error": result.get("msg", "Gagal memproses data ketikan.")}), 400

        # Verify password hash
        reconstructed = result.get("real_password_string", "")
        reconstructed_hash = hashlib.sha256(reconstructed.encode()).hexdigest()
        if subject.password_hash and reconstructed_hash != subject.password_hash:
            return jsonify({
                "success": False,
                "error": "Kata sandi tidak sesuai dengan yang didaftarkan. Ketik ulang kata sandi yang sama.",
            }), 400

        features = result["features"]
        entry = DatasetEntry(
            subject_id     = subject.id,
            repetition     = global_rep,
            total_duration = features.get("total_duration"),
            typing_speed   = features.get("typing_speed"),
        )
        for vec_name in ("H", "DD", "UD", "UU", "DU"):
            entry.set_vector(vec_name, features.get(f"{vec_name}_vector", []))
        for vec_name in ("H", "DD", "UD", "UU", "DU"):
            for stat in ("mean", "std", "min", "max", "cv"):
                val = features.get(f"{vec_name}_{stat}")
                if val is not None:
                    setattr(entry, f"{vec_name}_{stat}", float(val))

        db.session.add(entry)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({"success": False, "error": "Sample ini sudah tersimpan. Refresh tidak perlu diulang."}), 409

        collected = subject.total_entries()
        all_done  = (collected >= DATASET_TOTAL_SAMPLES)

        return jsonify({
            "success":       True,
            "collected":     collected,
            "total_samples": DATASET_TOTAL_SAMPLES,
            "all_done":      all_done,
            "progress":      {"collected": collected, "total": DATASET_TOTAL_SAMPLES},
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] dataset_submit: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@api_bp.route("/dataset/status/<subject_code>", methods=["GET"])
def dataset_status(subject_code):
    """Return current progress for a subject.

    Response JSON:
        subject_code   str
        total_entries  int
        is_complete    bool
        collected      int
        total_samples  int
    """
    try:
        from app.models.dataset import (
            DATASET_TOTAL_SAMPLES,
            DatasetSubject,
        )

        subject = DatasetSubject.query.filter_by(subject_code=subject_code).first()
        if subject is None:
            return jsonify({"success": False, "error": "Subjek tidak ditemukan."}), 404

        collected = subject.total_entries()

        return jsonify({
            "success":       True,
            "subject_code": subject.subject_code,
            "total_entries": collected,
            "is_complete":   subject.is_complete(),
            "collected":     collected,
            "total_samples": DATASET_TOTAL_SAMPLES,
        }), 200

    except Exception as e:
        print(f"[ERROR] dataset_status: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
