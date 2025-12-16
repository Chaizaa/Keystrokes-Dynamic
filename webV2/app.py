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

    features = {
        'username': username,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'password_hash': full_hash,
        'keys_sequence': masked_sequence, 
        'char_sequence': char_sequence,  # [FITUR BARU #1] Sekuens karakter asli
        'dev_real_password': real_password_string, # [DEV ONLY]
        'total_duration': round(total_duration_sec, 4),
        'backspace_count': backspace_count,
        'typing_rollover_ratio': typing_rollover_ratio,
        
        # [VEKTOR LAMA] Waktu saja (backward compatibility)
        'H_vector': H_vec, 
        'DD_vector': DD_vec, 
        'UD_vector': UD_vec, 
        'UU_vector': UU_vec, 
        'DU_vector': DU_vec,
        
        # [FITUR BARU #1] Vektor dengan label karakter (seperti keystrokev1)
        'H_features': H_features,
        'DD_features': DD_features,
        'UD_features': UD_features,
        'UU_features': UU_features,
        'DU_features': DU_features
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
    
    if len(enrollment_data) < 5:
        return jsonify({"status": "error", "message": f"User belum terdaftar atau data enrollment kurang. Anda punya {len(enrollment_data)} sampel, minimal 5 diperlukan untuk verifikasi."}), 404

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