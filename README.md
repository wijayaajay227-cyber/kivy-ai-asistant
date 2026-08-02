# kivy
app android
# Robot AI Vector — Panduan Setup di VSCode

## 1. Yang perlu di-install di VSCode

- **Extension "Python"** (Microsoft) — untuk linting, autocomplete, debug.
- **Extension "Pylance"** — type checking, biar cepat nangkep bug seperti `import_classes` yang tadi tidak terdefinisi.
- (Opsional) **Extension "Kivy Language Support"** — syntax highlight kalau nanti nambah file `.kv`.

## 2. Struktur folder project

```
robot_ai/
├── main.py
├── buildozer.spec
├── requirements.txt
├── robot_idle.png       <- contoh asset robot, bisa diganti dengan desain sendiri
└── icon.png             <- opsional, untuk ikon APK
```

> **Catatan:** Aplikasi ini sudah dirancang untuk berjalan di desktop dan Android. Untuk Android, jalankan build lewat Buildozer di Linux atau WSL2.

## 3. Setup environment Python di VSCode

Buka terminal di VSCode (`` Ctrl+` ``), lalu jalankan:

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Pastikan VSCode memakai interpreter dari `venv` ini:
`Ctrl+Shift+P` → **Python: Select Interpreter** → pilih `./venv/bin/python`.

## 4. Testing dulu di PC (sebelum build ke Android)

Kode ini sudah aman dijalankan langsung di PC karena ada pengecekan `platform == 'android'` — bagian TTS dan Intent Android otomatis di-skip. Cukup jalankan:

```bash
python main.py
```

Kamu akan lihat window Kivy, dan bagian TTS akan tercetak di terminal sebagai `[Simulasi Suara PC]: Hay Bos` — tidak akan bersuara beneran karena itu memang khusus Android.

## 5. Build ke APK Android

Buildozer **hanya jalan di Linux** (native atau WSL2 di Windows). Kalau kamu di Windows, pakai WSL2 dulu.

```bash
pip install buildozer cython
sudo apt update && sudo apt install -y git zip unzip openjdk-17-jdk \
    autoconf libtool pkg-config zlib1g-dev libncurses5-dev \
    libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev

buildozer -v android debug
```

APK hasil build akan muncul di folder `bin/`. Buildozer otomatis download Android SDK/NDK di percobaan pertama (bisa makan waktu lama & butuh koneksi stabil).

## 6. Hal-hal lain yang perlu kamu siapkan/putuskan

- **Package target trading app** (`com.binance.dev` di kode) — cek package name asli aplikasi yang mau kamu buka otomatis, biasanya lewat `adb shell pm list packages | grep binance` kalau app-nya sudah terpasang di HP test kamu.
- **API rate limit CoinGecko** — endpoint publik CoinGecko punya limit request per menit; untuk auto-refresh 60 detik seperti sekarang harusnya aman, tapi kalau mau lebih sering perlu API key berbayar.
- **Signing key** untuk rilis ke Play Store (`buildozer android release`) belum disiapkan — itu langkah terpisah pas mau publish beneran, debug build (`android debug`) tidak butuh ini.

## 7. Fitur baru: Voice Command & Overlay Robot

### Voice command ("Buka <nama app>")
- Tekan tombol **"Dengar Perintah"**, ucapkan misalnya *"Buka WhatsApp"*.
- App mencocokkan ucapan dengan daftar aplikasi terinstall (nama app, bukan package name), lalu membukanya via Intent.
- **Perlu request permission `RECORD_AUDIO` saat runtime** — kode saat ini belum handle dialog izin runtime Android 6+. Tambahkan pengecekan `ActivityCompat.checkSelfPermission` sebelum `mulai_dengar_perintah()` dipanggil, kalau belum di-grant, panggil `ActivityCompat.requestPermissions()`. (Saya bisa bantu tambahkan kalau kamu mau langkah berikutnya.)

### Overlay robot kecil (`service.py`)
Ini fitur paling rawan trial-and-error. Langkah setelah build APK:
1. Install APK, buka app minimal sekali (supaya service terdaftar).
2. **Izinkan manual**: Settings HP → Apps → Robot AI Vector → "Tampilkan di atas aplikasi lain" (istilah persis beda-beda tiap merk HP: Xiaomi/Oppo/Vivo sering menyembunyikan opsi ini lebih dalam, kadang perlu diaktifkan juga "Autostart"/"Background activity" biar service tidak dimatikan sistem penghemat baterai mereka).
3. Ikon robot yang muncul masih pakai **icon default app** (`service.getApplicationInfo().icon`) sebagai placeholder — ganti ke gambar robot asli dengan menaruh file di `res/drawable/robot_kecil.png` lalu ubah baris `setImageResource(...)` di `service.py`.
4. Drag ikon untuk pindah posisi, tap singkat untuk balik ke app utama.

**Realistis soal HP pabrikan Cina** (Xiaomi/MIUI, Oppo/ColorOS, Vivo/FuntouchOS): mereka punya battery-optimization agresif yang sering mematikan background service pihak ketiga meski permission sudah diberikan. Kalau overlay robotnya suka hilang sendiri, itu bukan bug di kode — itu battery-management HP tersebut, solusinya user harus whitelist manual di pengaturan baterai HP masing-masing.

## 8. Soal berita trending Instagram/TikTok

Belum saya buatkan karena **tidak ada API resmi gratis** untuk data ini (lihat penjelasan di chat). Kalau kamu tetap mau fitur "apa yang lagi viral", opsi yang legal & stabil:
- **YouTube Data API v3** (gratis, quota harian) → video trending per kategori/negara.
- **Reddit API** (gratis) → post trending dari subreddit tertentu.
- **pytrends** (unofficial wrapper Google Trends, banyak dipakai, cukup stabil) → kata kunci yang lagi naik.

Kasih tahu saya kalau mau saya buatkan salah satu dari ini — bisa jadi bagian berikutnya dari `muat_informasi_hangat()`.

## Ringkasan perubahan dari kode awal

| Masalah | Perbaikan |
|---|---|
| `import_classes(...)` tidak terdefinisi → crash pas TTS init | Diganti pakai `PythonJavaClass` + `java_method`, sesuai cara resmi Pyjnius implement interface Java |
| URL API salah (`coingecko.com`, `yahoo.com` — itu homepage, bukan endpoint) | Diganti ke endpoint API resmi yang mengembalikan JSON |
| `requests.get()` di main thread → UI freeze | Dipindah ke `threading.Thread`, update UI balik lewat `Clock.schedule_once` |
| Data market cuma diambil sekali | Ditambah `Clock.schedule_interval` refresh tiap 60 detik |
| Bahasa TTS di-hardcode `Locale.US` padahal teksnya "Hay Bos" | Diganti coba `Locale('id','ID')` dulu, fallback ke US kalau device tidak support |
| Tidak ada `buildozer.spec` | Dibuatkan lengkap dengan permission `INTERNET` & `QUERY_ALL_PACKAGES` |