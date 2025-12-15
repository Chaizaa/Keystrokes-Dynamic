import numpy as np
import json

class Verifier:
    def __init__(self):
        self.MAX_BACKSPACE = 3
        self.OUTLIER_CAP = 1.0
        self.EXTREME_ANOMALY_THRESHOLD = 0.5  # [BARU] Jika 1 fitur beda > 0.5s = HARD REJECT
        self.THRESHOLD = 0.35 # Dilonggarkan sedikit karena sekarang ada banyak fitur
    
    def _parse_vector(self, vector_data):
        if isinstance(vector_data, str):
            try: return np.array(json.loads(vector_data))
            except: return np.array([])
        return np.array(vector_data)
    
    def _parse_features(self, feature_data):
        """Parse H_features, DD_features, UD_features (dict format)"""
        if isinstance(feature_data, str):
            try: return json.loads(feature_data)
            except: return {}
        return feature_data if isinstance(feature_data, dict) else {}

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

        # A. Profil Vektor (Legacy - untuk backward compatibility)
        for key in vector_keys:
            vecs = []
            for row in clean_samples:
                v = self._parse_vector(row[key])
                vecs.append(v)
            mean_profile[key] = np.mean(vecs, axis=0)

        # A2. [FITUR BARU] Profil Fitur Per-Karakter (H_features, DD_features, UD_features, UU_features, DU_features)
        feature_keys = ['H_features', 'DD_features', 'UD_features', 'UU_features', 'DU_features']
        for fkey in feature_keys:
            # Kumpulkan semua key yang muncul di sampel
            all_feature_keys = set()
            for row in clean_samples:
                feat_dict = self._parse_features(row.get(fkey, {}))
                all_feature_keys.update(feat_dict.keys())
            
            # Hitung rata-rata per key
            mean_profile[fkey] = {}
            for k in all_feature_keys:
                values = []
                for row in clean_samples:
                    feat_dict = self._parse_features(row.get(fkey, {}))
                    if k in feat_dict:
                        values.append(float(feat_dict[k]))
                if values:
                    mean_profile[fkey][k] = np.mean(values)
            
            print(f"[INFO] Profil {fkey}: {len(mean_profile[fkey])} fitur")


        # B. Profil Macro
        macro_keys = ['total_duration', 'typing_rollover_ratio']
        for key in macro_keys:
            vals = [float(row[key]) for row in clean_samples]
            mean_profile[key] = np.mean(vals)

        # ---------------------------------------------------------
        # 3. BANDINGKAN VEKTOR & FITUR BARU
        # ---------------------------------------------------------
        input_vectors = {}
        scores = {}
        
        # A. Bandingkan Vektor Legacy
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
        
        # B. [FITUR BARU] Bandingkan Fitur Per-Karakter
        feature_scores = {}
        has_extreme_anomaly = False  # Flag untuk deteksi anomaly ekstrem
        
        for fkey in ['H_features', 'DD_features', 'UD_features', 'UU_features', 'DU_features']:
            input_feat = self._parse_features(new_features.get(fkey, {}))
            profile_feat = mean_profile.get(fkey, {})
            
            if not profile_feat:
                feature_scores[fkey] = 0.0  # Tidak ada data profil, skip
                continue
            
            # Hitung rata-rata selisih untuk fitur yang cocok
            diffs = []
            for k in profile_feat.keys():
                if k in input_feat:
                    diff = abs(float(input_feat[k]) - float(profile_feat[k]))
                    
                    # [CRITICAL] Deteksi anomaly ekstrem (misal hold 2s vs 0.2s)
                    if diff > self.EXTREME_ANOMALY_THRESHOLD:
                        print(f"[ALERT] ANOMALY EKSTREM di {k}: Input={input_feat[k]:.4f}, Profil={profile_feat[k]:.4f}, Diff={diff:.4f}")
                        has_extreme_anomaly = True
                    
                    capped_diff = min(diff, self.OUTLIER_CAP)
                    diffs.append(capped_diff)
            
            if diffs:
                feature_scores[fkey] = np.mean(diffs)
                print(f"[DEBUG] {fkey} Distance: {feature_scores[fkey]:.4f}")
            else:
                feature_scores[fkey] = self.OUTLIER_CAP  # Tidak ada fitur cocok
                print(f"[WARNING] {fkey}: Tidak ada fitur yang cocok!")
        
        # [CRITICAL] HARD REJECTION jika ada anomaly ekstrem
        if has_extreme_anomaly:
            print("\n" + "="*50)
            print("⚠️  DETEKSI ANOMALY EKSTREM - LOGIN DITOLAK")
            print("="*50)
            return {
                "result": False,
                "score": 1.0,
                "threshold": 0.45,
                "reason": "Pola waktu tidak cocok! Ada perbedaan ekstrem (>0.5s) pada fitur biometrik."
            }


        # ---------------------------------------------------------
        # 4. HITUNG SKOR AKHIR (Gabungkan Legacy + Fitur Baru)
        # ---------------------------------------------------------
        # ... (Kode bagian Macro sama seperti sebelumnya) ...
        
        dur_diff = abs(new_features['total_duration'] - mean_profile['total_duration'])
        dur_score = dur_diff / (mean_profile['total_duration'] + 0.001)
        dur_score = min(dur_score, 1.0)
        
        roll_diff = abs(new_features['typing_rollover_ratio'] - mean_profile['typing_rollover_ratio'])

        # HITUNG WEIGHTED SCORE (Legacy Vectors)
        w_vec = (scores['H_vector'] * 1.0 + 
                 scores['DD_vector'] * 1.5 + 
                 scores['UD_vector'] * 1.2 +
                 scores['UU_vector'] * 0.8 + 
                 scores['DU_vector'] * 0.5) / 5.0
        
        # [FITUR BARU] Score dari fitur per-karakter
        w_features = (feature_scores.get('H_features', 0) * 2.5 +   # [FIX] Hold time SANGAT penting!
                      feature_scores.get('DD_features', 0) * 1.5 +
                      feature_scores.get('UD_features', 0) * 1.0 +
                      feature_scores.get('UU_features', 0) * 0.8 +
                      feature_scores.get('DU_features', 0) * 0.5) / 6.3  # Total weight: 6.3
        
        w_macro = (dur_score * 1.5 + roll_diff * 1.0) / 2.5
        
        # [FIX] Bobot baru: 60% fitur waktu per-karakter + 20% legacy + 20% macro
        final_score = (w_vec * 0.2) + (w_features * 0.6) + (w_macro * 0.2)
        
        # [FIX] Perketat threshold untuk lebih strict
        REAL_THRESHOLD = 0.30  # Turunkan dari 0.45 ke 0.30 
        
        is_verified = final_score < REAL_THRESHOLD
        
        print("-" * 30)
        print(f"SKOR Legacy Vec  : {w_vec:.4f}")
        print(f"SKOR Fitur Baru  : {w_features:.4f}")
        print(f"SKOR Macro       : {w_macro:.4f}")
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