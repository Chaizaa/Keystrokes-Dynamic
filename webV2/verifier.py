import numpy as np
import json

class Verifier:
    def __init__(self):
        self.MAX_BACKSPACE = 3
        self.OUTLIER_CAP = 1.0 
        self.THRESHOLD = 0.35
    
    def _parse_vector(self, vector_data):
        if isinstance(vector_data, str):
            try: return np.array(json.loads(vector_data))
            except: return np.array([])
        return np.array(vector_data)

    def verify_user(self, new_features, enrollment_samples):
        """Statistical verification only (no ML)"""
        
        if not enrollment_samples:
            return {"result": False, "reason": "No enrollment data"}
            
        # Check password hash
        stored_hash = enrollment_samples[0]['password_hash']
        if new_features['password_hash'] != stored_hash:
            return {"result": False, "reason": "Wrong password"}

        # Statistical comparison (same as before)
        # ... (keep the vector comparison logic)
        
        return {"result": True, "score": 0.1}