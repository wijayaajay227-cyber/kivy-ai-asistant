# ==============================================================================
# test_groq.py -- Script diagnostik berdiri sendiri (TANPA Kivy)
# Tujuan: memastikan API Key Groq kamu berfungsi sebelum dipakai di aplikasi.
# Cara pakai: python test_groq.py
# ==============================================================================

import sys

GROQ_API_KEY = "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"  # ganti dengan key dari console.groq.com/keys

print("=" * 60)
print("DIAGNOSTIK KONEKSI GROQ API")
print("=" * 60)

# --- 1. Cek library 'requests' ---
try:
    import requests
    print(f"[OK] Library 'requests' terpasang -> versi {requests.__version__}")
except ImportError:
    print("[GAGAL] Library 'requests' TIDAK terpasang.")
    print("        Jalankan: pip install requests")
    sys.exit(1)

# --- 2. Cek format key ---
api_key = GROQ_API_KEY.strip()
if not api_key or "MASUKKAN" in api_key.upper():
    print("[GAGAL] GROQ_API_KEY belum diisi.")
    print("        1. Buka https://console.groq.com/keys")
    print("        2. Login pakai akun Google (gratis)")
    print("        3. Klik 'Create API Key', copy key-nya")
    print("        4. Tempel di variabel GROQ_API_KEY pada file ini")
    sys.exit(1)
if not api_key.startswith("gsk_"):
    print("[PERINGATAN] Key tidak diawali 'gsk_' -- pastikan kamu copy dengan benar.")

# --- 3. Cek koneksi internet dasar ---
try:
    r = requests.get("https://www.google.com", timeout=8)
    print(f"[OK] Bisa akses internet -> status {r.status_code}")
except Exception as e:
    print(f"[GAGAL] Tidak bisa akses internet sama sekali: {e}")
    sys.exit(1)

# --- 4. Tes request chat completion sesungguhnya ---
print("-" * 60)
print("Mengirim pertanyaan tes ke Groq...")

url = "https://api.groq.com/openai/v1/chat/completions"
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}",
}
body = {
    "model": "openai/gpt-oss-120b",
    "messages": [
        {"role": "user", "content": "Siapa presiden Indonesia saat ini? Jawab singkat."}
    ],
    "max_tokens": 200,
}

try:
    res = requests.post(url, json=body, headers=headers, timeout=25)
    print(f"HTTP Status Code : {res.status_code}")
    print("Isi respons mentah:")
    print(res.text[:2000])
    if res.status_code == 200:
        data = res.json()
        jawaban = data["choices"][0]["message"]["content"]
        print("-" * 60)
        print("JAWABAN AI:")
        print(jawaban)
except Exception as e:
    print(f"[GAGAL] Request ke Groq error: {e}")