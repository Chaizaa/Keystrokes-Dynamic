from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import time
import hashlib
from datetime import datetime
import sys
import importlib

# Force reload modules in debug mode (prevents __pycache__ issues)
if 'db' in sys.modules:
    importlib.reload(sys.modules['db'])
if 'verifier' in sys.modules:
    importlib.reload(sys.modules['verifier'])

from db import Database 
from verifier import Verifier  # <--- (1) KITA IMPORT OTAKNYA DI SINI

app = Flask(__name__, template_folder='templates')
CORS(app) 

# Inisialisasi Database & Verifier
db_manager = Database()
verifier = Verifier()          # <--- (2) INISIALISASI VERIFIER

# ============================================================================
# QUALITY ASSESSMENT FUNCTION
# ============================================================================
def assess_sample_quality(features):
    """Assess sample quality and return warnings (non-blocking)"""
    warnings = []
    score = 100
    
    # Extract vectors for analysis
    H_vec = features.get('H_vector', [])
    DD_vec = features.get('DD_vector', [])
    UD_vec = features.get('UD_vector', [])
    
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
        import statistics
        dd_mean = statistics.mean(DD_vec)
        dd_std = statistics.stdev(DD_vec) if len(DD_vec) > 1 else 0
        if dd_std > dd_mean * 1.5:  # CV > 150%
            warnings.append(f"High timing variance detected (inconsistent rhythm)")
            score -= 10
    
    # Check 5: Too many rollovers (> 80%)
    rollover_ratio = features.get('typing_rollover_ratio', 0)
    if rollover_ratio > 0.8:
        warnings.append(f"Very high rollover rate: {rollover_ratio*100:.0f}%")
        score -= 5
    
    # Determine quality label
    if score >= 80:
        quality_label = 'good'
    elif score >= 60:
        quality_label = 'questionable'
    else:
        quality_label = 'poor'
    
    return {
        'quality_label': quality_label,
        'quality_score': max(0, score),
        'quality_warnings': warnings
    }

# ============================================================================
# LOGIKA PEMROSESAN RAW DATA (Sama seperti sebelumnya)
# ============================================================================
def process_web_events(raw_events_from_js, username):
    raw_events_from_js.sort(key=lambda x: x['t'])
    
    if not raw_events_from_js: 
        return {"status": "error", "msg": "Data kosong"}
        
    # Fitur Global
    start_time = raw_events_from_js[0]['t']
    end_time = raw_events_from_js[-1]['t']
    total_duration_sec = (end_time - start_time) / 1000.0
    
    # --- [MODIFIKASI DI SINI] ---
    
    # 1. Hitung Backspace
    backspace_count = sum(1 for x in raw_events_from_js if x['code'] == 'Backspace' and x['evt'] == 'd')
    
    # 2. Tambahkan Validasi Batas Backspace
    MAX_ALLOWED_BACKSPACE = 3  # Batas maksimal
    
    if backspace_count > MAX_ALLOWED_BACKSPACE:
        return {
            "status": "error", 
            "msg": f"Terlalu banyak hapus ({backspace_count}x). Maksimal {MAX_ALLOWED_BACKSPACE}x. Ulangi ketikan ini."
        }
    
    # ----------------------------
    # [REMOVED] Shift dominance detection - tidak diperlukan lagi
    
    # Data Cleaning & Pairing
    MAX_HOLD_NORMAL = 800    
    MAX_HOLD_MODIFIER = 5000 
    MAX_HOLD_FOR_REPEAT = 800  # [FITUR BARU] Batas hold time sebelum dianggap auto-repeat (0.8 detik)
    
    # [CATATAN] Validasi auto-repeat DIHAPUS dari backend karena frontend (register.html)
    # sudah menangani dengan benar: mencatat waktu repeat tapi batasi karakter di UI.
    # Backend sekarang hanya fokus pada ekstraksi fitur dari data yang diterima.
    
    temp_keystrokes = []
    temp_dict = {}
    
    for x in raw_events_from_js:
        k_id = x['code']
        
        # [FIX - DEFENSIVE] Filter Enter key - tidak relevan untuk biometric analysis
        # Enter hanya trigger submit, hold time & transition ke Enter tidak konsisten
        # Primary filter di frontend, ini sebagai fallback/secondary defense
        if k_id == 'Enter' or x.get('key') == 'Enter':
            continue  # Skip Enter key completely
        
        if x['evt'] == 'd':
            # PERBAIKAN: Simpan Tuple (Waktu, Karakter Asli saat ditekan)
            # Agar '!' tetap '!' meskipun saat dilepas shift sudah mati
            # Jika belum ada (keydown pertama), simpan
            # Jika sudah ada (event repeat), JANGAN overwrite - biarkan waktu pertama tetap
            if k_id not in temp_dict:
                temp_dict[k_id] = (x['t'], x['key']) 
            
        elif x['evt'] == 'u':
            if k_id in temp_dict:
                # Ambil data waktu start & karakter dari event DOWN PERTAMA
                down_time, char_at_down = temp_dict[k_id] 
                
                up_time = x['t']
                hold_time = up_time - down_time  # Ini akan menghitung TOTAL hold time termasuk repeat
                del temp_dict[k_id]

                is_modifier = ('Shift' in k_id or 'Control' in k_id or 'Alt' in k_id or 'Meta' in k_id or 'CapsLock' in k_id)
                limit = MAX_HOLD_MODIFIER if is_modifier else MAX_HOLD_NORMAL
                
                # Validasi hold time maksimal (untuk mencegah tombol macet/error hardware)
                # CATATAN: Batas ini dinaikkan untuk mengakomodasi user yang sengaja menahan tombol lama
                if hold_time > limit and not is_modifier:
                    # JANGAN langsung reject, beri toleransi lebih
                    # Hanya reject jika SANGAT ekstrem (misal > 5 detik)
                    if hold_time > 5000:
                        return {"status": "error", "msg": f"Tombol {char_at_down} ditahan terlalu lama (>{hold_time}ms). Mungkin tombol macet?"}
                
                # [CATATAN] Validasi is_potential_repeat DIHAPUS
                # Frontend sudah menangani repeat dengan mencatat waktu tapi batasi karakter
                # Backend hanya perlu memproses data yang diterima

                temp_keystrokes.append({
                    'key_char': char_at_down,
                    'key_code': x['code'],
                    'down': down_time, 
                    'up': up_time,
                    'is_backspace': (x['code'] == 'Backspace')
                })
    temp_keystrokes.sort(key=lambda x: x['down'])
    if not temp_keystrokes: return {"status": "error", "msg": "Data tidak valid."}

    # Stack Backspace
    final_stack = []
    for item in temp_keystrokes:
        if item['is_backspace']:
            if final_stack: final_stack.pop()
        else:
            # [CATATAN] Validasi is_potential_repeat DIHAPUS
            # Frontend sudah mencegah repeat, backend hanya proses data yang valid
            final_stack.append(item)

    if len(final_stack) < 2: return {"status": "error", "msg": "Password terlalu pendek."}

    # Build Hash & String Password dengan Sekuens Karakter Terpisah
    real_password_string = ""
    char_sequence = []  # [FITUR BARU #1] Sekuens karakter terpisah
    masked_sequence = []
    
    for k in final_stack:
        if len(k['key_char']) == 1:
            real_password_string += k['key_char']
            char_sequence.append(k['key_char'])  # [FITUR BARU #1] Simpan karakter asli
            masked_sequence.append("*")
        else:
            masked_sequence.append(k['key_code']) 
            
    full_hash = hashlib.sha256(real_password_string.encode()).hexdigest()

    # Rollover & Vector Calculation
    typing_overlap_count = 0
    total_typing_trans = 0
    
    # [FITUR BARU #1] VEKTOR TERPISAH: Waktu vs Huruf
    # Vektor waktu saja (seperti sebelumnya)
    H_vec, DD_vec, UD_vec, UU_vec, DU_vec = [], [], [], [], []
    
    # [FITUR BARU #1] Vektor dengan label karakter (seperti keystrokev1)
    H_features = {}   # Format: "H.a_0": 0.123, "H.b_1": 0.234
    DD_features = {}  # Format: "DD.a_0.b_1": 0.145
    UD_features = {}  # Format: "UD.a_0.b_1": 0.089
    UU_features = {}  # Format: "UU.a_0.b_1": 0.234
    DU_features = {}  # Format: "DU.a_0.b_1": 0.345

    for i, k in enumerate(final_stack):
        hold_time_sec = (k['up'] - k['down']) / 1000
        H_vec.append(round(hold_time_sec, 4))
        
        # [FITUR BARU #1] Simpan dengan label karakter
        char = char_sequence[i] if i < len(char_sequence) else 'X'
        H_features[f"H.{char}_{i}"] = round(hold_time_sec, 4)

    for i in range(len(final_stack) - 1):
        k1 = final_stack[i]
        k2 = final_stack[i+1]
        
        dd_val = (k2['down'] - k1['down']) / 1000
        ud_val = (k2['down'] - k1['up']) / 1000
        uu_val = (k2['up'] - k1['up']) / 1000
        du_val = (k2['up'] - k1['down']) / 1000
        
        # Hitung rollover (semua transition, tidak dibedakan modifier/typing)
        total_typing_trans += 1
        if ud_val < 0: typing_overlap_count += 1
            
        DD_vec.append(round(dd_val, 4))
        UD_vec.append(round(ud_val, 4))
        UU_vec.append(round(uu_val, 4))
        DU_vec.append(round(du_val, 4))
        
        # [FITUR BARU #1] Simpan dengan label karakter
        char1 = char_sequence[i] if i < len(char_sequence) else 'X'
        char2 = char_sequence[i+1] if i+1 < len(char_sequence) else 'X'
        DD_features[f"DD.{char1}_{i}.{char2}_{i+1}"] = round(dd_val, 4)
        UD_features[f"UD.{char1}_{i}.{char2}_{i+1}"] = round(ud_val, 4)
        UU_features[f"UU.{char1}_{i}.{char2}_{i+1}"] = round(uu_val, 4)
        DU_features[f"DU.{char1}_{i}.{char2}_{i+1}"] = round(du_val, 4)

    typing_rollover_ratio = round(typing_overlap_count / total_typing_trans, 4) if total_typing_trans > 0 else 0

    # =========================================================================
    # CALCULATE STATISTICAL FEATURES
    # =========================================================================
    import statistics
    
    # Helper function for safe statistics
    def safe_stats(vec):
        if not vec or len(vec) == 0:
            return 0, 0, 0, 0, 0
        mean_val = statistics.mean(vec)
        std_val = statistics.stdev(vec) if len(vec) > 1 else 0
        min_val = min(vec)
        max_val = max(vec)
        cv_val = (std_val / mean_val) if mean_val > 0 else 0
        return mean_val, std_val, min_val, max_val, cv_val
    
    H_mean, H_std, H_min, H_max, H_cv = safe_stats(H_vec)
    DD_mean, DD_std, DD_min, DD_max, DD_cv = safe_stats(DD_vec)
    UD_mean, UD_std, UD_min, UD_max, UD_cv = safe_stats(UD_vec)
    UU_mean, UU_std, UU_min, UU_max, UU_cv = safe_stats(UU_vec)
    DU_mean, DU_std, DU_min, DU_max, DU_cv = safe_stats(DU_vec)
    
    # Calculate advanced features
    rollover_frequency = typing_overlap_count  # Absolute count of rollovers
    error_rate = backspace_count / len(final_stack) if len(final_stack) > 0 else 0
    typing_speed = len(final_stack) / total_duration_sec if total_duration_sec > 0 else 0  # chars per second

    features = {
        'username': username,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'password_hash': full_hash,
        'keys_sequence': masked_sequence,
        'char_sequence': char_sequence,  # [DEBUG] Sekuens karakter untuk debugging
        'dev_real_password': real_password_string, # [DEV ONLY]
        'total_duration': round(total_duration_sec, 4),
        'backspace_count': backspace_count,
        'typing_rollover_ratio': typing_rollover_ratio,
        
        # RAW VECTORS (for ML)
        'H_vector': H_vec, 
        'DD_vector': DD_vec, 
        'UD_vector': UD_vec, 
        'UU_vector': UU_vec, 
        'DU_vector': DU_vec,
        
        # LABELED FEATURES (with character position - for ML with context)
        'H_features': H_features,
        'DD_features': DD_features,
        'UD_features': UD_features,
        'UU_features': UU_features,
        'DU_features': DU_features,
        
        # STATISTICAL FEATURES (20 features)
        'H_mean': round(H_mean, 4),
        'H_std': round(H_std, 4),
        'H_min': round(H_min, 4),
        'H_max': round(H_max, 4),
        'DD_mean': round(DD_mean, 4),
        'DD_std': round(DD_std, 4),
        'DD_min': round(DD_min, 4),
        'DD_max': round(DD_max, 4),
        'UD_mean': round(UD_mean, 4),
        'UD_std': round(UD_std, 4),
        'UD_min': round(UD_min, 4),
        'UD_max': round(UD_max, 4),
        'UU_mean': round(UU_mean, 4),
        'UU_std': round(UU_std, 4),
        'UU_min': round(UU_min, 4),
        'UU_max': round(UU_max, 4),
        'DU_mean': round(DU_mean, 4),
        'DU_std': round(DU_std, 4),
        'DU_min': round(DU_min, 4),
        'DU_max': round(DU_max, 4),
        
        # ADVANCED FEATURES (8 features)
        'rollover_frequency': rollover_frequency,
        'error_rate': round(error_rate, 4),
        'typing_speed': round(typing_speed, 4),
        'H_cv': round(H_cv, 4),
        'DD_cv': round(DD_cv, 4),
        'UD_cv': round(UD_cv, 4),
        'UU_cv': round(UU_cv, 4),
        'DU_cv': round(DU_cv, 4)
    }

    return {"status": "success", "data": features}

# ============================================================================
# ROUTING HALAMAN
# ============================================================================
@app.route('/')
def home():
    return render_template('home.html') 

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/register')
def register_page():
    return render_template('register.html')

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/register_sample', methods=['POST'])
def register_sample():
    data = request.json
    username = data.get('username')
    events = data.get('events') 
    
    if not events or not username: return jsonify({"message": "Data tidak lengkap"}), 400
        
    result = process_web_events(events, username)
    
    if result['status'] == 'success':
        features = result['data']
        features['data_type'] = 'enrollment' 
        
        # Quality assessment (non-blocking)
        quality = assess_sample_quality(features)
        features['quality_label'] = quality['quality_label']
        features['quality_score'] = quality['quality_score']
        features['quality_warnings'] = quality['quality_warnings']
        
        # [DEV ONLY] Simpan password asli
        real_pass = features.pop('dev_real_password', None)
        if real_pass: db_manager.save_dev_credentials(username, real_pass)
        
        db_manager.save_data(features)
        return jsonify({"status": "success", "message": "Sampel berhasil disimpan.", "quality": quality})
    else:
        return jsonify({"status": "error", "message": result['msg']}), 400


@app.route('/api/login_sample', methods=['POST'])
def login_sample():
    """NEW: Pure data collection for login samples (no verification)"""
    data = request.json
    username = data.get('username')
    events = data.get('events')
    
    if not events or not username:
        return jsonify({"status": "error", "message": "Data tidak lengkap"}), 400
    
    # Process events to extract features
    result = process_web_events(events, username)
    
    if result['status'] == 'success':
        features = result['data']
        features['data_type'] = 'login'  # Mark as login sample
        
        # Quality assessment (non-blocking)
        quality = assess_sample_quality(features)
        features['quality_label'] = quality['quality_label']
        features['quality_score'] = quality['quality_score']
        features['quality_warnings'] = quality['quality_warnings']
        
        # [DEV ONLY] Simpan password asli
        real_pass = features.pop('dev_real_password', None)
        if real_pass:
            db_manager.save_dev_credentials(username, real_pass)
        
        db_manager.save_data(features)
        
        # Get current counts for progress tracking
        enrollment_count = db_manager.get_enrollment_count(username)
        
        print(f"✅ Login sample saved: {username} (total enrollment: {enrollment_count})")
        
        return jsonify({
            "status": "success",
            "message": "Login sample berhasil disimpan.",
            "quality": quality
        })
    else:
        return jsonify({"status": "error", "message": result['msg']}), 400


@app.route('/api/verify_user', methods=['POST'])
def verify_user():
    """HYBRID MODE: Verify user with biometric authentication (no data saving)"""
    data = request.json
    username = data.get('username')
    events = data.get('events')
    
    if not events or not username:
        return jsonify({"status": "error", "message": "Data tidak lengkap"}), 400
    
    # 1. Extract features from keystroke events
    process_result = process_web_events(events, username)
    if process_result['status'] == 'error':
        return jsonify({"status": "error", "message": process_result['msg']}), 400
    
    new_features = process_result['data']
    
    # 2. Get enrollment data from database
    enrollment_data = db_manager.get_enrollment_samples(username)
    
    if len(enrollment_data) < 5:
        return jsonify({
            "status": "error",
            "message": f"User belum terdaftar atau data enrollment kurang. Anda punya {len(enrollment_data)} sampel, minimal 5 diperlukan untuk verifikasi."
        }), 404
    
    # 3. Call verifier for authentication
    verification_result = verifier.verify_user(new_features, enrollment_data)
    
    # 4. Return result (NO SAVING in verification mode)
    if verification_result['result']:
        detail_msg = verification_result.get('msg') or verification_result.get('reason', '')
        return jsonify({
            "status": "success",
            "authenticated": True,
            "message": f"✅ LOGIN SUKSES! Skor: {verification_result['score']}",
            "score": verification_result['score'],
            "detail": detail_msg
        })
    else:
        detail_msg = verification_result.get('msg') or verification_result.get('reason', '')
        return jsonify({
            "status": "error",
            "authenticated": False,
            "message": f"❌ LOGIN GAGAL. {detail_msg}",
            "score": verification_result.get('score', 'N/A'),
            "detail": detail_msg
        })


@app.route('/api/login_attempt', methods=['POST'])
def login_attempt():
    """LEGACY: Keep for backward compatibility / testing verification"""
    data = request.json
    username = data.get('username')
    events = data.get('events') 
    
    if not events or not username: return jsonify({"message": "Data tidak lengkap"}), 400
        
    # 1. Ubah Data Mentah (JS) -> Fitur Vektor (Python)
    process_result = process_web_events(events, username)
    if process_result['status'] == 'error':
        return jsonify({"status": "error", "message": process_result['msg']}), 400
    
    new_features = process_result['data']
    
    # 2. Ambil Data Latihan dari Database (via db.py)
    enrollment_data = db_manager.get_enrollment_samples(username)
    
    if len(enrollment_data) < 5:
        return jsonify({"status": "error", "message": f"User belum terdaftar atau data enrollment kurang. Anda punya {len(enrollment_data)} sampel, minimal 5 diperlukan untuk verifikasi."}), 404

    # 3. PANGGIL VERIFIER UNTUK MENILAI (via verifier.py)
    verification_result = verifier.verify_user(new_features, enrollment_data)
    
    # 4. Simpan Log Hasilnya
    new_features['login_result'] = str(verification_result['result'])
    new_features['login_score'] = verification_result.get('score', 0)
    new_features['data_type'] = 'login_attempt'
    
    # [DEV ONLY] Hapus password asli sebelum simpan log
    new_features.pop('dev_real_password', None)
    
    # PURE COLLECTION MODE: Just save, no adaptive learning
    if verification_result['result']:
        db_manager.save_data(new_features)
        detail_msg = verification_result.get('msg') or verification_result.get('reason', '')
        return jsonify({
            "status": "success",
            "message": f"✅ LOGIN SUKSES! Skor: {verification_result['score']} {detail_msg}"
        })
    else:
        db_manager.save_data(new_features)
        detail_msg = verification_result.get('msg') or verification_result.get('reason', '')
        return jsonify({
            "status": "error",
            "message": f"❌ LOGIN GAGAL. {detail_msg} (Skor: {verification_result.get('score', 'N/A')})"
        })


if __name__ == '__main__':
    app.run(debug=True)