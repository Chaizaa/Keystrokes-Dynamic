"""
Utility for keystroke biometric processing.

Provides the KeystrokeProcessor class to parse raw events into timing features.
"""

from __future__ import annotations

import hashlib
import statistics
from collections import deque
from typing import Deque, Dict, List, Optional, Tuple


class KeystrokeProcessor:
    """
    Processor to convert raw JS events into biometric timing vectors.
    """

    MODIFIER_CODES = {
        "ShiftLeft", "ShiftRight",
        "ControlLeft", "ControlRight",
        "AltLeft", "AltRight",
        "MetaLeft", "MetaRight",
        "CapsLock",
    }

    def __init__(self, max_allowed_backspace: int = 4, decimals: int = 4):
        self.max_allowed_backspace = max_allowed_backspace
        self.decimals = decimals

    def round_val(self, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        return round(float(value), self.decimals)

    def round_vec(self, vec: List[float]) -> List[float]:
        return [round(v, self.decimals) for v in vec]

    def compute_vector_stats(self, vec: List[float]) -> Dict[str, float]:
        if not vec:
            return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "cv": 0.0}
        
        mean = statistics.mean(vec)
        std = statistics.stdev(vec) if len(vec) > 1 else 0.0
        cv = (std / mean) if mean != 0.0 else 0.0
        
        return {
            "mean": self.round_val(mean),
            "std": self.round_val(std),
            "min": self.round_val(min(vec)),
            "max": self.round_val(max(vec)),
            "cv": self.round_val(cv),
        }

    def assess_quality(self, features: Dict) -> Dict:
        """Score a sample and return quality label + warnings."""
        warnings = []
        score = 100

        h_vec = features.get("H_vector", [])
        dd_vec = features.get("DD_vector", [])
        ud_vec = features.get("UD_vector", [])


        ### Seharusnya long hold times tidak perlu dibatasi karena dalam sistem ini justru itu adalah tujuan utama dari keystroke dynamics, dengan membuat password yang bisa bervariasi dalam waktu penekanannya
        if any(h > 1.0 for h in h_vec):
            warnings.append("Very long hold times detected (> 1s)")
            score -= 20

        if any(dd > 2.0 for dd in dd_vec):
            warnings.append("Long pauses detected (> 2s)")
            score -= 15

        super_fast = sum(1 for dd in dd_vec if 0 < dd < 0.05)
        if super_fast > len(dd_vec) * 0.3:
            warnings.append("Unusually fast typing (< 50ms)")
            score -= 10

        if len(dd_vec) > 1:
            mean_v = statistics.mean(dd_vec)
            if mean_v > 0 and statistics.stdev(dd_vec) > mean_v * 1.5:
                warnings.append("High timing variance (inconsistent rhythm)")
                score -= 10

        neg_ud = sum(1 for ud in ud_vec if ud < -0.2)
        if neg_ud > len(ud_vec) * 0.5:
            warnings.append("Extreme key overlap detected")
            score -= 10

        if features.get("typing_rollover_ratio", 0) > 0.8:
            score -= 5

        label = "good" if score >= 80 else ("questionable" if score >= 60 else "poor")
        return {
            "quality_label": label,
            "quality_score": max(0, score),
            "quality_warnings": warnings,
        }

    def process(self, raw_events: List[Dict], username: str) -> Dict:
        """Parse raw events into features and reconstructed password."""
        raw_events = sorted(raw_events, key=lambda x: x["t"])
        raw_events = [x for x in raw_events if x.get("code") not in self.MODIFIER_CODES]

        if not raw_events:
            return {"status": "error", "msg": "Data kosong"}

        total_duration = (raw_events[-1]["t"] - raw_events[0]["t"]) / 1000.0
        backspace_count = sum(1 for x in raw_events if x["code"] == "Backspace" and x["evt"] == "d")

        if backspace_count > self.max_allowed_backspace:
            return {
                "status": "error",
                "msg": f"Terlalu banyak hapus ({backspace_count}x). Maksimal {self.max_allowed_backspace}x.",
            }

        temp_keystrokes = []
        temp_dict: Dict[str, Deque[Tuple[int, str]]] = {}

        for x in raw_events:
            k_id = x["code"]
            if k_id == "Enter" or x.get("key") == "Enter":
                continue

            if x["evt"] == "d":
                temp_dict.setdefault(k_id, deque()).append((x["t"], x["key"]))
            elif x["evt"] == "u":
                if k_id in temp_dict and temp_dict[k_id]:
                    down_t, char = temp_dict[k_id].popleft()
                    if not temp_dict[k_id]:
                        del temp_dict[k_id]
                    temp_keystrokes.append({
                        "char": char, "code": k_id, "down": down_t, "up": x["t"],
                        "is_backspace": (k_id == "Backspace")
                    })

        temp_keystrokes.sort(key=lambda x: x["down"])
        if not temp_keystrokes:
            return {"status": "error", "msg": "Data tidak valid."}

        # Backspace handling
        final_stack = []
        for item in temp_keystrokes:
            if item["is_backspace"]:
                if final_stack: final_stack.pop()
            else:
                final_stack.append(item)

        if len(final_stack) < 2:
            return {"status": "error", "msg": "Password terlalu pendek."}

        # Password reconstruction
        real_password = ""
        char_seq = []
        mask_seq = []
        for k in final_stack:
            val = k["char"]
            if len(val) == 1:
                real_password += val
                char_seq.append(val)
                mask_seq.append("*")
            else:
                real_password += f"[{val}]"
                char_seq.append(f"[{val}]")
                mask_seq.append("[key]")

        # Feature extraction
        h_vec, dd_vec, ud_vec, uu_vec, du_vec = [], [], [], [], []
        for i, k in enumerate(final_stack):
            h_vec.append((k["up"] - k["down"]) / 1000.0)
            if i > 0:
                prev = final_stack[i-1]
                dd_vec.append((k["down"] - prev["down"]) / 1000.0)
                ud_vec.append((k["down"] - prev["up"]) / 1000.0)
                uu_vec.append((k["up"] - prev["up"]) / 1000.0)
                du_vec.append((k["up"] - prev["down"]) / 1000.0)

        rollover = sum(1 for ud in ud_vec if ud < 0) / len(ud_vec) if ud_vec else 0
        speed = len(final_stack) / total_duration if total_duration > 0 else 0.0

        h_s = self.compute_vector_stats(h_vec)
        dd_s = self.compute_vector_stats(dd_vec)
        ud_s = self.compute_vector_stats(ud_vec)
        uu_s = self.compute_vector_stats(uu_vec)
        du_s = self.compute_vector_stats(du_vec)

        features = {
            "H_vector": self.round_vec(h_vec),
            "DD_vector": self.round_vec(dd_vec),
            "UD_vector": self.round_vec(ud_vec),
            "UU_vector": self.round_vec(uu_vec),
            "DU_vector": self.round_vec(du_vec),
            "H_mean": h_s["mean"], "H_std": h_s["std"], "H_min": h_s["min"], "H_max": h_s["max"], "H_cv": h_s["cv"],
            "DD_mean": dd_s["mean"], "DD_std": dd_s["std"], "DD_min": dd_s["min"], "DD_max": dd_s["max"], "DD_cv": dd_s["cv"],
            "UD_mean": ud_s["mean"], "UD_std": ud_s["std"], "UD_min": ud_s["min"], "UD_max": ud_s["max"], "UD_cv": ud_s["cv"],
            "UU_mean": uu_s["mean"], "UU_std": uu_s["std"], "UU_min": uu_s["min"], "UU_max": uu_s["max"], "UU_cv": uu_s["cv"],
            "DU_mean": du_s["mean"], "DU_std": du_s["std"], "DU_min": du_s["min"], "DU_max": du_s["max"], "DU_cv": du_s["cv"],
            "total_duration": self.round_val(total_duration),
            "typing_speed": self.round_val(speed),
            "typing_rollover_ratio": self.round_val(rollover),
            "char_count": len(final_stack),
            "backspace_count": backspace_count,
            "char_sequence": char_seq,
            "masked_sequence": mask_seq,
        }

        return {
            "status": "success",
            "features": features,
            "password_hash": hashlib.sha256(real_password.encode()).hexdigest(),
            "real_password_string": real_password,
        }


# Legacy function wrappers for compatibility
_default_processor = KeystrokeProcessor()

def process_web_events(events, username):
    return _default_processor.process(events, username)

def assess_sample_quality(features):
    return _default_processor.assess_quality(features)

def compute_vector_stats(vec):
    return _default_processor.compute_vector_stats(vec)