# 📋 CHANGELOG - Penghapusan Shift Dominance & Perbaikan Modifier Keys

## 🎯 Perubahan Utama

### 1. **SHIFT DOMINANCE DIHAPUS SEPENUHNYA**
   - ❌ Tidak ada lagi deteksi Left/Right shift
   - ❌ Tidak ada lagi shift_dominance dalam database
   - ❌ Tidak ada lagi shift_penalty dalam verifikasi
   - ✅ Fokus hanya pada **karakter yang dihasilkan**, bukan cara menghasilkannya

### 2. **MODIFIER KEYS TIDAK DIHITUNG HOLD TIME**
   ```javascript
   // Frontend (register.html & login.html)
   const isModifier = ['Shift', 'Control', 'Alt', 'Meta', 'CapsLock']
   
   // Modifier keys TIDAK direkam ke rawEvents
   if (!isModifier) {
       rawEvents.push({key, code, evt: 'd', t: time})
   }
   ```

### 3. **KARAKTER KHUSUS DENGAN SHIFT DIBATASI SEPERTI HURUF**
   ```
   User Action: Hold Shift+1 selama 3 detik
   
   Frontend UI: !           (HANYA 1 karakter)
   Backend Data: 
   - rawEvents: [
       {key: '!', evt: 'd', t: 1000, isRepeat: false},
       {key: '!', evt: 'd', t: 1016, isRepeat: true},  // Auto-repeat
       {key: '!', evt: 'd', t: 1032, isRepeat: true},
       {key: '!', evt: 'd', t: 1048, isRepeat: true},
       ... (puluhan event repeat)
       {key: '!', evt: 'u', t: 4000}
     ]
   - Hold time: 3.0 detik ✅ (dihitung dari first keydown sampai keyup)
   - char_sequence: ['!']  (hanya 1 karakter)
   ```

---

## 📝 File yang Diubah

### **Frontend (JavaScript)**

#### `register.html`
```diff
// Event Listener keydown
- // Rekam semua event termasuk modifier
+ const isModifier = ['Shift', 'Control', 'Alt', 'Meta', 'CapsLock']...
+ if (!isModifier) {  // HANYA non-modifier yang direkam
+     rawEvents.push({...})
+ }

// Event Listener keyup  
- // Rekam semua keyup
+ if (!isModifier) {  // HANYA non-modifier yang direkam
+     rawEvents.push({...})
+ }
```

#### `login.html`
- Perubahan identik dengan `register.html`

---

### **Backend (Python)**

#### `app.py`
```diff
# Hapus shift_dominance detection
- shift_l = sum(1 for x in events if x['code'] == 'ShiftLeft')
- shift_r = sum(1 for x in events if x['code'] == 'ShiftRight')
- if shift_l > 0 and shift_r == 0: shift_dominance = "Left"
- ...
+ # [REMOVED] Shift dominance detection - tidak diperlukan lagi

# Hapus modifier_rollover_ratio
- modifier_overlap_count = 0
- total_modifier_trans = 0
- if is_k1_modifier:
-     total_modifier_trans += 1
-     if ud_val < 0: modifier_overlap_count += 1
+ # Semua transition dihitung sebagai typing (tidak dibedakan)
+ total_typing_trans += 1
+ if ud_val < 0: typing_overlap_count += 1

# Hapus dari features dict
- 'shift_dominance': shift_dominance,
- 'modifier_rollover_ratio': modifier_rollover_ratio,
+ # Tidak ada lagi shift_dominance & modifier_rollover_ratio
```

#### `verifier.py`
```diff
# Hapus shift_dominance dari profil
- macro_keys = ['total_duration', 'typing_rollover_ratio', 'modifier_rollover_ratio']
+ macro_keys = ['total_duration', 'typing_rollover_ratio']

- # C. Shift Dominance
- shifts = [row['shift_dominance'] for row in clean_samples]
- mean_profile['shift_dominance'] = max(set(shifts), key=shifts.count)
+ # [REMOVED] Shift dominance tidak digunakan lagi

# Hapus shift_penalty
- shift_penalty = 0.0
- if new_features['shift_dominance'] != mean_profile['shift_dominance']:
-     shift_penalty = 0.20
+ # Tidak ada lagi shift_penalty

# Update weighted score
- w_macro = (dur_score * 1.0 + roll_diff * 1.5 + shift_penalty) / 2.5
+ w_macro = (dur_score * 1.5 + roll_diff * 1.0) / 2.5
```

#### `db.py`
- Tidak ada perubahan (sudah otomatis handle kolom baru/hilang)

---

## 🔍 Logika Lengkap: Modifier Keys vs Karakter Khusus

### **Case 1: User ketik huruf 'a' (hold 2 detik)**
```
Browser Events:
1. keydown 'a' → rawEvents.push({key: 'a', evt: 'd', t: 1000})
2. keydown 'a' (repeat) → preventDefault() + rawEvents.push({isRepeat: true})
3. keydown 'a' (repeat) → preventDefault() + rawEvents.push({isRepeat: true})
...
N. keyup 'a' → rawEvents.push({key: 'a', evt: 'u', t: 3000})

UI Display: a
Backend Hold Time: 2.0 detik ✅
```

### **Case 2: User ketik '!' (Shift+1, hold 2 detik)**
```
Browser Events:
1. keydown Shift → TIDAK DIREKAM (isModifier = true)
2. keydown '!' → rawEvents.push({key: '!', evt: 'd', t: 1000})
3. keydown '!' (repeat) → preventDefault() + rawEvents.push({isRepeat: true})
4. keydown '!' (repeat) → preventDefault() + rawEvents.push({isRepeat: true})
...
N. keyup '!' → rawEvents.push({key: '!', evt: 'u', t: 3000})
M. keyup Shift → TIDAK DIREKAM (isModifier = true)

UI Display: !
Backend Hold Time: 2.0 detik ✅
```

### **Case 3: User ketik 'A' (Shift+a, hold 2 detik)**
```
Browser Events:
1. keydown Shift → TIDAK DIREKAM
2. keydown 'A' → rawEvents.push({key: 'A', evt: 'd', t: 1000})
3. keydown 'A' (repeat) → preventDefault() + rawEvents.push({isRepeat: true})
...
N. keyup 'A' → rawEvents.push({key: 'A', evt: 'u', t: 3000})
M. keyup Shift → TIDAK DIREKAM

UI Display: A
Backend Hold Time: 2.0 detik ✅
char_sequence: ['A']  // Capital A dicatat sebagai 1 karakter
```

---

## ✅ Hasil Akhir

### **Database Schema (Kolom yang Dihapus)**
```diff
- shift_dominance TEXT
- modifier_rollover_ratio REAL
```

### **Features Dictionary (Sebelum vs Sesudah)**
```python
# SEBELUM
features = {
    ...
    'shift_dominance': 'Left',           # ❌ DIHAPUS
    'typing_rollover_ratio': 0.12,
    'modifier_rollover_ratio': 0.05,     # ❌ DIHAPUS
    ...
}

# SESUDAH
features = {
    ...
    'typing_rollover_ratio': 0.12,       # ✅ TETAP
    ...
}
```

### **Verifier Score Calculation**
```python
# SEBELUM
w_macro = (dur_score * 1.0 + roll_diff * 1.5 + shift_penalty) / 2.5

# SESUDAH  
w_macro = (dur_score * 1.5 + roll_diff * 1.0) / 2.5
```

---

## 🧪 Testing Checklist

- [x] Modifier keys (Shift, Ctrl, Alt) tidak ada di rawEvents
- [x] Karakter huruf (a-z) hold time dicatat dengan benar
- [x] Karakter khusus (!, @, #, $, %, dll) hold time dicatat dengan benar
- [x] UI hanya tampilkan 1 karakter meskipun ditahan lama
- [x] Backend catat full hold time untuk semua karakter (termasuk khusus)
- [x] Verifier tidak ada lagi error tentang shift_dominance
- [x] Database tidak error saat menyimpan data tanpa shift_dominance

---

## 📌 Catatan Penting

1. **Backward Compatibility**: Database lama yang punya kolom `shift_dominance` tetap bisa dibaca, tapi nilai tersebut diabaikan

2. **Adaptive Learning**: Login sukses tetap menambah data enrollment (tanpa shift_dominance)

3. **Karakter Khusus = Karakter Biasa**: Sistem tidak membedakan 'a' vs '!', keduanya dihitung hold time-nya sama

4. **Shift Hanya Penghubung**: Shift+1='!', Shift+a='A', tapi yang dicatat cuma '!' dan 'A', bukan Shift-nya

---

## 🎯 Keuntungan Perubahan Ini

✅ **Lebih Sederhana**: Tidak ada lagi kompleksitas shift dominance  
✅ **Lebih Fokus**: Hanya fokus pada timing karakter yang sebenarnya diketik  
✅ **Lebih Akurat**: Karakter khusus (!, @, #) juga bisa jadi bagian biometrik  
✅ **Lebih Universal**: User bisa pakai Shift kiri/kanan sesuka hati tanpa penalti  

---

**Update Date**: December 9, 2025  
**Status**: ✅ IMPLEMENTED & TESTED
