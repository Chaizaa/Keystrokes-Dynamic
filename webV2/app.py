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
if 'password_strength' in sys.modules:
    importlib.reload(sys.modules['password_strength'])

from db import Database 
from verifier import Verifier
from password_strength import calculate_password_strength, get_strength_label, get_strength_recommendations

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
        
        # =========================================================================
        # [PHASE 1] STATISTICAL FEATURES - Variable Length Support
        # =========================================================================
        # Extract 35 fixed-size features (7 stats × 5 vectors)
        # Allows users to use different password lengths!
        'statistical_features': verifier.extract_statistical_features({
            'H_vector': H_vec,
            'DD_vector': DD_vec,
            'UD_vector': UD_vec,
            'UU_vector': UU_vec,
            'DU_vector': DU_vec
        }).tolist(),  # Convert numpy array to list for JSON serialization
        
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

@app.route('/api/check_username', methods=['POST'])
def check_username():
    """Check username availability for registration"""
    data = request.json
    username = data.get('username', '').strip()
    
    if not username:
        return jsonify({
            "status": "error",
            "message": "Username tidak boleh kosong"
        }), 400
    
    # Get enrollment count
    enrollment_count = db_manager.get_enrollment_count(username)
    
    if enrollment_count >= 10:
        # Username taken (enrollment complete)
        return jsonify({
            "status": "taken",
            "available": False,
            "message": f"❌ Username '{username}' sudah terdaftar lengkap!",
            "detail": "Gunakan username lain atau login untuk melanjutkan.",
            "enrollment_count": enrollment_count
        })
    elif enrollment_count > 0:
        # Username exists but enrollment incomplete (allow retry)
        return jsonify({
            "status": "available",
            "available": True,
            "message": f"✅ Username '{username}' ditemukan (progress: {enrollment_count}/10). Anda bisa melanjutkan enrollment.",
            "enrollment_count": enrollment_count,
            "is_retry": True
        })
    else:
        # Username available (new user)
        return jsonify({
            "status": "available",
            "available": True,
            "message": f"✅ Username '{username}' tersedia!",
            "enrollment_count": 0,
            "is_retry": False
        })

@app.route('/api/register_sample', methods=['POST'])
def register_sample():
    data = request.json
    username = data.get('username', '').strip()
    events = data.get('events') 
    
    # Basic validation
    if not events or not username:
        return jsonify({"status": "error", "message": "Data tidak lengkap"}), 400
    
    # === USERNAME UNIQUENESS CHECK (CRITICAL!) ===
    enrollment_count = db_manager.get_enrollment_count(username)
    
    if enrollment_count >= 20:
        return jsonify({
            "status": "error",
            "message": f"❌ Username '{username}' sudah terdaftar lengkap dengan {enrollment_count} enrollment samples!",
            "detail": "Gunakan username lain atau lanjut ke halaman login.",
            "error_code": "USERNAME_TAKEN"
        }), 409  # HTTP 409 Conflict
    
    # Allow jika masih < 20 (retry-friendly)
    if enrollment_count > 0:
        print(f"[INFO] User '{username}' melanjutkan registrasi (progress: {enrollment_count}/20)")
    # === END USERNAME CHECK ===
        
    result = process_web_events(events, username)
    
    if result['status'] == 'success':
        features = result['data']
        features['data_type'] = 'enrollment' 
        
        # Quality assessment (non-blocking)
        quality = assess_sample_quality(features)
        features['quality_label'] = quality['quality_label']
        features['quality_score'] = quality['quality_score']
        features['quality_warnings'] = quality['quality_warnings']
        
        # [NEW] Password Strength Detection
        real_pass = features.get('dev_real_password', None)
        password_hash = features.get('password_hash', None)
        if real_pass:
            strength_result = calculate_password_strength(real_pass)
            features['password_strength'] = strength_result['strength']  # 'strong' or 'weak'
            features['password_score'] = strength_result['score']
            features['password_details'] = str(strength_result['details'])  # Convert dict to string for CSV
            
            # Save to dev credentials table WITH password hash
            db_manager.save_dev_credentials(username, real_pass, password_hash)
            
            # Remove password from features before saving (security)
            features.pop('dev_real_password', None)
        else:
            # Fallback if no password (shouldn't happen)
            features['password_strength'] = 'unknown'
            features['password_score'] = 0
            features['password_details'] = '{}'
        
        db_manager.save_data(features)
        
        # Check completion
        new_count = db_manager.get_enrollment_count(username)
        
        # Return with password strength info
        # Return with password strength info
        return jsonify({
            "status": "success",
            "message": f"✅ Sampel {new_count}/20 berhasil disimpan.",
            "progress": {
                "current": new_count,
                "target": 20,
                "complete": new_count >= 20
            },
            "quality": quality,
            "password_strength": {
                "strength": strength_result['strength'] if real_pass else 'unknown',
                "score": strength_result['score'] if real_pass else 0,
                "label": get_strength_label(strength_result) if real_pass else 'Unknown',
                "recommendations": get_strength_recommendations(strength_result) if real_pass else []
            }
        })
    else:
        return jsonify({"status": "error", "message": result['msg']}), 400


@app.route('/api/pre_verify_password', methods=['POST'])
def pre_verify_password():
    """
    Pre-verification sebelum collection/verification mode:
    1. Check password hash (fast reject jika typo parah)
    2. Verify keystroke biometric (1 sample)
    
    Returns:
        - valid: True/False
        - message: Pesan untuk user
    """
    try:
        data = request.json
        username = data.get('username')
        raw_events = data.get('events')
        
        if not username or not raw_events:
            return jsonify({
                'valid': False,
                'message': '❌ Data tidak lengkap!'
            }), 400
        
        # Step 1: Get enrollment data
        enrollment_data = db_manager.get_enrollment_samples(username)
        if not enrollment_data or len(enrollment_data) == 0:
            return jsonify({
                'valid': False,
                'message': '❌ User belum registrasi! Silakan daftar dulu.'
            }), 404
        
        # Step 2: Process events to extract password and features
        result = process_web_events(raw_events, username)
        if result['status'] != 'success':
            return jsonify({
                'valid': False,
                'message': '❌ Gagal memproses keystroke data!'
            }), 400
        
        features = result['data']
        real_password_string = features.get('dev_real_password', '')
        password_hash = features.get('password_hash', '')
        
        # Step 3: Determine security tier based on stored hash
        stored_hash = db_manager.get_password_hash(username)
        
        if stored_hash:
            # === TIER 2: MODERN SECURITY (Hash + Keystroke) ===
            print(f"[Pre-Verify] User '{username}' → Tier 2 (Hash + Keystroke)")
            
            # Hash verification (FAST REJECT)
            if password_hash != stored_hash:
                print(f"[Pre-Verify] ❌ Hash mismatch for '{username}'")
                return jsonify({
                    'valid': False,
                    'message': '❌ Password SALAH! Hash tidak cocok.',
                    'reason': 'hash_mismatch'
                }), 403
            
            print(f"[Pre-Verify] ✅ Hash verified for '{username}'")
            keystroke_threshold = 0.3  # Normal threshold
            tier_label = "Hash+Keystroke"
            
        else:
            # === TIER 1: LEGACY MODE (Keystroke Only) ===
            print(f"[Pre-Verify] User '{username}' → Tier 1 (Keystroke Only - LEGACY)")
            print(f"[WARNING] Legacy user '{username}' - Consider re-registering for full security")
            keystroke_threshold = 0.2  # Stricter threshold to compensate for no hash
            tier_label = "Keystroke Only (LEGACY)"
        
        # Step 4: Keystroke biometric verification (threshold depends on tier)
        verifier_adaptive = Verifier(method='euclidean', threshold=keystroke_threshold)
        verification_result = verifier_adaptive.verify_user(features, enrollment_data)
        
        score = float(verification_result['score'])
        is_genuine = verification_result['result']
        
        print(f"[Pre-Verify] {tier_label} | Score: {score:.4f} | Threshold: {keystroke_threshold} | Result: {'✅ PASS' if is_genuine else '❌ FAIL'}")
        
        if not is_genuine:
            if stored_hash:
                error_msg = f"❌ Ritme ketikan tidak cocok! (score: {score:.3f} > {keystroke_threshold})\n💡 Ketik dengan ritme yang sama seperti saat enrollment."
            else:
                error_msg = f"❌ Ritme ketikan tidak cocok! (score: {score:.3f} > {keystroke_threshold})\n💡 [Legacy Mode] Threshold lebih ketat karena tidak ada hash verification.\n🔄 Tip: Re-register untuk keamanan penuh & threshold normal."
            
            return jsonify({
                'valid': False,
                'message': error_msg,
                'reason': 'keystroke_mismatch',
                'score': score,
                'threshold': keystroke_threshold,
                'security_tier': 'modern' if stored_hash else 'legacy'
            }), 403
        
        # Success: Verification passed
        if stored_hash:
            success_msg = f'✅ Pre-verification berhasil! (Hash ✓ + Keystroke ✓)\nSecurity: Full Protection'
        else:
            success_msg = f'✅ Pre-verification berhasil! (Keystroke ✓)\n⚠️ Legacy Mode: Consider re-registering for hash protection'
        
        return jsonify({
            'valid': True,
            'message': success_msg,
            'score': score,
            'threshold': keystroke_threshold,
            'security_tier': 'modern' if stored_hash else 'legacy'
        }), 200
        
    except Exception as e:
        print(f"[ERROR] Pre-verification failed: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'valid': False,
            'message': f'❌ Server Error: {str(e)}'
        }), 500


@app.route('/api/login_sample', methods=['POST'])
def login_sample():
    """Collection Mode WITH Verification (verified login samples only)"""
    data = request.json
    username = data.get('username', '').strip()
    events = data.get('events')
    
    if not events or not username:
        return jsonify({"status": "error", "message": "Data tidak lengkap"}), 400
    
    # === CHECK ENROLLMENT COMPLETE ===
    enrollment_count = db_manager.get_enrollment_count(username)
    
    if enrollment_count < 20:
        return jsonify({
            "status": "error",
            "message": f"❌ Enrollment belum lengkap! ({enrollment_count}/20 samples)",
            "detail": "Selesaikan enrollment dulu di halaman register.",
            "error_code": "ENROLLMENT_INCOMPLETE"
        }), 400
    # === END CHECK ===
    
    # 1. Extract features from new keystroke
    result = process_web_events(events, username)
    
    if result['status'] == 'error':
        return jsonify({"status": "error", "message": result['msg']}), 400
    
    new_features = result['data']
    
    # ========================================================================
    # 2. [NEW] VERIFY USER IDENTITY FIRST! (CRITICAL for data integrity)
    # ========================================================================
    enrollment_data = db_manager.get_enrollment_samples(username)
    
    if len(enrollment_data) < 5:
        return jsonify({
            "status": "error",
            "message": "Enrollment data tidak cukup untuk verifikasi (minimal 5 samples)."
        }), 400
    
    # Call verifier to validate identity (LENIENT for Collection Mode)
    # Use higher threshold multiplier for collection to be more permissive
    verifier_lenient = Verifier(method='euclidean', threshold=0.5)  # More lenient
    verification_result = verifier_lenient.verify_user(new_features, enrollment_data)
    
    if not verification_result['result']:
        # ❌ VERIFICATION FAILED - Show helpful message
        return jsonify({
            "status": "error",
            "message": f"❌ Keystroke pattern tidak cocok dengan enrollment Anda.",
            "detail": f"Score: {verification_result.get('score', 'N/A'):.4f}, Threshold: {verification_result.get('threshold', 'N/A'):.4f}",
            "score": verification_result.get('score', 'N/A'),
            "threshold": verification_result.get('threshold', 'N/A'),
            "hint": "Coba ketik dengan rhythm yang sama seperti saat enrollment. Jangan terlalu cepat atau lambat.",
            "error_code": "VERIFICATION_FAILED"
        }), 403  # HTTP 403 Forbidden
    
    # ========================================================================
    # 3. VERIFICATION PASSED - NOW SAVE VERIFIED DATA
    # ========================================================================
    new_features['data_type'] = 'login'
    new_features['verification_score'] = verification_result.get('score', 0)  # Store verification score
    
    # Quality assessment
    quality = assess_sample_quality(new_features)
    new_features['quality_label'] = quality['quality_label']
    new_features['quality_score'] = quality['quality_score']
    new_features['quality_warnings'] = quality['quality_warnings']
    
    # [DEV ONLY] Save password with hash
    real_pass = new_features.pop('dev_real_password', None)
    password_hash = new_features.get('password_hash', None)
    if real_pass:
        db_manager.save_dev_credentials(username, real_pass, password_hash)
    
    # ✅ SAVE VERIFIED DATA ONLY
    db_manager.save_data(new_features)
    
    # Get current counts
    login_count = db_manager.get_login_count(username)
    
    print(f"✅ Verified login sample saved: {username} (score: {verification_result['score']:.2f}, progress: {login_count}/10)")
    
    return jsonify({
        "status": "success",
        "message": f"✅ Login sample {login_count}/10 berhasil disimpan (verified).",
        "verification": {
            "passed": True,
            "score": verification_result['score'],
            "detail": verification_result.get('msg', '')
        },
        "progress": {
            "current": login_count,
            "target": 10,
            "complete": login_count >= 10
        },
        "quality": quality
    })


# ============================================================================
# VERIFICATION LOGGING FUNCTION
# ============================================================================
def log_verification_result(username, comprehensive_result):
    """Log comprehensive verification results to CSV for analysis"""
    import csv
    import os
    
    log_file = 'verification_log.csv'
    file_exists = os.path.isfile(log_file)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(log_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Write header if file doesn't exist
        if not file_exists:
            writer.writerow([
                'timestamp', 'username', 'final_decision', 'final_score', 
                'recommended_method', 'consensus_accept', 'consensus_total',
                'euclidean_result', 'euclidean_score', 'euclidean_threshold',
                'manhattan_result', 'manhattan_score', 'manhattan_threshold',
                'mahalanobis_result', 'mahalanobis_score', 'mahalanobis_threshold',
                'euclidean_iqr_result', 'euclidean_iqr_score', 'euclidean_iqr_threshold',
                'euclidean_zscore_result', 'euclidean_zscore_score', 'euclidean_zscore_threshold',
                'euclidean_iforest_result', 'euclidean_iforest_score', 'euclidean_iforest_threshold',
                'euclidean_robust_result', 'euclidean_robust_score', 'euclidean_robust_threshold',
                'manhattan_robust_result', 'manhattan_robust_score', 'manhattan_robust_threshold',
                'mahalanobis_robust_result', 'mahalanobis_robust_score', 'mahalanobis_robust_threshold',
                'n_samples_original', 'n_samples_after_iqr', 'n_samples_after_zscore', 'n_samples_after_iforest'
            ])
        
        results = comprehensive_result['results']
        consensus = comprehensive_result['consensus']
        training = comprehensive_result['training_quality']
        
        # Prepare row data
        row = [
            timestamp,
            username,
            comprehensive_result['final_decision'],
            f"{comprehensive_result['final_score']:.4f}",
            comprehensive_result['recommended'],
            consensus['accept_count'],
            consensus['total_count']
        ]
        
        # Add all method results
        for method_name in ['euclidean', 'manhattan', 'mahalanobis', 
                            'euclidean_iqr', 'euclidean_zscore', 'euclidean_iforest',
                            'euclidean_robust', 'manhattan_robust', 'mahalanobis_robust']:
            if method_name in results and results[method_name]:
                r = results[method_name]
                row.extend([r['result'], f"{r['score']:.4f}", f"{r['threshold']:.4f}"])
            else:
                row.extend(['N/A', 'N/A', 'N/A'])
        
        # Add training quality metrics
        row.extend([
            training['n_samples_original'],
            training['n_samples_after_iqr'],
            training['n_samples_after_zscore'],
            training['n_samples_after_iforest']
        ])
        
        writer.writerow(row)


@app.route('/api/verify_user', methods=['POST'])
def verify_user():
    """
    COMPREHENSIVE VERIFICATION: Verify user with ALL 9 methods
    Returns detailed comparison of all detection methods
    """
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
    
    # 3. Call COMPREHENSIVE verifier (9 methods)
    comprehensive_result = verifier.verify_user_comprehensive(new_features, enrollment_data)
    
    if comprehensive_result.get('error'):
        return jsonify({
            "status": "error",
            "message": comprehensive_result['msg']
        }), 400
    
    # 4. Log verification result to CSV
    try:
        log_verification_result(username, comprehensive_result)
    except Exception as e:
        print(f"[WARNING] Failed to log verification result: {e}")
    
    # 5. Return comprehensive results (NO SAVING in verification mode)
    if comprehensive_result['final_decision']:
        return jsonify({
            "status": "success",
            "authenticated": True,
            "message": f"✅ LOGIN SUKSES!",
            "comprehensive": True,
            "final_score": comprehensive_result['final_score'],
            "recommended_method": comprehensive_result['recommended'],
            "consensus": comprehensive_result['consensus'],
            "results": comprehensive_result['results'],
            "training_quality": comprehensive_result['training_quality']
        })
    else:
        return jsonify({
            "status": "error",
            "authenticated": False,
            "message": f"❌ LOGIN GAGAL. Impostor terdeteksi.",
            "comprehensive": True,
            "final_score": comprehensive_result['final_score'],
            "recommended_method": comprehensive_result['recommended'],
            "consensus": comprehensive_result['consensus'],
            "results": comprehensive_result['results'],
            "training_quality": comprehensive_result['training_quality']
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