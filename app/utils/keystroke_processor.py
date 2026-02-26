"""
Utility functions for keystroke biometric processing.

Public API
----------
- ``process_web_events(raw_events_from_js, username)``
    Parse raw JS key-down/key-up events and extract timing feature vectors.

- ``assess_sample_quality(features)``
    Score a feature dict and return quality label + warnings.

- ``compute_vector_stats(vec)``
    Calculate mean, std, min, max, and CV for a list of floats.
"""

import hashlib
import statistics
from typing import Dict, List, Tuple


def compute_vector_stats(vec: List[float]) -> Dict[str, float]:
    """
    Compute descriptive statistics for a timing vector.

    Args:
        vec: list of float timing values (seconds)

    Returns:
        dict with keys: mean, std, min, max, cv
            - cv (coefficient of variation) = std / mean, or 0 when mean == 0
    """
    if not vec:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "cv": 0.0}
    mean = statistics.mean(vec)
    std  = statistics.stdev(vec) if len(vec) > 1 else 0.0
    cv   = (std / mean) if mean != 0.0 else 0.0
    return {
        "mean": mean,
        "std":  std,
        "min":  min(vec),
        "max":  max(vec),
        "cv":   cv,
    }


def assess_sample_quality(features: Dict) -> Dict:
    """
    Assess the quality of a single keystroke sample and return non-blocking warnings.

    Args:
        features: feature dict returned by process_web_events() with optional
                  keys: H_vector, DD_vector, UD_vector, typing_rollover_ratio

    Returns:
        dict with keys:
          - quality_label (str): 'good', 'questionable', or 'poor'
          - quality_score (int): 0–100
          - quality_warnings (list[str]): human-readable warning messages
    """
    warnings = []
    score = 100

    H_vec  = features.get("H_vector", [])
    DD_vec = features.get("DD_vector", [])
    UD_vec = features.get("UD_vector", [])

    # Check 1: Extremely long hold times (> 1 second)
    long_holds = [h for h in H_vec if h > 1.0]
    if long_holds:
        warnings.append(f"Very long hold times detected: {len(long_holds)} keys held > 1s")
        score -= 20

    # Check 2: Extremely long pauses (DD > 2 seconds)
    long_pauses = [dd for dd in DD_vec if dd > 2.0]
    if long_pauses:
        warnings.append(f"Long pauses detected: {len(long_pauses)} intervals > 2s")
        score -= 15

    # Check 3: Extremely fast typing (DD < 0.05s = 50ms)
    super_fast = [dd for dd in DD_vec if 0 < dd < 0.05]
    if len(super_fast) > len(DD_vec) * 0.3:
        warnings.append(f"Unusually fast typing: {len(super_fast)} intervals < 50ms")
        score -= 10

    # Check 4: High variance in timing (inconsistent typing)
    if len(DD_vec) > 1:
        dd_mean = statistics.mean(DD_vec)
        dd_std  = statistics.stdev(DD_vec)
        if dd_mean > 0 and dd_std > dd_mean * 1.5:
            warnings.append("High timing variance detected (inconsistent rhythm)")
            score -= 10

    # Check 5: UD vector — terlalu banyak negatif (rollover ekstrem)  ✅ sekarang dipakai
    if UD_vec:
        neg_ud = [ud for ud in UD_vec if ud < -0.2]
        if len(neg_ud) > len(UD_vec) * 0.5:
            warnings.append(f"Extreme key overlap detected: {len(neg_ud)} UD intervals < -200ms")
            score -= 10

    # Check 6: Too many rollovers (> 80%)
    rollover_ratio = features.get("typing_rollover_ratio", 0)
    if rollover_ratio > 0.8:
        warnings.append(f"Very high rollover rate: {rollover_ratio*100:.0f}%")
        score -= 5

    if score >= 80:
        quality_label = "good"
    elif score >= 60:
        quality_label = "questionable"
    else:
        quality_label = "poor"

    return {
        "quality_label":    quality_label,
        "quality_score":    max(0, score),
        "quality_warnings": warnings,
    }


def process_web_events(raw_events_from_js: List[Dict], username: str) -> Dict:
    """
    Parse raw keystroke events from JavaScript and extract biometric timing features.

    Expected event format (each item in list)::

        {"t": <unix ms>, "evt": "d"|"u", "code": "KeyA", "key": "a"}

    Args:
        raw_events_from_js: list of key-event dicts sent by the frontend
        username: username of the user being measured (used for logging)

    Returns:
        dict with keys:
          - status (str): 'success' or 'error'
          - features (dict): timing vectors + aggregate statistics  *(on success)*
          - password_hash (str): SHA-256 of reconstructed password  *(on success)*
          - real_password_string (str): plaintext password           *(on success)*
          - msg (str): human-readable error description              *(on error)*
    """
    raw_events_from_js.sort(key=lambda x: x["t"])

    if not raw_events_from_js:
        return {"status": "error", "msg": "Data kosong"}

    start_time        = raw_events_from_js[0]["t"]
    end_time          = raw_events_from_js[-1]["t"]
    total_duration_sec = (end_time - start_time) / 1000.0

    backspace_count = sum(
        1 for x in raw_events_from_js if x["code"] == "Backspace" and x["evt"] == "d"
    )

    MAX_ALLOWED_BACKSPACE = 3
    if backspace_count > MAX_ALLOWED_BACKSPACE:
        return {
            "status": "error",
            "msg": f"Terlalu banyak hapus ({backspace_count}x). Maksimal {MAX_ALLOWED_BACKSPACE}x. Ulangi ketikan ini.",
        }

    # ✅ Hapus MAX_HOLD_NORMAL, MAX_HOLD_MODIFIER, MAX_HOLD_FOR_REPEAT — tidak dipakai
    temp_keystrokes = []
    temp_dict       = {}

    for x in raw_events_from_js:
        k_id = x["code"]

        if k_id == "Enter" or x.get("key") == "Enter":
            continue

        if x["evt"] == "d":
            if k_id not in temp_dict:
                temp_dict[k_id] = (x["t"], x["key"])

        elif x["evt"] == "u":
            if k_id in temp_dict:
                down_time, char_at_down = temp_dict[k_id]
                up_time = x["t"]
                del temp_dict[k_id]

                # ✅ Hapus is_modifier & limit — tidak dipakai untuk filter apapun
                temp_keystrokes.append(
                    {
                        "key_char":     char_at_down,
                        "key_code":     x["code"],
                        "down":         down_time,
                        "up":           up_time,
                        "is_backspace": (x["code"] == "Backspace"),
                    }
                )

    temp_keystrokes.sort(key=lambda x: x["down"])
    if not temp_keystrokes:
        return {"status": "error", "msg": "Data tidak valid."}

    # Handle Backspace
    final_stack = []
    for item in temp_keystrokes:
        if item["is_backspace"]:
            if final_stack:
                final_stack.pop()
        else:
            final_stack.append(item)

    if len(final_stack) < 2:
        return {"status": "error", "msg": "Password terlalu pendek."}

    real_password_string = ""
    char_sequence        = []
    masked_sequence      = []

    for k in final_stack:
        if len(k["key_char"]) == 1:
            real_password_string += k["key_char"]
            char_sequence.append(k["key_char"])
            masked_sequence.append("*")
        else:
            real_password_string += f"[{k['key_char']}]"
            char_sequence.append(f"[{k['key_char']}]")
            masked_sequence.append("[key]")

    password_hash = hashlib.sha256(real_password_string.encode()).hexdigest()

    # Extract timing features
    H_vector  = []
    DD_vector = []
    UD_vector = []
    UU_vector = []
    DU_vector = []

    for i, k in enumerate(final_stack):
        hold_time = (k["up"] - k["down"]) / 1000.0
        H_vector.append(hold_time)

        if i > 0:
            prev_k = final_stack[i - 1]
            DD_vector.append((k["down"] - prev_k["down"]) / 1000.0)
            UD_vector.append((k["down"] - prev_k["up"])   / 1000.0)
            UU_vector.append((k["up"]   - prev_k["up"])   / 1000.0)
            DU_vector.append((k["up"]   - prev_k["down"]) / 1000.0)

    overlap_count  = sum(1 for ud in UD_vector if ud < 0)
    rollover_ratio = overlap_count / len(UD_vector) if UD_vector else 0

    # Typing speed: characters per second (excluding backspaces)
    char_count   = len(final_stack)
    typing_speed = char_count / total_duration_sec if total_duration_sec > 0 else 0.0

    # Per-vector statistics (including coefficient of variation)
    H_stats  = compute_vector_stats(H_vector)
    DD_stats = compute_vector_stats(DD_vector)
    UD_stats = compute_vector_stats(UD_vector)
    UU_stats = compute_vector_stats(UU_vector)
    DU_stats = compute_vector_stats(DU_vector)

    features = {
        # Raw timing vectors
        "H_vector":  H_vector,
        "DD_vector": DD_vector,
        "UD_vector": UD_vector,
        "UU_vector": UU_vector,
        "DU_vector": DU_vector,
        # Nested stats dicts (convenient for downstream processing)
        "H_stats":   H_stats,
        "DD_stats":  DD_stats,
        "UD_stats":  UD_stats,
        "UU_stats":  UU_stats,
        "DU_stats":  DU_stats,
        # Flat stats matching UsersVector model columns
        "H_mean":  H_stats["mean"],  "H_std":  H_stats["std"],
        "H_min":   H_stats["min"],   "H_max":  H_stats["max"],  "H_cv":  H_stats["cv"],
        "DD_mean": DD_stats["mean"], "DD_std": DD_stats["std"],
        "DD_min":  DD_stats["min"],  "DD_max": DD_stats["max"], "DD_cv": DD_stats["cv"],
        "UD_mean": UD_stats["mean"], "UD_std": UD_stats["std"],
        "UD_min":  UD_stats["min"],  "UD_max": UD_stats["max"], "UD_cv": UD_stats["cv"],
        "UU_mean": UU_stats["mean"], "UU_std": UU_stats["std"],
        "UU_min":  UU_stats["min"],  "UU_max": UU_stats["max"], "UU_cv": UU_stats["cv"],
        "DU_mean": DU_stats["mean"], "DU_std": DU_stats["std"],
        "DU_min":  DU_stats["min"],  "DU_max": DU_stats["max"], "DU_cv": DU_stats["cv"],
        # Aggregate metrics
        "char_count":            char_count,
        "total_duration":        total_duration_sec,
        "typing_speed":          round(typing_speed, 4),
        "typing_rollover_ratio": rollover_ratio,
        "backspace_count":       backspace_count,
        "char_sequence":         char_sequence,
        "masked_sequence":       masked_sequence,
    }

    return {
        "status":               "success",
        "features":             features,
        "password_hash":        password_hash,
        "real_password_string": real_password_string,
    }