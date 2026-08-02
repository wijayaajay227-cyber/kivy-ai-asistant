# AGENTS.md

## Purpose
This repository is a Kivy-based mobile app project with Android-specific behavior. The app is designed to run on desktop for development and preview, but actual Android packaging requires Buildozer on Linux/WSL2.

## Key files
- `main.py` — main Kivy application. Contains UI widgets, app logic, and Android-only behavior guarded by `platform == 'android'`.
- `service.py` — Android foreground service for overlay chat-head style robot icon. Uses Pyjnius and Android WindowManager APIs.
- `buildozer.spec` — Android packaging configuration, permissions, and app metadata.
- `requirements.txt` — Python runtime dependencies. Note that `pyjnius` is Android-only and the repo currently keeps desktop usage safe by guarding imports.
- `README.md` — setup and build guidance, especially Windows + WSL2 build instructions and missing asset notes.
- `test_groq.py` — standalone diagnostic script for Groq API connectivity, not a Kivy app.

## How to run
- Local development: use a Python virtual environment and run `python main.py`.
- Desktop runtime is supported for development; Android-specific code is skipped unless `platform == 'android'`.
- Android build must be done with Buildozer on Linux or WSL2 from Windows.

## Build and environment notes
- This project expects `kivy==2.3.1` and `requests` for desktop/local runs.
- Buildozer runs only on Linux natively, so use WSL2 on Windows if building APKs.
- The app uses Android permissions for `INTERNET` and `RECORD_AUDIO`; overlay behavior also requires a manual "display over other apps" approval on Android.
- `robot_idle.png` is included as an example asset; update icon or robot images as needed for branding.

## Development conventions for AI agents
- Do not add Android-only imports at top level in `main.py`; keep them inside `if platform == 'android'` blocks.
- Avoid blocking the Kivy main thread with synchronous network requests; use threads and `Clock.schedule_once` for UI updates.
- Preserve existing UI composition patterns: custom `Card`, `RoundedButton`, animated avatar widgets, and chat bubble layout.
- If editing Android overlay behavior in `service.py`, be aware that this is fragile and may fail on some devices due to OS-level battery and overlay restrictions.

## Useful notes for code changes
- `main.py` is the primary source of feature changes and bug fixes.
- `service.py` is only relevant for Android overlay and should not affect desktop app behavior.
- `test_groq.py` is a helper for verifying the Groq API key and network connectivity; it is not part of the main app runtime.
- When updating packaging behavior, verify `buildozer.spec` and `requirements.txt` together.

## Recommended next agent customization
- Add a dedicated skill or prompt for Android build troubleshooting and Kivy asset handling, because this repo mixes desktop preview with mobile packaging and overlay service code.
