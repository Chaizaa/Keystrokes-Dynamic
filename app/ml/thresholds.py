EXACT_MATCH_THRESHOLD = 0.95
HIGH_CONFIDENCE_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.70
LOW_CONFIDENCE_THRESHOLD = 0.55

MIN_SAMPLES_FOR_VERIFICATION = 3
RECOMMENDED_SAMPLES = 10


def get_confidence_label(score: float) -> str:
    if score >= EXACT_MATCH_THRESHOLD:
        return "exact_match"
    elif score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high"
    elif score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"
    elif score >= LOW_CONFIDENCE_THRESHOLD:
        return "low"
    else:
        return "failed"