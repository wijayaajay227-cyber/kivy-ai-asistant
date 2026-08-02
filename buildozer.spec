[app]
title = Robot AI Vector
package.name = robot_ai_vector
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,ttf,otf,json
version = 0.1
orientation = portrait
fullscreen = 0
android.permissions = INTERNET, RECORD_AUDIO, ACCESS_NETWORK_STATE, WAKE_LOCK, SYSTEM_ALERT_WINDOW
android.api = 33
android.minapi = 26
android.arch = armeabi-v7a,arm64-v8a
android.log_level = 2
requirements = python3,kivy,requests,pyjnius,certifi,urllib3,charset-normalizer,idna
services = overlay:service.py

# Buildozer builds the Android package natively on Linux/WSL2.
# The app uses Android native APIs for TTS and speech recognition,
# so the build must run through Buildozer/python-for-android.
