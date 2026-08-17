[app]
title = Robot AI Vector
package.name = robot_ai_vector
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,ttf,otf,json,svg,env
version = 0.1
orientation = portrait
fullscreen = 0
android.permissions = INTERNET, RECORD_AUDIO, ACCESS_NETWORK_STATE, WAKE_LOCK, SYSTEM_ALERT_WINDOW
android.api = 33
android.minapi = 26
android.arch = armeabi-v7a,arm64-v8a
android.log_level = 2

# cairosvg SENGAJA TIDAK dimasukkan -- library ini butuh libcairo (C library
# native) yang TIDAK punya "recipe" resmi di python-for-android, jadi build
# akan selalu gagal kalau dipaksa masuk requirements. Untungnya kode di
# main.py sudah punya fallback aman (CAIROSVG_AVAILABLE = False kalau gagal
# import), jadi tanpa ini app tetap jalan normal -- cuma render logo dari
# SVG yang nonaktif (fallback ke avatar canvas biasa).
requirements = python3,kivy,requests,pyjnius,Pillow,certifi,urllib3,charset-normalizer,idna,yt-dlp

# DIHAPUS: baris "services = overlay:service.py" -- kode overlay di main.py
# (fungsi mulai_overlay_service) tidak pakai file service custom, cukup
# pakai org.kivy.android.PythonService bawaan. Baris itu menyuruh Buildozer
# mencari file overlay/service.py yang tidak ada di project, dan akan bikin
# build gagal.

# WAJIB untuk build non-interaktif (GitHub Actions dll) -- tanpa ini,
# proses build macet nunggu konfirmasi "Accept? (y/N)" untuk lisensi
# Android SDK Build-Tools, otomatis ke-skip jadi "No" dan bikin error
# "Aid1 not found" / build-tools folder not found -- persis error kemarin.
android.accept_sdk_license = True

# Buildozer builds the Android package natively on Linux/WSL2.
# The app uses Android native APIs for TTS and speech recognition,
# so the build must run through Buildozer/python-for-android.

[buildozer]
log_level = 2
warn_on_root = 1
