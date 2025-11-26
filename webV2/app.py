from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import time
import hashlib
from datetime import datetime
from db import Database 
from verifier import Verifier  # <--- (1) KITA IMPORT OTAKNYA DI SINI

app = Flask(__name__, template_folder='templates')
CORS(app) 

# Inisialisasi Database & Verifier
db_manager = Database()
verifier = Verifier()          # <--- (2) INISIALISASI VERIFIER

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
    
    shift_l = sum(1 for x in raw_events_from_js if x['code'] == 'ShiftLeft' and x['evt'] == 'd')
    shift_r = sum(1 for x in raw_events_from_js if x['code'] == 'ShiftRight' and x['evt'] == 'd')
    if shift_l > 0 and shift_r == 0: shift_dominance = "Left"
    elif shift_r > 0 and shift_l == 0: shift_dominance = "Right"
    elif shift_l > 0 and shift_r > 0: shift_dominance = "Mixed"
    else: shift_dominance = "None"

    # Data Cleaning & Pairing
    MAX_HOLD_NORMAL = 800    
    MAX_HOLD_MODIFIER = 5000 
    
    active_keys = {}
    for x in raw_events_from_js:
        k_id = x['code']
        is_safe = ('Shift' in k_id or 'Control' in k_id or 'Alt' in k_id or 'Meta' in k_id)
        if x['evt'] == 'd':
            cnt = active_keys.get(k_id, 0)
            if cnt > 0 and not is_safe:
                return {"status": "error", "msg": f"Tombol {x['key']} ditahan (Auto-Repeat)."}
            active_keys[k_id] = cnt + 1
        elif x['evt'] == 'u':
            active_keys[k_id] = 0

    temp_keystrokes = []
    temp_dict = {}
    
    for x in raw_events_from_js:
        k_id = x['code'] 
        if x['evt'] == 'd':
            # PERBAIKAN: Simpan Tuple (Waktu, Karakter Asli saat ditekan)
            # Agar '!' tetap '!' meskipun saat dilepas shift sudah mati
            temp_dict[k_id] = (x['t'], x['key']) 
            
        elif x['evt'] == 'u':
            if k_id in temp_dict:
                # Ambil data waktu start & karakter dari event DOWN
                down_time, char_at_down = temp_dict[k_id] 
                
                up_time = x['t']
                hold_time = up_time - down_time
                del temp_dict[k_id]

                is_modifier = ('Shift' in k_id or 'Control' in k_id or 'Alt' in k_id or 'Meta' in k_id or 'CapsLock' in k_id)
                limit = MAX_HOLD_MODIFIER if is_modifier else MAX_HOLD_NORMAL
                
                if hold_time > limit:
                    return {"status": "error", "msg": f"Tombol {char_at_down} ditahan terlalu lama."}

                temp_keystrokes.append({
                    'key_char': char_at_down, # <--- GUNAKAN KARAKTER DARI DOWN EVENT
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
            final_stack.append(item)

    if len(final_stack) < 2: return {"status": "error", "msg": "Password terlalu pendek."}

    # Build Hash & Vektor
    real_password_string = ""
    masked_sequence = []
    for k in final_stack:
        if len(k['key_char']) == 1:
            real_password_string += k['key_char']
            masked_sequence.append("*")
        else:
            masked_sequence.append(k['key_code']) 
            
    full_hash = hashlib.sha256(real_password_string.encode()).hexdigest()

    # Rollover & Vector Calculation
    typing_overlap_count = 0
    total_typing_trans = 0
    modifier_overlap_count = 0
    total_modifier_trans = 0
    
    H_vec, DD_vec, UD_vec, UU_vec, DU_vec = [], [], [], [], []

    for k in final_stack:
        H_vec.append(round((k['up'] - k['down']) / 1000, 4))

    for i in range(len(final_stack) - 1):
        k1 = final_stack[i]
        k2 = final_stack[i+1]
        
        dd_val = (k2['down'] - k1['down']) / 1000
        ud_val = (k2['down'] - k1['up']) / 1000
        uu_val = (k2['up'] - k1['up']) / 1000
        du_val = (k2['up'] - k1['down']) / 1000
        
        k1_code = k1['key_code']
        is_k1_modifier = ('Shift' in k1_code or 'Control' in k1_code or 'Alt' in k1_code)
        
        if is_k1_modifier:
            total_modifier_trans += 1
            if ud_val < 0: modifier_overlap_count += 1
        else:
            total_typing_trans += 1
            if ud_val < 0: typing_overlap_count += 1
            
        DD_vec.append(round(dd_val, 4))
        UD_vec.append(round(ud_val, 4))
        UU_vec.append(round(uu_val, 4))
        DU_vec.append(round(du_val, 4))

    typing_rollover_ratio = round(typing_overlap_count / total_typing_trans, 4) if total_typing_trans > 0 else 0
    modifier_rollover_ratio = round(modifier_overlap_count / total_modifier_trans, 4) if total_modifier_trans > 0 else 0

    features = {
        'username': username,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'password_hash': full_hash,
        'keys_sequence': masked_sequence, 
        'dev_real_password': real_password_string, # [DEV ONLY]
        'total_duration': round(total_duration_sec, 4),
        'backspace_count': backspace_count,
        'shift_dominance': shift_dominance,
        'typing_rollover_ratio': typing_rollover_ratio,
        'modifier_rollover_ratio': modifier_rollover_ratio,
        'H_vector': H_vec, 'DD_vector': DD_vec, 'UD_vector': UD_vec, 
        'UU_vector': UU_vec, 'DU_vector': DU_vec
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
        
        # [DEV ONLY] Simpan password asli
        real_pass = features.pop('dev_real_password', None)
        if real_pass: db_manager.save_dev_credentials(username, real_pass)
        
        db_manager.save_data(features)
        return jsonify({"status": "success", "message": "Sampel berhasil disimpan."})
    else:
        return jsonify({"status": "error", "message": result['msg']}), 400


@app.route('/api/login_attempt', methods=['POST'])
def login_attempt():
    """Endpoint Login yang SUDAH TERHUBUNG dengan Verifier"""
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
    
    if len(enrollment_data) < 2:
        return jsonify({"status": "error", "message": "User belum terdaftar atau data latihan kurang (Min 2)."}), 404

    # 3. PANGGIL VERIFIER UNTUK MENILAI (via verifier.py)
    #    Ini adalah langkah "KONEKSI" yang Anda tanyakan
    verification_result = verifier.verify_user(new_features, enrollment_data)
    
    # 4. Simpan Log Hasilnya
    new_features['login_result'] = str(verification_result['result'])
    new_features['login_score'] = verification_result.get('score', 0)
    new_features['data_type'] = 'login_attempt'
    
    # [DEV ONLY] Hapus password asli sebelum simpan log
    new_features.pop('dev_real_password', None)
    
    # Jika SUKSES -> Update DB (Adaptive Learning)
    # Jika GAGAL  -> Simpan sebagai log gagal
    if verification_result['result']:
        new_features['data_type'] = 'enrollment' # Jadi data latihan baru
    
    db_manager.save_data(new_features)
    
    # 5. Kirim Balik ke HTML
    # Mengambil pesan detail (msg) atau alasan gagal (reason) dari verifier
    detail_msg = verification_result.get('msg') or verification_result.get('reason', '')
    
    if verification_result['result']:
        return jsonify({
            "status": "success", 
            "message": f"LOGIN SUKSES! Skor: {verification_result['score']} {detail_msg}"
        })
    else:
        return jsonify({
            "status": "error", 
            "message": f"LOGIN GAGAL. {detail_msg} (Skor: {verification_result.get('score', 'N/A')})"
        })

if __name__ == '__main__':
    app.run(debug=True)