"""
Utility functions for keystroke processing
"""

import statistics


def assess_sample_quality(features):
    """
    Assess sample quality and return warnings (non-blocking)

    Args:
        features: Dictionary containing keystroke feature vectors

    Returns:
        Dictionary with quality_label, quality_score, and quality_warnings
    """
    warnings = []
    score = 100

    # Extract vectors for analysis
    H_vec = features.get("H_vector", [])
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
    if len(super_fast) > len(DD_vec) * 0.3:  # More than 30% super fast
        warnings.append(f"Unusually fast typing: {len(super_fast)} intervals < 50ms")
        score -= 10

    # Check 4: High variance in timing (inconsistent typing)
    if len(DD_vec) > 0:
        dd_mean = statistics.mean(DD_vec)
        dd_std = statistics.stdev(DD_vec) if len(DD_vec) > 1 else 0
        if dd_std > dd_mean * 1.5:  # CV > 150%
            warnings.append(f"High timing variance detected (inconsistent rhythm)")
            score -= 10

    # Check 5: Too many rollovers (> 80%)
    rollover_ratio = features.get("typing_rollover_ratio", 0)
    if rollover_ratio > 0.8:
        warnings.append(f"Very high rollover rate: {rollover_ratio*100:.0f}%")
        score -= 5

    # Determine quality label
    if score >= 80:
        quality_label = "good"
    elif score >= 60:
        quality_label = "questionable"
    else:
        quality_label = "poor"

    return {
        "quality_label": quality_label,
        "quality_score": max(0, score),
        "quality_warnings": warnings,
    }


def process_web_events(raw_events_from_js, username):
    """
    Process raw keystroke events from JavaScript and extract biometric features

    Args:
        raw_events_from_js: List of keystroke events with 'evt', 'key', 'code', 't' keys
        username: Username for context

    Returns:
        Dictionary with status, features, or error message
    """
    raw_events_from_js.sort(key=lambda x: x["t"])

    if not raw_events_from_js:
        return {"status": "error", "msg": "Data kosong"}

    # Global features
    start_time = raw_events_from_js[0]["t"]
    end_time = raw_events_from_js[-1]["t"]
    total_duration_sec = (end_time - start_time) / 1000.0

    # Count Backspace
    backspace_count = sum(
        1 for x in raw_events_from_js if x["code"] == "Backspace" and x["evt"] == "d"
    )

    # Validate Backspace limit
    MAX_ALLOWED_BACKSPACE = 3

    if backspace_count > MAX_ALLOWED_BACKSPACE:
        return {
            "status": "error",
            "msg": f"Terlalu banyak hapus ({backspace_count}x). Maksimal {MAX_ALLOWED_BACKSPACE}x. Ulangi ketikan ini.",
        }

    # Data Cleaning & Pairing
    MAX_HOLD_NORMAL = 800
    MAX_HOLD_MODIFIER = 5000
    MAX_HOLD_FOR_REPEAT = 800

    temp_keystrokes = []
    temp_dict = {}

    for x in raw_events_from_js:
        k_id = x["code"]

        # Filter Enter key - not relevant for biometric analysis
        if k_id == "Enter" or x.get("key") == "Enter":
            continue

        if x["evt"] == "d":
            # Store first keydown time only
            if k_id not in temp_dict:
                temp_dict[k_id] = (x["t"], x["key"])

        elif x["evt"] == "u":
            if k_id in temp_dict:
                down_time, char_at_down = temp_dict[k_id]

                up_time = x["t"]
                hold_time = up_time - down_time
                del temp_dict[k_id]

                is_modifier = (
                    "Shift" in k_id
                    or "Control" in k_id
                    or "Alt" in k_id
                    or "Meta" in k_id
                    or "CapsLock" in k_id
                )
                limit = MAX_HOLD_MODIFIER if is_modifier else MAX_HOLD_NORMAL

                temp_keystrokes.append(
                    {
                        "key_char": char_at_down,
                        "key_code": x["code"],
                        "down": down_time,
                        "up": up_time,
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

    # Build password string and sequences
    real_password_string = ""
    char_sequence = []
    masked_sequence = []

    for k in final_stack:
        if len(k["key_char"]) == 1:
            real_password_string += k["key_char"]
            char_sequence.append(k["key_char"])
            masked_sequence.append("*")
        else:
            real_password_string += f"[{k['key_char']}]"
            char_sequence.append(f"[{k['key_char']}]")
            masked_sequence.append("[key]")

    import hashlib

    password_hash = hashlib.sha256(real_password_string.encode()).hexdigest()

    # Extract timing features
    H_vector = []
    DD_vector = []
    UD_vector = []

    for i, k in enumerate(final_stack):
        hold_time = (k["up"] - k["down"]) / 1000.0
        H_vector.append(hold_time)

        if i > 0:
            prev_k = final_stack[i - 1]
            dd = (k["down"] - prev_k["down"]) / 1000.0
            ud = (k["down"] - prev_k["up"]) / 1000.0
            DD_vector.append(dd)
            UD_vector.append(ud)

    # Calculate rollover ratio
    overlap_count = sum(1 for ud in UD_vector if ud < 0)
    rollover_ratio = overlap_count / len(UD_vector) if UD_vector else 0

    # Calculate statistics
    def calc_stats(vec):
        if not vec:
            return {"mean": 0, "std": 0, "min": 0, "max": 0}
        return {
            "mean": statistics.mean(vec),
            "std": statistics.stdev(vec) if len(vec) > 1 else 0,
            "min": min(vec),
            "max": max(vec),
        }

    features = {
        "H_vector": H_vector,
        "DD_vector": DD_vector,
        "UD_vector": UD_vector,
        "H_stats": calc_stats(H_vector),
        "DD_stats": calc_stats(DD_vector),
        "UD_stats": calc_stats(UD_vector),
        "char_count": len(final_stack),
        "total_duration": total_duration_sec,
        "typing_rollover_ratio": rollover_ratio,
        "backspace_count": backspace_count,
        "char_sequence": char_sequence,
        "masked_sequence": masked_sequence,
    }

    return {
        "status": "success",
        "features": features,
        "password_hash": password_hash,
        "real_password_string": real_password_string,
    }
