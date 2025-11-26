import numpy as np
import json

class Verifier:
    def __init__(self):
        self.MAX_BACKSPACE = 3
        self.OUTLIER_CAP = 1.0 
        self.THRESHOLD = 0.35 # Dilonggarkan sedikit karena sekarang ada banyak fitur
    
    def _parse_vector(self, vector_data):
        if isinstance(vector_data, str):
            try: return np.array(json.loads(vector_data))
            except: return np.array([])
        return np.array(vector_data)

    def calculate_capped_distance(self, vec_input, vec_profile, label=""):
        if len(vec_input) != len(vec_profile):
            print(f"[DEBUG {label}] GAGAL: Panjang vektor beda")
            return float('inf')

        diffs = np.abs(vec_input - vec_profile)
        capped_diffs = np.clip(diffs, 0, self.OUTLIER_CAP)
        mean_dist = np.mean(capped_diffs)
        
        # Debug Print
        # print(f"--> {label} Dist: {mean_dist:.4f}")
        return mean_dist

    def verify_user(self, new_features, enrollment_samples):
        print("\n" + "="*50)
        print("MEMULAI VERIFIKASI BIOMETRIK (PERBAIKAN)")
        print("="*50)

        if not enrollment_samples:
            return {"result": False, "reason": "Belum ada data latihan."}
            
        # Cek Password Hash
        stored_hash = enrollment_samples[0]['password_hash']
        if new_features['password_hash'] != stored_hash:
            return {"result": False, "reason": "Password Salah."}

        # ---------------------------------------------------------
        # PERBAIKAN 1: Cari Panjang Vektor Dominan (Mode)
        # Agar satu sampel rusak tidak menghancurkan profil
        # ---------------------------------------------------------
        vector_keys = ['H_vector', 'DD_vector', 'UD_vector', 'UU_vector', 'DU_vector']
        
        # Kumpulkan semua panjang vektor dari sampel H_vector
        lengths = []
        for row in enrollment_samples:
            vec = self._parse_vector(row['H_vector'])
            lengths.append(len(vec))
        
        # Cari modus (panjang yang paling sering muncul)
        if not lengths: return {"result": False, "reason": "Data latihan rusak."}
        dominant_len = max(set(lengths), key=lengths.count)
        
        print(f"[INFO] Panjang vektor dominan: {dominant_len}")

        # ---------------------------------------------------------
        # 2. BANGUN PROFIL USER (Hanya pakai sampel yang panjangnya sesuai)
        # ---------------------------------------------------------
        mean_profile = {}
        
        # Filter sampel yang "kotor" (panjang beda atau ada backspace berlebih)
        clean_samples = [
            row for row in enrollment_samples 
            if len(self._parse_vector(row['H_vector'])) == dominant_len
            # Opsional: Abaikan sampel yang banyak backspace untuk profil lebih akurat
            # and int(row['backspace_count']) == 0 
        ]

        if not clean_samples:
             return {"result": False, "reason": "Tidak ada data sampel yang konsisten."}

        print(f"[INFO] Membangun Profil dari {len(clean_samples)} sampel bersih.")

        # A. Profil Vektor
        for key in vector_keys:
            vecs = []
            for row in clean_samples:
                v = self._parse_vector(row[key])
                vecs.append(v)
            mean_profile[key] = np.mean(vecs, axis=0)

        # B. Profil Macro
        macro_keys = ['total_duration', 'typing_rollover_ratio', 'modifier_rollover_ratio']
        for key in macro_keys:
            vals = [float(row[key]) for row in clean_samples]
            mean_profile[key] = np.mean(vals)
            
        # C. Shift Dominance
        shifts = [row['shift_dominance'] for row in clean_samples]
        mean_profile['shift_dominance'] = max(set(shifts), key=shifts.count)

        # ---------------------------------------------------------
        # 3. BANDINGKAN VEKTOR
        # ---------------------------------------------------------
        input_vectors = {}
        scores = {}
        
        for key in vector_keys:
            input_vectors[key] = self._parse_vector(new_features[key])
            
            # Cek panjang input vs profil
            if len(input_vectors[key]) != len(mean_profile[key]):
                print(f"[GAGAL] Panjang {key}: Input={len(input_vectors[key])}, Profil={len(mean_profile[key])}")
                # Jangan langsung return False, beri penalti maksimal saja
                scores[key] = self.OUTLIER_CAP 
            else:
                scores[key] = self.calculate_capped_distance(
                    input_vectors[key], mean_profile[key], key
                )

        # ---------------------------------------------------------
        # 4. HITUNG SKOR AKHIR
        # ---------------------------------------------------------
        # ... (Kode bagian Macro sama seperti sebelumnya) ...
        
        dur_diff = abs(new_features['total_duration'] - mean_profile['total_duration'])
        dur_score = dur_diff / (mean_profile['total_duration'] + 0.001)
        dur_score = min(dur_score, 1.0)
        
        roll_diff = abs(new_features['typing_rollover_ratio'] - mean_profile['typing_rollover_ratio'])
        
        shift_penalty = 0.0
        if new_features['shift_dominance'] != mean_profile['shift_dominance']:
            shift_penalty = 0.20

        # HITUNG WEIGHTED SCORE
        w_vec = (scores['H_vector'] * 1.0 + 
                 scores['DD_vector'] * 1.5 + 
                 scores['UD_vector'] * 1.2 +
                 scores['UU_vector'] * 0.8 + 
                 scores['DU_vector'] * 0.5) / 5.0
                 
        w_macro = (dur_score * 1.0 + roll_diff * 1.5 + shift_penalty) / 2.5
        final_score = (w_vec * 0.7) + (w_macro * 0.3)
        
        # PERBAIKAN 2: Longgarkan Threshold
        # Naikkan dari 0.35 ke 0.45 atau 0.50 agar lebih toleran
        REAL_THRESHOLD = 0.45 
        
        is_verified = final_score < REAL_THRESHOLD
        
        print("-" * 30)
        print(f"SKOR AKHIR       : {final_score:.4f}")
        print(f"STATUS           : {'LOLOS' if is_verified else 'DITOLAK'}")
        print("-" * 30)

        return {
            "result": is_verified,
            "score": round(final_score, 4),
            "threshold": REAL_THRESHOLD,
            "msg": f"Skor: {final_score:.4f}"
        }

# Testing Block
if __name__ == "__main__":
    print("Jalankan lewat app.py untuk hasil real.")