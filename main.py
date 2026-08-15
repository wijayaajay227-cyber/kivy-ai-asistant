import ast
import json
import operator
import os
import threading
import time
import webbrowser
import xml.etree.ElementTree as ET
import base64
from typing import Any, Callable, Dict, List, Optional, cast

import requests
from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.effects.dampedscroll import DampedScrollEffect
from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import AsyncImage, Image
from kivy.loader import Loader

# Kivy secara default cuma memuat 2 gambar sekaligus (num_workers=2). Dengan
# banyak thumbnail video & berita dimuat bersamaan, sisanya jadi antre lama
# atau gagal diam-diam. Naikkan kapasitasnya di sini.
try:
    Loader.num_workers = 8
except Exception:
    pass
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import platform
from io import BytesIO
from kivy.core.image import Image as CoreImage
from PIL import Image as PILImage, ImageDraw, ImageFont

try:
    import cairosvg
    CAIROSVG_AVAILABLE = True
except Exception:
    CAIROSVG_AVAILABLE = False

VideoPlayer: Any = None
try:
    from kivy.uix.videoplayer import VideoPlayer as _VideoPlayer
    VideoPlayer = _VideoPlayer
except Exception:
    try:
        from kivy.uix.video import Video as _VideoPlayer
        VideoPlayer = _VideoPlayer
    except Exception:
        class _FallbackVideoPlayer(Widget):
            def __init__(self, **kwargs: Any) -> None:
                super().__init__(**kwargs)
                self.add_widget(Label(text='Video tidak tersedia', halign='center', valign='middle'))

        VideoPlayer = _FallbackVideoPlayer

if platform == 'win':
    from kivy.core.text import LabelBase
    _font_emoji = "C:\\Windows\\Fonts\\seguiemj.ttf"
    if os.path.exists(_font_emoji):
        LabelBase.register(name="Roboto", fn_regular=_font_emoji)

AI_NAME = "KIVY"
MEMORY_FILE = "memory.json"


def _muat_secrets_lokal(nama_file: str = "secrets.env") -> None:
    """Baca file secrets.env sederhana (format KEY=VALUE per baris) dan
    masukkan isinya ke os.environ, TANPA menimpa env var yang sudah ada
    (misal yang di-inject GitHub Actions lewat secrets).

    File ini sengaja TIDAK pakai nama '.env' (dotfile) karena Buildozer
    mendeteksi file untuk dibundel berdasarkan ekstensi, dan dotfile murni
    seperti '.env' tidak punya ekstensi yang bisa dikenali -- jadi dipakai
    nama 'secrets.env' (ekstensi 'env') supaya konsisten di semua tempat.

    Tidak butuh library tambahan (python-dotenv dll), cukup Python bawaan.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), nama_file)
    if not os.path.exists(path):
        return
    try:
        with open(path, 'r', encoding='utf-8') as f:
            for baris in f:
                baris = baris.strip()
                if not baris or baris.startswith('#') or '=' not in baris:
                    continue
                key, _, value = baris.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ.setdefault(key, value)
    except Exception as e:
        print(f"Gagal memuat {nama_file}: {e}")


_muat_secrets_lokal()

# API key TIDAK ditulis langsung di kode -- diambil dari environment variable.
# Cara mengisinya:
#   1) PC/testing lokal  -> copy 'secrets.env.example' jadi 'secrets.env',
#      isi key aslinya di situ (file ini otomatis di-gitignore, aman).
#   2) Build via GitHub Actions -> isi lewat Settings > Secrets and variables
#      > Actions, workflow yang sudah disiapkan otomatis inject ke sini.
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# ------------------------------------------------------------------------
# PALET WARNA MODERN (Indigo / Violet Neon Dark Theme)
# ------------------------------------------------------------------------
WARNA_BG = (0.045, 0.055, 0.09, 1)
WARNA_CARD_HEADER = (0.11, 0.10, 0.22, 1)
WARNA_CARD_PASAR = (0.08, 0.14, 0.26, 0.75)
WARNA_CARD_VIDEO = (0.17, 0.09, 0.26, 1)
WARNA_CARD_BERITA = (0.06, 0.17, 0.30, 1)
WARNA_THUMB_VIDEO_BG = (0.55, 0.80, 1.0, 0.22)  # biru muda transparan (placeholder saat loading)
WARNA_CARD_CHAT = (0.08, 0.09, 0.17, 1)
WARNA_BUBBLE_USER = (0.36, 0.32, 0.94, 1)
WARNA_BUBBLE_KIVY = (0.15, 0.16, 0.27, 1)
WARNA_TOMBOL_MIC = (0.918, 0.263, 0.208, 1)     # Google Red #EA4335
WARNA_TOMBOL_TRADING = (0.204, 0.659, 0.325, 1)  # Google Green #34A853
WARNA_TOMBOL_KIRIM = (0.259, 0.522, 0.957, 1)    # Google Blue #4285F4
WARNA_TOOL_CHIP = (0.16, 0.17, 0.28, 1)
WARNA_AKSEN = (0.55, 0.45, 1.0, 1)
WARNA_SHADOW = (0, 0, 0, 0.35)

# ------------------------------------------------------------------------
# PALET GOOGLE MATERIAL (dipakai untuk aksen tombol & badge, ala produk Google)
# ------------------------------------------------------------------------
GOOGLE_BLUE = (0.259, 0.522, 0.957, 1)    # #4285F4
GOOGLE_RED = (0.918, 0.263, 0.208, 1)     # #EA4335
GOOGLE_YELLOW = (0.984, 0.737, 0.020, 1)  # #FBBC05
GOOGLE_GREEN = (0.204, 0.659, 0.325, 1)   # #34A853

activity: Any = None
if platform == 'android':
    from jnius import autoclass, PythonJavaClass, java_method  # type: ignore

    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    activity = PythonActivity.mActivity
    Locale = autoclass('java.util.Locale')
    TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
    Intent = autoclass('android.content.Intent')
    Uri = autoclass('android.net.Uri')
    SpeechRecognizer = autoclass('android.speech.SpeechRecognizer')
    RecognizerIntent = autoclass('android.speech.RecognizerIntent')
    PackageManager = autoclass('android.content.pm.PackageManager')
    Manifest = autoclass('android.Manifest')
    Settings = autoclass('android.provider.Settings')

    class TTSListener(PythonJavaClass):
        __javainterfaces__ = ['android/speech/tts/TextToSpeech$OnInitListener']
        __javacontext__ = 'app'

        def __init__(self, callback: Callable[[int], None]) -> None:
            super().__init__()
            self.callback = callback

        @java_method('(I)V')
        def onInit(self, status: int) -> None:
            self.callback(status)

    class RecognitionListenerImpl(PythonJavaClass):
        __javainterfaces__ = ['android/speech/RecognitionListener']
        __javacontext__ = 'app'

        def __init__(self, on_result: Callable[[str], None], on_error: Callable[[str], None]) -> None:
            super().__init__()
            self.on_result = on_result
            self.on_error = on_error

        @java_method('(Landroid/os/Bundle;)V')
        def onResults(self, bundle: Any) -> None:
            try:
                matches = bundle.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)
                if matches and matches.size() > 0:
                    self.on_result(matches.get(0))
            except Exception as e:
                self.on_error(str(e))

        @java_method('(I)V')
        def onError(self, error_code: int) -> None:
            self.on_error(f"Kode error suara: {error_code}")

        @java_method('(Landroid/os/Bundle;)V')
        def onReadyForSpeech(self, params: Any) -> None: pass
        @java_method('()V')
        def onBeginningOfSpeech(self) -> None: pass
        @java_method('(F)V')
        def onRmsChanged(self, rmsdB: float) -> None: pass
        @java_method('([B)V')
        def onBufferReceived(self, buffer: Any) -> None: pass
        @java_method('()V')
        def onEndOfSpeech(self) -> None: pass
        @java_method('(Landroid/os/Bundle;)V')
        def onPartialResults(self, partialResults: Any) -> None: pass
        @java_method('(ILandroid/os/Bundle;)V')
        def onEvent(self, eventType: int, params: Any) -> None: pass

    class OnClickListenerImpl(PythonJavaClass):
        __javainterfaces__ = ['android/view/View$OnClickListener']
        __javacontext__ = 'app'

        def __init__(self, callback: Callable[[Any], None]) -> None:
            super().__init__()
            self.callback = callback

        @java_method('(Landroid/view/View;)V')
        def onClick(self, view: Any) -> None:
            self.callback(view)


class MemoryStore:
    def __init__(self, path: str = MEMORY_FILE) -> None:
        self.path = path
        self.data: Dict[str, List[Any]] = self._load()
        self.data.setdefault("events", [])
        self.data.setdefault("pengingat", [])
        self.data.setdefault("catatan", [])

    def _load(self) -> Dict[str, List[Any]]:
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {"events": [], "pengingat": [], "catatan": []}
        return {"events": [], "pengingat": [], "catatan": []}

    def catat(self, jenis: str, isi: str) -> None:
        self.data["events"].append({
            "waktu": time.strftime("%Y-%m-%d %H:%M:%S"),
            "jenis": jenis,
            "isi": isi
        })
        self.data["events"] = self.data["events"][-500:]
        self._simpan()

    def tambah_pengingat(self, teks: str) -> None:
        self.data["pengingat"].append({"waktu": time.strftime("%Y-%m-%d %H:%M"), "teks": teks})
        self._simpan()

    def daftar_pengingat(self) -> List[Dict[str, str]]:
        return self.data.get("pengingat", [])

    def hapus_semua_pengingat(self) -> None:
        self.data["pengingat"] = []
        self._simpan()

    def tambah_catatan(self, teks: str) -> None:
        self.data["catatan"].append({"waktu": time.strftime("%Y-%m-%d %H:%M"), "teks": teks})
        self._simpan()

    def daftar_catatan(self) -> List[Dict[str, str]]:
        return self.data.get("catatan", [])

    def _simpan(self) -> None:
        try:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Gagal simpan memory: {e}")


class Card(BoxLayout):
    """Card dengan efek shadow lembut di belakang untuk kesan modern & elevasi."""
    def __init__(self, bg_color=(0.11, 0.13, 0.19, 1), radius: float = 18,
                 shadow: bool = True, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._radius = radius
        with self.canvas.before:
            if shadow:
                Color(*WARNA_SHADOW)
                self._shadow = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            else:
                self._shadow = None
            Color(*bg_color)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_bg(self, *args: Any) -> None:
        if self._shadow is not None:
            self._shadow.pos = (self.pos[0], self.pos[1] - dp(2))
            self._shadow.size = self.size
        self._bg.pos = self.pos
        self._bg.size = self.size


class CardFloat(FloatLayout):
    def __init__(self, bg_color=(0.11, 0.13, 0.19, 1), radius: float = 16, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*bg_color)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_bg(self, *args: Any) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size


class RoundedButton(Button):
    """Tombol pill modern dengan animasi tekan yang lebih halus.
    Bisa diberi `outline_color` untuk gaya chip bergaris tepi ala Groq Playground.
    """
    def __init__(self, bg_color=(0.20, 0.55, 0.85, 1), radius: float = 18,
                 outline_color: Optional[tuple] = None, outline_width: float = 1.3, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self._base_color = bg_color
        self._radius = radius
        with self.canvas.before:
            Color(*bg_color)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])
            if outline_color is not None:
                Color(*outline_color)
                self._outline = Line(
                    rounded_rectangle=(self.x, self.y, self.width, self.height, radius),
                    width=outline_width
                )
            else:
                self._outline = None
        self.bind(pos=self._update_bg, size=self._update_bg)
        self.bind(on_press=self._animasi_tekan)

    def _update_bg(self, *args: Any) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size
        if self._outline is not None:
            self._outline.rounded_rectangle = (self.x, self.y, self.width, self.height, self._radius)

    def _animasi_tekan(self, *args: Any) -> None:
        Animation.cancel_all(self, 'opacity')
        anim = Animation(opacity=0.65, duration=0.06) + Animation(opacity=1, duration=0.12, t='out_quad')
        anim.start(self)


class AnimatedRobotAvatar(FloatLayout):
    """Avatar robot modern: gradient, antena, mata LED, mulut LED."""
    def __init__(self, bg_color=WARNA_AKSEN, size_dp: float = 64, **kwargs: Any) -> None:
        super().__init__(size_hint=(None, None), size=(dp(size_dp), dp(size_dp)), **kwargs)
        self.size_dp = size_dp
        self.bg_color = bg_color
        self._blink = 0
        self._mouth = 0
        self.bind(pos=self._schedule_redraw, size=self._schedule_redraw)
        Clock.schedule_once(lambda *_: self._redraw(), 0)
        Clock.schedule_interval(self._animate, 0.28)

    def _schedule_redraw(self, *args: Any) -> None:
        Clock.schedule_once(lambda *_: self._redraw(), 0)

    def _redraw(self, *args: Any) -> None:
        if getattr(self, 'canvas', None) is None:
            return
        self.canvas.clear()
        cx, cy = self.center
        s = dp(self.size_dp)
        eye_w = dp(s * 0.22)
        eye_h = dp(s * (0.08 if self._blink % 3 == 0 else 0.18))

        with self.canvas:  # type: ignore
            # background glow circle
            Color(self.bg_color[0]*0.9, self.bg_color[1]*0.9, self.bg_color[2]*0.9, 0.18)
            Ellipse(pos=(self.x - dp(6), self.y - dp(6)), size=(self.width + dp(12), self.height + dp(12)))

            # main rounded body
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(self.size_dp/2)])

            # bezel inner
            Color(0.07, 0.08, 0.14, 1)
            RoundedRectangle(pos=(self.x + dp(4), self.y + dp(4)), size=(self.width - dp(8), self.height - dp(8)), radius=[dp(self.size_dp/2 - 4)])

            # eyes (LED)
            Color(0.96, 0.98, 1, 1)
            Ellipse(pos=(self.x + dp(s*0.18), self.y + dp(s*0.36)), size=(eye_w, eye_h))
            Ellipse(pos=(self.x + dp(s*0.58), self.y + dp(s*0.36)), size=(eye_w, eye_h))

            # eye pupils (glow)
            Color(0.05, 0.14, 0.28, 1)
            Ellipse(pos=(self.x + dp(s*0.23), self.y + dp(s*0.38)), size=(dp(s*0.08), dp(s*0.08)))
            Ellipse(pos=(self.x + dp(s*0.63), self.y + dp(s*0.38)), size=(dp(s*0.08), dp(s*0.08)))

            # mouth LED bar (animated)
            Color(0.92, 0.30, 0.46, 1)
            if self._mouth % 2 == 0:
                Line(points=[self.x + dp(s*0.26), self.y + dp(s*0.18), self.x + dp(s*0.74), self.y + dp(s*0.18)], width=dp(3))
            else:
                Line(points=[self.x + dp(s*0.28), self.y + dp(s*0.16), self.x + dp(s*0.72), self.y + dp(s*0.22)], width=dp(3))

            # antenna
            Color(0.85, 0.9, 1, 0.9)
            Line(points=[self.x + dp(s*0.5), self.y + dp(s*0.92), self.x + dp(s*0.5), self.y + dp(s*1.08)], width=dp(1.4))
            Color(1, 0.9, 0.4, 1)
            Ellipse(pos=(self.x + dp(s*0.48), self.y + dp(s*1.06)), size=(dp(6), dp(6)))

    def _animate(self, _dt: float) -> None:
        self._blink += 1
        self._mouth += 1
        self._redraw()


def get_robot_svg() -> str:
    """Return SVG markup for the robot (without outer HTML wrapper)."""
    return '''
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
    <defs>
        <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
        <style>
            @keyframes blink { 0%, 90%, 100% { transform: scaleY(1); } 95% { transform: scaleY(0.1); } }
            @keyframes pulse { 0%,100% { opacity:0.8 } 50% { opacity:1; filter: drop-shadow(0 0 8px #00ffcc);} }
            .robot-eye { transform-origin: center; animation: blink 4s infinite ease-in-out; }
            .neon-part { animation: pulse 2s infinite ease-in-out; }
        </style>
    </defs>
    <rect x="95" y="15" width="10" height="25" rx="5" fill="#4a5568" />
    <circle cx="100" cy="15" r="8" fill="#00ffcc" class="neon-part" filter="url(#neon-glow)" />
    <rect x="25" y="75" width="15" height="50" rx="6" fill="#2d3748" />
    <rect x="160" y="75" width="15" height="50" rx="6" fill="#2d3748" />
    <rect x="35" y="40" width="130" height="120" rx="28" fill="#1a202c" stroke="#4a5568" stroke-width="4" />
    <path d="M 60 40 L 140 40 L 130 65 L 70 65 Z" fill="#2d3748" />
    <rect x="50" y="75" width="100" height="45" rx="12" fill="#0f172a" stroke="#2d3748" stroke-width="2" />
    <ellipse class="robot-eye" cx="75" cy="97" rx="10" ry="10" fill="#00ffcc" filter="url(#neon-glow)" />
    <ellipse class="robot-eye" cx="125" cy="97" rx="10" ry="10" fill="#00ffcc" filter="url(#neon-glow)" />
    <g fill="#4a5568">
        <rect x="75" y="135" width="6" height="12" rx="2" />
        <rect x="87" y="135" width="6" height="16" rx="2" />
        <rect x="99" y="135" width="6" height="16" rx="2" />
        <rect x="111" y="135" width="6" height="16" rx="2" />
        <rect x="123" y="135" width="6" height="12" rx="2" />
    </g>
</svg>
'''


def svg_to_texture(svg_markup: str, px_width: int, px_height: int):
    """Convert SVG markup to a Kivy texture using cairosvg. Returns None if unavailable."""
    if not CAIROSVG_AVAILABLE:
        return None
    try:
        png_bytes = cairosvg.svg2png(bytestring=svg_markup.encode('utf-8'), output_width=px_width, output_height=px_height)
        if not png_bytes:
            return None
        core = CoreImage(BytesIO(cast(bytes, png_bytes)), ext='png')
        return core.texture
    except Exception:
        return None


def _ukur_teks(draw: "ImageDraw.ImageDraw", teks: str, font: Any) -> tuple:
    """Ganti draw.textsize() yang sudah DIHAPUS total sejak Pillow 10.0.
    Pillow modern hanya punya draw.textbbox() / font.getbbox() sebagai penggantinya.
    """
    try:
        bbox = draw.textbbox((0, 0), teks, font=font)
        return (bbox[2] - bbox[0], bbox[3] - bbox[1])
    except Exception:
        try:
            bbox = font.getbbox(teks)
            return (bbox[2] - bbox[0], bbox[3] - bbox[1])
        except Exception:
            # Fallback kasar terakhir kalau semua API gagal
            return (len(teks) * 8, 16)


def generate_sticker(text: str, filename: Optional[str] = None) -> Optional[str]:
    """Generate a simple sticker PNG with text and emoji using Pillow.
    Returns path to PNG or None on failure.
    """
    try:
        stickers_dir = os.path.join(os.path.dirname(__file__), 'assets', 'stickers')
        os.makedirs(stickers_dir, exist_ok=True)
        if not filename:
            safe = ''.join(c for c in text if c.isalnum() or c in (' ', '-')).rstrip()
            filename = f"sticker_{int(time.time())}_{safe[:20].replace(' ', '_')}.png"
        path = os.path.join(stickers_dir, filename)

        # Create image 240x240 with rounded background
        size = (240, 240)
        bg = (13, 17, 23)
        im = PILImage.new('RGBA', size, bg + (255,))
        draw = ImageDraw.Draw(im)

        # draw rounded rect background
        radius = 28
        rect = (8, 8, size[0]-8, size[1]-8)
        draw.rounded_rectangle(rect, radius=radius, fill=(28,34,48,255))

        # draw big emoji / robot face
        try:
            font_emoji = ImageFont.truetype("seguiemj.ttf", 72)
        except Exception:
            font_emoji = ImageFont.load_default()
        emoji = '🤖'
        w, h = _ukur_teks(draw, emoji, font_emoji)
        draw.text(((size[0]-w)/2, 28), emoji, font=font_emoji, fill=(0,255,204,255))

        # draw text wrapped
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except Exception:
            font = ImageFont.load_default()
        lines = []
        words = text.split()
        line = ''
        for word in words:
            test = (line + ' ' + word).strip()
            if _ukur_teks(draw, test, font)[0] > (size[0] - 32):
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)

        y = 110
        for ln in lines[:4]:
            w, h = _ukur_teks(draw, ln, font)
            draw.text(((size[0]-w)/2, y), ln, font=font, fill=(220,220,230,255))
            y += h + 4

        im.save(path)
        return path
    except Exception:
        return None


def _get_stickers_dir() -> str:
    try:
        app = App.get_running_app()
        user_data_dir = getattr(app, 'user_data_dir', None)
        if user_data_dir:
            stickers_dir = os.path.join(user_data_dir, 'stickers')
        else:
            stickers_dir = os.path.join(os.path.dirname(__file__), 'assets', 'stickers')
    except Exception:
        stickers_dir = os.path.join(os.path.dirname(__file__), 'assets', 'stickers')
    os.makedirs(stickers_dir, exist_ok=True)
    return stickers_dir


def _save_base64_image(base64_data: str, filename: Optional[str] = None) -> Optional[str]:
    try:
        stickers_dir = _get_stickers_dir()
        if not filename:
            filename = f"sticker_ai_{int(time.time())}.png"
        path = os.path.join(stickers_dir, filename)
        data = base64.b64decode(base64_data)
        with open(path, 'wb') as f:
            f.write(data)
        return path
    except Exception:
        return None


def _save_pil_image(image: PILImage.Image, filename: Optional[str] = None) -> Optional[str]:
    try:
        stickers_dir = _get_stickers_dir()
        if not filename:
            filename = f"sticker_local_{int(time.time())}.png"
        path = os.path.join(stickers_dir, filename)
        image.save(path)
        return path
    except Exception:
        return None


def generate_local_sticker_from_prompt(prompt: str) -> Optional[str]:
    """Generate a sticker image from a locally installed Stable Diffusion model."""
    try:
        import importlib
        torch = importlib.import_module('torch')
        diffusers = importlib.import_module('diffusers')
        StableDiffusionPipeline = getattr(diffusers, 'StableDiffusionPipeline')
    except Exception:
        return None

    try:
        model_id = os.environ.get('LOCAL_SD_MODEL', 'runwayml/stable-diffusion-v1-5')
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        kwargs = {'torch_dtype': torch.float16} if device == 'cuda' else {}
        pipe = StableDiffusionPipeline.from_pretrained(model_id, **kwargs)
        pipe = pipe.to(device)
        result = pipe(prompt, num_inference_steps=25, guidance_scale=7.5)
        image = result.images[0]
        return _save_pil_image(image, filename=f"sticker_local_{int(time.time())}.png")
    except Exception:
        return None


def generate_ai_sticker_from_prompt(prompt: str) -> Optional[str]:
    """Generate a sticker image from a hosted AI image endpoint if an API key is configured."""
    api_key = os.environ.get('OPENAI_API_KEY') or os.environ.get('STABILITY_API_KEY')
    if not api_key:
        return None

    try:
        if os.environ.get('OPENAI_API_KEY'):
            url = 'https://api.openai.com/v1/images/generations'
            headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
            payload = {
                'prompt': prompt,
                'n': 1,
                'size': '512x512'
            }
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            b64 = data['data'][0]['b64_json']
        else:
            url = 'https://api.stability.ai/v1/generation/stable-diffusion-512-v2-1/text-to-image'
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
            payload = {
                'text_prompts': [{'text': prompt}],
                'cfg_scale': 7,
                'height': 512,
                'width': 512,
                'samples': 1
            }
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            b64 = data['artifacts'][0]['base64']

        return _save_base64_image(b64, filename=f"sticker_ai_{int(time.time())}.png")
    except Exception:
        return None

class AvatarBadge(FloatLayout):
    """Fallback sederhana untuk avatar robot jika dibutuhkan."""
    def __init__(self, emoji: str = "🤖", bg_color=WARNA_AKSEN, size_dp: float = 56, **kwargs: Any) -> None:
        super().__init__(size_hint=(None, None), size=(dp(size_dp), dp(size_dp)), **kwargs)
        with self.canvas.before:
            Color(*bg_color)
            self._circle = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(size_dp / 2)])
        self.bind(pos=self._update, size=self._update)
        self.add_widget(Label(
            text=emoji, font_size=f'{int(size_dp * 0.5)}sp',
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        ))

    def _update(self, *args: Any) -> None:
        self._circle.pos = self.pos
        self._circle.size = self.size


class ChatBubble(BoxLayout):
    def __init__(self, teks: str, dari_user: bool, image_path: Optional[str] = None, **kwargs: Any) -> None:
        super().__init__(orientation='horizontal', size_hint=(1, None), spacing=dp(6), opacity=0, **kwargs)
        bg = WARNA_BUBBLE_USER if dari_user else WARNA_BUBBLE_KIVY
        fg = (1, 1, 1, 1) if dari_user else (0.90, 0.95, 1, 1)
        lebar_maksimal = dp(230)

        # avatar: user gets emoji, robot tries to load assets/robot_logo.png, else emoji fallback
        if dari_user:
            avatar = Label(text="🧑", font_size='16sp', size_hint=(None, None), size=(dp(24), dp(24)))
        else:
            asset_img = os.path.join(os.path.dirname(__file__), 'assets', 'robot_logo.png')
            try:
                if os.path.exists(asset_img):
                    avatar = Image(source=asset_img, size_hint=(None, None), size=(dp(24), dp(24)), allow_stretch=True)
                else:
                    avatar = Label(text="🤖", font_size='16sp', size_hint=(None, None), size=(dp(24), dp(24)))
            except Exception:
                avatar = Label(text="🤖", font_size='16sp', size_hint=(None, None), size=(dp(24), dp(24)))

        label = Label(
            text=teks, font_size='13sp', color=fg,
            size_hint=(None, None), width=lebar_maksimal,
            halign='left', valign='top'
        )
        label.text_size = (lebar_maksimal, None)
        label.bind(texture_size=lambda inst, val: setattr(inst, 'height', val[1]))

        jam = Label(
            text=time.strftime("%H:%M"), font_size='9sp', color=(0.65, 0.68, 0.85, 1),
            size_hint=(None, None), width=lebar_maksimal, height=dp(12), halign='left'
        )
        jam.bind(size=lambda s, w: setattr(jam, 'text_size', w))

        isi_bubble = BoxLayout(orientation='vertical', size_hint=(None, None), spacing=dp(2))
        isi_bubble.add_widget(label)
        isi_bubble.add_widget(jam)
        isi_bubble.bind(minimum_height=isi_bubble.setter('height'))

        bubble = Card(bg_color=bg, radius=16, shadow=False, size_hint=(None, None), padding=(dp(12), dp(9)))
        bubble.add_widget(isi_bubble)

        # If an image_path is provided, add the image below the text inside the bubble
        if image_path and os.path.exists(image_path):
            try:
                img_w = dp(140)
                img = Image(source=image_path, size_hint=(None, None), size=(img_w, img_w * 0.75), allow_stretch=True, keep_ratio=True)
                isi_bubble.add_widget(img)
            except Exception:
                pass
        label.bind(size=lambda s, v: setattr(bubble, 'width', min(v[0] + dp(24), lebar_maksimal + dp(24))))
        isi_bubble.bind(height=lambda s, v: setattr(bubble, 'height', v + dp(16)))
        bubble.bind(height=lambda s, v: setattr(self, 'height', max(v, dp(26)) + dp(4)))

        spacer = Widget(size_hint=(1, 1))
        if dari_user:
            self.add_widget(spacer)
            self.add_widget(bubble)
            self.add_widget(avatar)
        else:
            self.add_widget(avatar)
            self.add_widget(bubble)
            self.add_widget(spacer)

        Animation(opacity=1, duration=0.2, t='out_quad').start(self)


class VideoModal(FloatLayout):
    def __init__(self, source: str, on_close: Callable[[], None], **kwargs: Any) -> None:
        super().__init__(size_hint=(1, 1), **kwargs)
        with self.canvas.before:
            Color(0, 0, 0, 0.9)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        if Window.width > Window.height:
            video_width = min(Window.width * 0.72, dp(760))
            video_height = min(Window.height * 0.64, dp(420))
        else:
            video_width = min(Window.width * 0.94, dp(520))
            video_height = min(Window.height * 0.48, dp(320))

        try:
            player: Widget = VideoPlayer(
                source=source,
                state='play',
                options={'eos': 'stop'},
                allow_fullscreen=False,
                size_hint=(None, None),
                size=(video_width, video_height),
                pos_hint={'center_x': 0.5, 'center_y': 0.58}
            )
        except TypeError:
            # Terjadi kalau perangkat tidak punya codec video (GStreamer/ffpyplayer)
            # sehingga VideoPlayer jatuh ke widget dummy yang tidak kenal
            # parameter di atas -- tampilkan pesan fallback alih-alih crash.
            player = Label(
                text="Pemutar video tidak tersedia di perangkat ini.\nGunakan tombol Tutup lalu buka linknya di browser.",
                size_hint=(None, None), size=(video_width, video_height),
                pos_hint={'center_x': 0.5, 'center_y': 0.58},
                halign='center', valign='middle', color=(1, 1, 1, 1)
            )
            player.bind(size=lambda s, w: setattr(player, 'text_size', w))
        self.add_widget(player)

        close_button = RoundedButton(
            text='Tutup',
            size_hint=(None, None),
            size=(dp(100), dp(40)),
            pos_hint={'center_x': 0.5, 'y': 0.04}
        )
        close_button.bind(on_release=lambda *_: on_close())
        self.add_widget(close_button)

    def _update_bg(self, *args: Any) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size


def buat_async_image_retry(source: str, max_percobaan: int = 3, jeda_detik: float = 2.5, **kwargs: Any) -> AsyncImage:
    """AsyncImage dengan retry otomatis. Kalau gambar gagal/belum termuat
    setelah beberapa detik (misal kena antrean loader Kivy atau koneksi
    lambat), coba reload beberapa kali sebelum menyerah.
    """
    img = AsyncImage(source=source, **kwargs)
    percobaan = {'n': 0}

    def cek_dan_retry(_dt: float) -> None:
        if img.texture is not None:
            return  # sudah berhasil termuat
        if percobaan['n'] >= max_percobaan:
            return
        percobaan['n'] += 1
        try:
            img.reload()
        except Exception:
            pass
        Clock.schedule_once(cek_dan_retry, jeda_detik)

    Clock.schedule_once(cek_dan_retry, jeda_detik)
    return img


class ClickableCardFloat(ButtonBehavior, CardFloat):
    pass


class NewsCard(BoxLayout):
    def __init__(self, judul: str, ringkasan: str, gambar: str, url: str,
                 on_tap: Callable[[str], None], **kwargs: Any) -> None:
        super().__init__(orientation='horizontal', size_hint=(1, None), height=dp(78), spacing=dp(8), **kwargs)
        self.url = url
        self.on_tap = on_tap

        thumb_wrap = CardFloat(bg_color=WARNA_THUMB_VIDEO_BG, radius=10, size_hint=(None, None), size=(dp(68), dp(68)))
        if gambar:
            thumb = buat_async_image_retry(gambar, size_hint=(1, 1), allow_stretch=True, keep_ratio=True)
        else:
            thumb = Label(
                text="No Image", font_size='10sp', color=(0.88, 0.88, 0.92, 1),
                halign='center', valign='middle', size_hint=(1, 1)
            )
            thumb.bind(size=lambda s, w: setattr(thumb, 'text_size', s.size))
        thumb_wrap.add_widget(thumb)
        self.add_widget(thumb_wrap)

        kolom_teks = BoxLayout(orientation='vertical', size_hint=(1, 1), spacing=dp(2))
        label_judul = Label(
            text=judul, font_size='12sp', bold=True, color=(0.94, 0.96, 1, 1),
            size_hint=(1, None), height=dp(20), halign='left', valign='middle', shorten=True
        )
        label_judul.bind(size=lambda s, w: setattr(label_judul, 'text_size', w))
        kolom_teks.add_widget(label_judul)

        label_ringkasan = Label(
            text=ringkasan, font_size='10sp', color=(0.72, 0.80, 0.92, 1),
            size_hint=(1, None), height=dp(44), halign='left', valign='top', shorten=True
        )
        label_ringkasan.bind(size=lambda s, w: setattr(label_ringkasan, 'text_size', w))
        kolom_teks.add_widget(label_ringkasan)

        self.add_widget(kolom_teks)

    def on_touch_down(self, touch: Any) -> bool:
        if self.collide_point(*touch.pos):
            self.on_tap(self.url)
            return True
        return super().on_touch_down(touch)  # type: ignore[safe-super]


class PercentPill(BoxLayout):
    """Pill kecil ala CoinGecko: panah + persentase, hijau kalau naik, merah kalau turun."""
    def __init__(self, persen: float, **kwargs: Any) -> None:
        super().__init__(size_hint=(None, None), size=(dp(62), dp(20)), **kwargs)
        naik = persen >= 0
        warna = (0.14, 0.58, 0.34, 1) if naik else (0.78, 0.22, 0.26, 1)
        with self.canvas.before:
            Color(*warna)
            self._bg = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.bind(pos=self._update, size=self._update)
        panah = "▲" if naik else "▼"
        self.add_widget(Label(
            text=f"{panah} {abs(persen):.1f}%", font_size='10sp', bold=True, color=(1, 1, 1, 1)
        ))

    def _update(self, *args: Any) -> None:
        self._bg.pos = self.pos
        self._bg.size = self.size


class StatBox(Card):
    """Kotak statistik kecil (Kap Pasar / Volume) dengan nilai yang bisa di-update dinamis."""
    def __init__(self, label: str, nilai_awal: str = "Memuat...", **kwargs: Any) -> None:
        super().__init__(bg_color=(0.06, 0.11, 0.20, 1), radius=14, shadow=False,
                          orientation='vertical', padding=(dp(10), dp(8)), spacing=dp(3), **kwargs)
        lbl_judul = Label(
            text=label, font_size='10sp', color=(0.62, 0.74, 0.92, 1),
            size_hint=(1, None), height=dp(16), halign='left', valign='middle'
        )
        lbl_judul.bind(size=lambda s, w: setattr(lbl_judul, 'text_size', w))
        self.add_widget(lbl_judul)

        self._baris_nilai = BoxLayout(orientation='horizontal', size_hint=(1, 1), spacing=dp(6))
        self._lbl_nilai = Label(
            text=nilai_awal, font_size='13sp', bold=True, color=(1, 1, 1, 1),
            halign='left', valign='middle', shorten=True
        )
        self._lbl_nilai.bind(size=lambda s, w: setattr(self._lbl_nilai, 'text_size', w))
        self._baris_nilai.add_widget(self._lbl_nilai)
        self.add_widget(self._baris_nilai)
        self._pill: Optional[PercentPill] = None

    def set_nilai(self, nilai_teks: str, persen: Optional[float] = None) -> None:
        self._lbl_nilai.text = nilai_teks
        if self._pill is not None:
            self._baris_nilai.remove_widget(self._pill)
            self._pill = None
        if persen is not None:
            self._pill = PercentPill(persen)
            self._baris_nilai.add_widget(self._pill)


class CoinRow(BoxLayout):
    """Satu baris koin: simbol, nama, harga, dan pill perubahan 24 jam."""
    def __init__(self, simbol: str, nama: str, harga_teks: str, persen_24j: float, **kwargs: Any) -> None:
        super().__init__(orientation='horizontal', size_hint=(1, None), height=dp(34), spacing=dp(8), **kwargs)

        lbl_simbol = Label(
            text=simbol.upper(), font_size='11sp', bold=True, color=(0.62, 0.76, 1, 1),
            size_hint=(None, 1), width=dp(48), halign='left', valign='middle'
        )
        lbl_simbol.bind(size=lambda s, w: setattr(lbl_simbol, 'text_size', w))
        self.add_widget(lbl_simbol)

        lbl_nama = Label(
            text=nama, font_size='11sp', color=(0.80, 0.86, 0.96, 1),
            size_hint=(1, 1), halign='left', valign='middle', shorten=True
        )
        lbl_nama.bind(size=lambda s, w: setattr(lbl_nama, 'text_size', w))
        self.add_widget(lbl_nama)

        lbl_harga = Label(
            text=harga_teks, font_size='11sp', bold=True, color=(1, 1, 1, 1),
            size_hint=(None, 1), width=dp(96), halign='right', valign='middle', shorten=True
        )
        lbl_harga.bind(size=lambda s, w: setattr(lbl_harga, 'text_size', w))
        self.add_widget(lbl_harga)

        self.add_widget(PercentPill(persen_24j))


class Sparkline(Widget):
    """Garis mini untuk menunjukkan pergerakan harga 7 hari ala CoinGecko."""
    def __init__(self, prices: List[float], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.prices = prices or []
        self.bind(pos=self._update, size=self._update)

    def _update(self, *args: Any) -> None:
        canvas = self.canvas
        if canvas is None:
            return

        canvas.clear()
        if not self.prices or self.width <= 0 or self.height <= 0:
            return

        terkecil = min(self.prices)
        terbesar = max(self.prices)
        rentang = terbesar - terkecil if terbesar != terkecil else 1.0
        langkah = self.width / max(len(self.prices) - 1, 1)
        poin: List[float] = []

        for idx, harga in enumerate(self.prices):
            x = self.x + idx * langkah
            y_norm = (harga - terkecil) / rentang
            y = self.y + dp(6) + y_norm * (self.height - dp(12))
            poin.extend([x, y])

        with canvas:
            Color(0.24, 0.68, 1, 0.9)
            Line(points=poin, width=1.8, cap='round')


class CoinCard(Card):
    """Kartu individual satu koin dengan harga, perubahan, dan grafik mini."""
    def __init__(self, simbol: str, nama: str, harga_teks: str, persen_24j: float,
                 sparkline: List[float], image_url: str = '', **kwargs: Any) -> None:
        super().__init__(bg_color=(0.06, 0.12, 0.20, 0.28), radius=18, shadow=False,
                          orientation='vertical', padding=(dp(10), dp(10)), spacing=dp(8),
                          size_hint=(1, None), height=dp(170), **kwargs)

        header = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(28), spacing=dp(8))
        if image_url:
            icon = buat_async_image_retry(
                image_url, size_hint=(None, None), size=(dp(28), dp(28)),
                allow_stretch=True, keep_ratio=True
            )
        else:
            icon = Label(
                text=simbol[:1].upper(), font_size='14sp', bold=True,
                size_hint=(None, None), size=(dp(28), dp(28)),
                color=(0.86, 0.94, 1, 1), halign='center', valign='middle'
            )
            icon.bind(size=lambda s, w: setattr(icon, 'text_size', s.size))
        header.add_widget(icon)

        info = BoxLayout(orientation='vertical', spacing=dp(2))
        lbl_simbol = Label(
            text=simbol.upper(), font_size='12sp', bold=True, color=(0.86, 0.94, 1, 1),
            size_hint=(1, None), height=dp(18), halign='left', valign='middle'
        )
        lbl_simbol.bind(size=lambda s, w: setattr(lbl_simbol, 'text_size', w))
        info.add_widget(lbl_simbol)
        lbl_nama = Label(
            text=nama, font_size='10sp', color=(0.72, 0.78, 0.96, 1),
            size_hint=(1, None), height=dp(16), halign='left', valign='middle', shorten=True
        )
        lbl_nama.bind(size=lambda s, w: setattr(lbl_nama, 'text_size', w))
        info.add_widget(lbl_nama)
        header.add_widget(info)

        price_col = BoxLayout(orientation='vertical', size_hint=(None, 1), width=dp(74), spacing=dp(4))
        lbl_harga = Label(
            text=harga_teks, font_size='11sp', bold=True, color=(1, 1, 1, 1),
            size_hint=(1, None), height=dp(18), halign='right', valign='middle', shorten=True
        )
        lbl_harga.bind(size=lambda s, w: setattr(lbl_harga, 'text_size', w))
        price_col.add_widget(lbl_harga)
        price_col.add_widget(PercentPill(persen_24j))
        header.add_widget(price_col)

        self.add_widget(header)
        self.add_widget(Sparkline(sparkline, size_hint=(1, None), height=dp(48)))

        self.add_widget(Label(
            text=f"24h {persen_24j:+.1f}%", font_size='10sp', color=(0.72, 0.82, 1, 1),
            size_hint=(1, None), height=dp(18), halign='left', valign='middle'
        ))


class RobotAIVector(BoxLayout):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        Window.clearcolor = WARNA_BG
        self.orientation = 'vertical'
        self.padding = dp(12)
        self.spacing = dp(12)
        self.tts: Any = None
        self.memory = MemoryStore()
        self.ringkasan_pasar_chat = "Data pasar belum termuat, coba lagi sebentar Bos."
        self.daftar_app: Dict[str, str] = {}
        self._tts_listener: Any = None
        self._recognition_listener: Any = None
        self._recognizer: Any = None

        if platform == 'android':
            self.init_android_tts()
            self.muat_daftar_aplikasi_terinstall()

        self.status_robot = 'idle'
        self.assistant_history: List[str] = []

        # -------------------- HEADER --------------------
        header = Card(bg_color=WARNA_CARD_HEADER, radius=20, orientation='horizontal',
                      size_hint=(1, None), height=dp(84), padding=dp(10), spacing=dp(12))

        avatar_wrap = FloatLayout(size_hint=(None, 1), width=dp(68))
        # Save SVG -> PNG asset if possible, then use the asset image in the header
        assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
        asset_path = os.path.join(assets_dir, 'robot_logo.png')
        try:
            os.makedirs(assets_dir, exist_ok=True)
        except Exception:
            pass

        used_image = False
        if not os.path.exists(asset_path) and CAIROSVG_AVAILABLE:
            try:
                cairosvg.svg2png(bytestring=get_robot_svg().encode('utf-8'), write_to=asset_path,
                                  output_width=int(dp(58)), output_height=int(dp(58)))
            except Exception:
                pass

        if os.path.exists(asset_path):
            from kivy.uix.image import Image as KivyImage
            try:
                img = KivyImage(source=asset_path, size_hint=(None, None), size=(dp(52), dp(52)),
                                 allow_stretch=True, keep_ratio=True, pos_hint={'center_x': 0.5, 'center_y': 0.5})
                self.robot_face = img
                avatar_wrap.add_widget(img)
                used_image = True
            except Exception:
                used_image = False

        if not used_image:
            # Fallback: try texture conversion, else use animated canvas avatar
            svg_texture = svg_to_texture(get_robot_svg(), int(dp(58)), int(dp(58)))
            if svg_texture:
                from kivy.uix.image import Image as KivyImage
                img = KivyImage(
                    texture=svg_texture,
                    size_hint=(None, None),
                    size=(dp(52), dp(52)),
                    allow_stretch=True,
                    keep_ratio=True,
                    pos_hint={'center_x': 0.5, 'center_y': 0.5}
                )
                self.robot_face = img
                avatar_wrap.add_widget(img)
            else:
                self.robot_face = AnimatedRobotAvatar(bg_color=WARNA_AKSEN, size_dp=58)
                avatar_wrap.add_widget(self.robot_face)
        header.add_widget(avatar_wrap)

        kolom_judul = BoxLayout(orientation='vertical', size_hint=(1, 1), spacing=dp(2))
        judul_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(24), spacing=dp(8))
        judul_row.add_widget(Label(
            text=f"{AI_NAME} AI Assistant", font_size='21sp', bold=True, color=(0.75, 0.78, 1, 1),
            halign='left', valign='bottom', size_hint=(1, 1)
        ))
        self.jam_header = Label(
            text=time.strftime("%H:%M"), font_size='12sp', bold=True, color=(0.88, 0.91, 1, 1),
            halign='right', valign='middle', size_hint=(None, 1), width=dp(56)
        )
        judul_row.add_widget(self.jam_header)
        kolom_judul.add_widget(judul_row)
        self.status_label = Label(
            text="🟢 Online & Siap", font_size='12sp', color=(0.45, 0.92, 0.65, 1),
            halign='left', valign='top', size_hint=(1, None), height=dp(18)
        )
        kolom_judul.add_widget(self.status_label)
        for lbl in kolom_judul.children:
            lbl.bind(size=lambda s, w: setattr(s, 'text_size', w))
        header.add_widget(kolom_judul)
        self.add_widget(header)
        Clock.schedule_interval(self._update_jam_header, 1)
        self._update_jam_header(0)

        # -------------------- TOMBOL UTAMA --------------------
        tombol_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(44), spacing=dp(10))
        self.btn_dengar = RoundedButton(text="🎤  Dengar Perintah", bg_color=WARNA_TOMBOL_MIC, bold=True, radius=22, size_hint=(1, 1))
        self.btn_dengar.bind(on_press=self.mulai_dengar_perintah)
        tombol_row.add_widget(self.btn_dengar)

        self.btn_overlay = RoundedButton(text="🤖  Overlay Robot", bg_color=WARNA_TOMBOL_KIRIM, bold=True, radius=22, size_hint=(1, 1))
        self.btn_overlay.bind(on_press=self.mulai_overlay_service)
        tombol_row.add_widget(self.btn_overlay)

        self.btn_otomasi = RoundedButton(text="💹  Buka Binance", bg_color=WARNA_TOMBOL_TRADING, bold=True, radius=22, size_hint=(1, 1))
        self.btn_otomasi.bind(on_press=lambda i: self.buka_aplikasi_by_package("com.binance.dev"))
        tombol_row.add_widget(self.btn_otomasi)
        self.add_widget(tombol_row)

        # -------------------- CHAT CARD --------------------
        self.chat_terbuka = True
        self.chat_card = Card(bg_color=WARNA_CARD_CHAT, radius=20, orientation='vertical',
                               size_hint=(1, None), height=dp(330), padding=dp(12), spacing=dp(8))

        header_chat = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(26), spacing=dp(6))
        header_chat.add_widget(Label(
            text="💬  Chat AI Asisten", font_size='14sp', bold=True,
            color=(0.80, 0.82, 1, 1), size_hint=(1, 1), halign='left', valign='middle'
        ))
        badge_groq = RoundedButton(
            text="⚡ Groq", bg_color=(0.259, 0.522, 0.957, 0.16), outline_color=(0.259, 0.522, 0.957, 0.75),
            outline_width=1.2, size_hint=(None, 1), width=dp(62), font_size='10sp', radius=13,
            color=(0.55, 0.75, 1, 1)
        )
        header_chat.add_widget(badge_groq)
        self.btn_toggle_chat = RoundedButton(
            text="▼", bg_color=(0.22, 0.23, 0.36, 1), size_hint=(None, 1), width=dp(30), font_size='11sp', radius=15
        )
        self.btn_toggle_chat.bind(on_press=self._toggle_chat)
        header_chat.add_widget(self.btn_toggle_chat)
        self.chat_card.add_widget(header_chat)

        self.chat_body = BoxLayout(orientation='vertical', size_hint=(1, None), height=dp(330) - dp(36), spacing=dp(8))

        self.chat_scroll = ScrollView(
            size_hint=(1, 1), bar_width=dp(4), scroll_type=['content', 'bars'],
            effect_cls=DampedScrollEffect, scroll_distance=5,
            bar_color=(0.55, 0.45, 1.0, 0.85), bar_inactive_color=(0.3, 0.3, 0.45, 0.3)
        )
        self.chat_container = BoxLayout(orientation='vertical', size_hint=(1, None), spacing=dp(8))
        self.chat_container.bind(minimum_height=self.chat_container.setter('height'))
        self.chat_scroll.add_widget(self.chat_container)
        self.chat_body.add_widget(self.chat_scroll)

        tools_row = ScrollView(
            size_hint=(1, None), height=dp(30), do_scroll_y=False,
            effect_cls=DampedScrollEffect, bar_width=0
        )
        tools_container = BoxLayout(orientation='horizontal', size_hint=(None, 1), spacing=dp(8))
        tools_container.bind(minimum_width=tools_container.setter('width'))

        daftar_tools = [
            ("🧹 Bersihkan", self._bersihkan_chat, dp(90), None),
            ("💡 Ide Hari Ini", lambda x: self.proses_pesan("Beri aku ide menarik buat hari ini, Bos!"), dp(118), GOOGLE_YELLOW),
            ("📈 Cek Crypto", lambda x: self.proses_pesan("Bagaimana harga crypto saat ini?"), dp(108), GOOGLE_GREEN),
            ("🌤️ Cuaca", lambda x: self.proses_pesan("cuaca Jakarta"), dp(85), GOOGLE_BLUE),
            ("⏰ Pengingat", lambda x: self.proses_pesan("lihat pengingat"), dp(105), None),
            ("🧮 Kalkulator", lambda x: self.proses_pesan("hitung "), dp(108), None),
            ("🌐 Terjemah", lambda x: self.proses_pesan("terjemahkan  ke bahasa Inggris: "), dp(98), GOOGLE_RED),
        ]
        for teks_tombol, aksi, lebar, warna_outline in daftar_tools:
            # Gaya chip bergaris tepi (outline) ala Groq Playground: isian gelap
            # transparan + border tipis warna aksen, bukan solid seperti sebelumnya.
            outline = (warna_outline[0], warna_outline[1], warna_outline[2], 0.65) if warna_outline else (0.45, 0.5, 0.65, 0.45)
            btn = RoundedButton(
                text=teks_tombol, bg_color=(0.12, 0.13, 0.20, 0.55),
                outline_color=outline, outline_width=1.1,
                size_hint=(None, 1), width=lebar, font_size='10sp', radius=15
            )
            btn.bind(on_press=aksi)
            tools_container.add_widget(btn)

        tools_row.add_widget(tools_container)
        self.chat_body.add_widget(tools_row)


        input_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(42), spacing=dp(8))
        input_wrap = Card(bg_color=(0.13, 0.14, 0.23, 1), radius=21, shadow=False,
                           size_hint=(1, 1), padding=(dp(12), dp(2)))
        self.chat_input = TextInput(
            hint_text=f"Ketik pesan ke {AI_NAME}...", multiline=False,
            size_hint=(1, 1), background_color=(0, 0, 0, 0),
            foreground_color=(1, 1, 1, 1), hint_text_color=(0.55, 0.58, 0.72, 1),
            padding=(dp(4), dp(10)), cursor_color=(0.6, 0.5, 1, 1)
        )
        self.chat_input.bind(on_text_validate=self._kirim_dari_input)
        input_wrap.add_widget(self.chat_input)
        input_row.add_widget(input_wrap)

        self.btn_kirim = RoundedButton(text="➤", bg_color=WARNA_TOMBOL_KIRIM, size_hint=(None, 1),
                                        width=dp(46), bold=True, radius=23)
        self.btn_kirim.bind(on_press=self._kirim_dari_input)
        input_row.add_widget(self.btn_kirim)

        # Sticker generation button: create sticker from input or last assistant reply
        self.btn_sticker = RoundedButton(text="🎨", bg_color=GOOGLE_BLUE, size_hint=(None, 1),
                         width=dp(46), bold=True, radius=23)
        self.btn_sticker.bind(on_press=self._buat_sticker_dari_input)
        input_row.add_widget(self.btn_sticker)

        # Local-model sticker generation button
        self.btn_local_sticker = RoundedButton(text="🧠", bg_color=GOOGLE_YELLOW, size_hint=(None, 1),
                         width=dp(46), bold=True, radius=23)
        self.btn_local_sticker.bind(on_press=self._buat_local_ai_sticker)
        input_row.add_widget(self.btn_local_sticker)

        # Hosted API sticker generation button
        self.btn_hosted_sticker = RoundedButton(text="☁️", bg_color=GOOGLE_GREEN, size_hint=(None, 1),
                         width=dp(46), bold=True, radius=23)
        self.btn_hosted_sticker.bind(on_press=self._buat_hosted_ai_sticker)
        input_row.add_widget(self.btn_hosted_sticker)

        self.chat_body.add_widget(input_row)
        self.chat_card.add_widget(self.chat_body)
        self.add_widget(self.chat_card)

        # -------------------- KONTEN BAWAH (scrollable) --------------------
        scroll = ScrollView(
            size_hint=(1, 1), bar_width=dp(5), scroll_type=['content', 'bars'],
            effect_cls=DampedScrollEffect, scroll_distance=5,
            bar_color=(0.55, 0.45, 1.0, 0.85), bar_inactive_color=(0.3, 0.3, 0.45, 0.35)
        )
        self.konten = BoxLayout(orientation='vertical', size_hint=(1, None), spacing=dp(14), padding=(0, dp(4)))
        self.konten.bind(minimum_height=self.konten.setter('height'))

        # -- Kartu Ringkasan Pasar Global (ala CoinGecko) dengan tombol buka/tutup --
        self.pasar_terbuka = True
        self.card_pasar = Card(bg_color=WARNA_CARD_PASAR, radius=20, orientation='vertical',
                                size_hint=(1, None), height=dp(40), padding=dp(12), spacing=dp(10))

        header_pasar = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(26), spacing=dp(6))
        judul_pasar = Label(
            text="📊 Ringkasan Pasar Global", font_size='14sp', bold=True,
            color=(0.85, 0.92, 1, 1), size_hint=(1, 1), halign='left', valign='middle'
        )
        judul_pasar.bind(size=lambda s, w: setattr(judul_pasar, 'text_size', w))
        header_pasar.add_widget(judul_pasar)

        self.label_ticker_pasar = Label(
            text="", font_size='11sp', color=(0.78, 0.86, 1, 1),
            size_hint=(None, 1), width=0, halign='right', valign='middle', opacity=0
        )
        self.label_ticker_pasar.bind(size=lambda s, w: setattr(self.label_ticker_pasar, 'text_size', w))
        header_pasar.add_widget(self.label_ticker_pasar)

        self.btn_toggle_pasar = RoundedButton(
            text="▼", bg_color=(0.14, 0.22, 0.36, 1), size_hint=(None, 1), width=dp(30), font_size='11sp', radius=15
        )
        self.btn_toggle_pasar.bind(on_press=self._toggle_pasar)
        header_pasar.add_widget(self.btn_toggle_pasar)
        self.card_pasar.add_widget(header_pasar)

        self.pasar_body = BoxLayout(orientation='vertical', size_hint=(1, None), spacing=dp(10))
        self.pasar_body.bind(minimum_height=self.pasar_body.setter('height'))
        self.pasar_body.bind(height=lambda s, v: self._update_tinggi_card_pasar())

        stat_row = BoxLayout(orientation='horizontal', size_hint=(1, None), height=dp(58), spacing=dp(10))
        self.stat_cap = StatBox("Kap Pasar")
        self.stat_volume = StatBox("Volume 24 Jam")
        stat_row.add_widget(self.stat_cap)
        stat_row.add_widget(self.stat_volume)
        self.pasar_body.add_widget(stat_row)

        label_top_koin = Label(
            text="🔥 Top Koin", font_size='12sp', bold=True, color=(0.85, 0.9, 1, 1),
            size_hint=(1, None), height=dp(18), halign='left', valign='middle'
        )
        label_top_koin.bind(size=lambda s, w: setattr(label_top_koin, 'text_size', w))
        self.pasar_body.add_widget(label_top_koin)

        self.list_koin = GridLayout(
            cols=1 if Window.width < dp(420) else 2,
            spacing=dp(10), size_hint=(1, None),
            row_force_default=True, row_default_height=dp(170),
            padding=(dp(8), dp(8), dp(8), dp(8))
        )
        with self.list_koin.canvas.before:
            Color(0.18, 0.24, 0.38, 0.40)
            self._koin_bg = RoundedRectangle(pos=self.list_koin.pos, size=self.list_koin.size, radius=[dp(18)])
            Color(0.60, 0.72, 1, 0.14)
            self._koin_divider = Line(points=[self.list_koin.x + self.list_koin.width / 2, self.list_koin.y,
                                              self.list_koin.x + self.list_koin.width / 2, self.list_koin.y + self.list_koin.height], width=1)

        self.list_koin.bind(minimum_height=self.list_koin.setter('height'))
        self.list_koin.bind(pos=self._update_list_koin_bg, size=self._update_list_koin_bg)
        self.list_koin.add_widget(Label(
            text="Memuat data pasar...", font_size='11sp', color=(0.75, 0.8, 0.9, 1),
            size_hint=(1, None), height=dp(30)
        ))
        self.pasar_body.add_widget(self.list_koin)

        self.card_pasar.add_widget(self.pasar_body)
        self._update_tinggi_card_pasar()
        self.konten.add_widget(self.card_pasar)

        card_video = Card(bg_color=WARNA_CARD_VIDEO, radius=20, orientation='vertical',
                           size_hint=(1, None), height=dp(202), padding=dp(12), spacing=dp(8))
        card_video.add_widget(Label(
            text="🔥 Video Trending (YouTube)", font_size='14sp', bold=True,
            color=(1, 0.82, 0.96, 1), size_hint=(1, None), height=dp(22)
        ))
        self.scroll_trending_video = ScrollView(
            size_hint=(1, None), height=dp(148), do_scroll_x=True, do_scroll_y=False,
            effect_cls=DampedScrollEffect, bar_width=0
        )
        self.grid_trending_video = GridLayout(rows=1, size_hint=(None, 1), spacing=dp(10))
        self.grid_trending_video.bind(minimum_width=self.grid_trending_video.setter('width'))
        self.scroll_trending_video.add_widget(self.grid_trending_video)
        card_video.add_widget(self.scroll_trending_video)
        self.konten.add_widget(card_video)

        self.card_berita = Card(bg_color=WARNA_CARD_BERITA, radius=20, orientation='vertical',
                                 size_hint=(1, None), height=dp(120), padding=dp(12), spacing=dp(8))
        self.card_berita.add_widget(Label(
            text="📰 Berita Trending", font_size='14sp', bold=True,
            color=(0.90, 0.98, 1, 1), size_hint=(1, None), height=dp(22)
        ))
        self.list_berita = GridLayout(cols=1, size_hint=(1, None), spacing=dp(10), padding=(dp(6), dp(6), dp(6), dp(6)))
        with self.list_berita.canvas.before:
            Color(0.12, 0.16, 0.26, 0.80)
            self._berita_bg = RoundedRectangle(pos=self.list_berita.pos, size=self.list_berita.size, radius=[dp(16)])
            Color(0.70, 0.80, 1, 0.15)
            self._berita_divider = Line(points=[self.list_berita.x + self.list_berita.width / 2, self.list_berita.y,
                                                self.list_berita.x + self.list_berita.width / 2, self.list_berita.y + self.list_berita.height], width=1)
        self.list_berita.bind(minimum_height=self.list_berita.setter('height'))
        self.list_berita.bind(pos=self._update_list_berita_bg, size=self._update_list_berita_bg)
        self.list_berita.bind(size=lambda *_: self._update_berita_layout())
        self._update_berita_layout()
        self.info_berita_pesan = Label(
            text="Memuat berita trending...", font_size='12sp', color=(0.85, 0.92, 0.98, 1),
            size_hint=(1, None), height=dp(24)
        )
        self.list_berita.add_widget(self.info_berita_pesan)
        self.card_berita.add_widget(self.list_berita)
        self.konten.add_widget(self.card_berita)

        scroll.add_widget(self.konten)
        self.add_widget(scroll)

        self.video_modal: Optional[VideoModal] = None

        # Window.bind dipasang di SINI (akhir __init__), bukan di awal --
        # supaya event resize (yang di Android selalu terjadi begitu app
        # dibuka, saat window disesuaikan ke ukuran layar asli) tidak
        # memicu _update_layout_on_resize sebelum semua widget (list_koin,
        # list_berita, card_pasar, dst) selesai dibuat. Ini penyebab app
        # force-close saat startup sebelumnya.
        Window.bind(size=self._update_layout_on_resize)

        Clock.schedule_once(self.sambut_bos, 0.8)
        Clock.schedule_interval(lambda dt: self.muat_informasi_hangat(), 60)
        Clock.schedule_interval(lambda dt: self.muat_trending_video(), 300)
        Clock.schedule_interval(lambda dt: self.muat_trending_berita(), 300)

    def _toggle_chat(self, instance: Any) -> None:
        self.chat_terbuka = not self.chat_terbuka
        if self.chat_terbuka:
            if self.chat_body.parent is None:
                self.chat_card.add_widget(self.chat_body)
            self.chat_card.height = dp(330)
            self.btn_toggle_chat.text = "▼"
        else:
            if self.chat_body.parent is not None:
                self.chat_card.remove_widget(self.chat_body)
            self.chat_card.height = dp(42)
            self.btn_toggle_chat.text = "▲"

    def _toggle_pasar(self, instance: Any) -> None:
        self.pasar_terbuka = not self.pasar_terbuka
        if self.pasar_terbuka:
            if self.pasar_body.parent is None:
                self.card_pasar.add_widget(self.pasar_body)
            self.btn_toggle_pasar.text = "▼"
            self.label_ticker_pasar.opacity = 0
            self.label_ticker_pasar.width = 0
        else:
            if self.pasar_body.parent is not None:
                self.card_pasar.remove_widget(self.pasar_body)
            self.btn_toggle_pasar.text = "▲"
            self.label_ticker_pasar.opacity = 1
            self.label_ticker_pasar.width = dp(150)
        self._update_tinggi_card_pasar()

    def _update_list_koin_bg(self, *args: Any) -> None:
        if hasattr(self, '_koin_bg'):
            self._koin_bg.pos = self.list_koin.pos
            self._koin_bg.size = self.list_koin.size
        if hasattr(self, '_koin_divider'):
            self._koin_divider.points = [
                self.list_koin.x + self.list_koin.width / 2,
                self.list_koin.y,
                self.list_koin.x + self.list_koin.width / 2,
                self.list_koin.y + self.list_koin.height
            ]

    def _update_jam_header(self, _dt: float = 0) -> None:
        if hasattr(self, 'jam_header') and self.jam_header is not None:
            self.jam_header.text = time.strftime('%H:%M')

    def _update_berita_layout(self, *args: Any) -> None:
        if not hasattr(self, 'list_berita'):
            return
        lebar = max(self.list_berita.width, dp(1))
        self.list_berita.cols = 1 if lebar < dp(700) else 2

    def _update_list_berita_bg(self, *args: Any) -> None:
        if hasattr(self, '_berita_bg'):
            self._berita_bg.pos = self.list_berita.pos
            self._berita_bg.size = self.list_berita.size
        if hasattr(self, '_berita_divider'):
            self._berita_divider.points = [
                self.list_berita.x + self.list_berita.width / 2,
                self.list_berita.y,
                self.list_berita.x + self.list_berita.width / 2,
                self.list_berita.y + self.list_berita.height
            ]

    def _update_tinggi_card_pasar(self) -> None:
        """Hitung ulang tinggi card_pasar sesuai status buka/tutup & isi konten."""
        tinggi_header = dp(26)
        padding_vertikal = dp(12) * 2
        if self.pasar_terbuka:
            self.card_pasar.height = tinggi_header + dp(10) + self.pasar_body.height + padding_vertikal
        else:
            self.card_pasar.height = tinggi_header + padding_vertikal

    def _update_layout_on_resize(self, instance: Any, size: Any) -> None:
        # Pengaman lapis kedua: kalau untuk alasan apapun fungsi ini
        # terpanggil sebelum semua widget selesai dibuat, jangan crash.
        if not hasattr(self, 'list_koin') or not hasattr(self, 'card_pasar'):
            return
        self.list_koin.cols = 1 if size[0] < dp(420) else 2
        self._update_berita_layout()
        self._update_list_koin_bg()
        self._update_list_berita_bg()
        self._update_tinggi_card_pasar()

    def _has_audio_permission(self) -> bool:
        try:
            return activity.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        except Exception:
            return False

    def _request_audio_permission(self) -> None:
        try:
            activity.requestPermissions([Manifest.permission.RECORD_AUDIO], 101)
            self.status_label.text = "Izinkan akses mikrofon lalu tekan kembali tombol Dengar Perintah."
        except Exception as e:
            self.status_label.text = f"Gagal minta izin mikrofon: {e}"

    def _has_overlay_permission(self) -> bool:
        try:
            return Settings.canDrawOverlays(activity)
        except Exception:
            return False

    def _request_overlay_permission(self) -> None:
        try:
            uri = Uri.parse(f"package:{activity.getPackageName()}")
            intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, uri)
            activity.startActivity(intent)
            self.status_label.text = "Buka pengaturan overlay lalu aktifkan izin 'Tampilkan di atas aplikasi lain'."
        except Exception as e:
            self.status_label.text = f"Gagal minta izin overlay: {e}"

    def mulai_overlay_service(self, instance: Any) -> None:
        if platform != 'android':
            self.status_label.text = "[PC Mode] Overlay hanya untuk Android."
            return

        if not self._has_overlay_permission():
            self._request_overlay_permission()
            return

        try:
            overlay_service = autoclass('org.kivy.android.PythonService')
            service_intent = Intent(activity, overlay_service)
            activity.startService(service_intent)
            self.status_label.text = "Overlay robot sedang dijalankan."
        except Exception as e:
            self.status_label.text = f"Gagal mulai service overlay: {e}"

    def _bersihkan_chat(self, instance: Any) -> None:
        self.chat_container.clear_widgets()
        self._tambah_bubble("Chat dibersihkan, Bos! Ada yang mau ditanyakan lagi?", dari_user=False)

    def set_status_robot(self, state: str) -> None:
        self.status_robot = state
        peta = {
            'idle': ("🟢 Online", (0.45, 0.92, 0.65, 1)),
            'listening': ("🎙️ Mendengarkan...", (0.98, 0.65, 0.35, 1)),
            'thinking': ("🤔 Berpikir...", (0.55, 0.72, 1, 1)),
            'speaking': ("🔊 Bicara...", (0.92, 0.55, 0.95, 1)),
        }
        teks, warna = peta.get(state, peta['idle'])
        self.status_label.text = teks
        self.status_label.color = warna

    def _tambah_bubble(self, teks: str, dari_user: bool) -> ChatBubble:
        bubble = ChatBubble(teks, dari_user)
        self.chat_container.add_widget(bubble)
        Clock.schedule_once(lambda dt: setattr(self.chat_scroll, 'scroll_y', 0), 0.05)
        # Track assistant messages for sticker prompts
        try:
            if not dari_user:
                self.assistant_history.append(teks)
                # keep last 20
                if len(self.assistant_history) > 20:
                    self.assistant_history = self.assistant_history[-20:]
        except Exception:
            pass
        return bubble

    def _kirim_dari_input(self, instance: Any) -> None:
        pesan = self.chat_input.text.strip()
        if not pesan:
            return
        self.chat_input.text = ""
        self.proses_pesan(pesan)

    def _buat_sticker_dari_input(self, instance: Any) -> None:
        # If there's text in input, use it; else use last assistant message
        teks = self.chat_input.text.strip()
        if not teks:
            teks = self.assistant_history[-1] if getattr(self, 'assistant_history', None) and len(self.assistant_history) > 0 else "Sticker dari AI"

        path = generate_sticker(teks)
        if path:
            img_bubble = ChatBubble(teks, dari_user=False, image_path=path)
            self.chat_container.add_widget(img_bubble)
            Clock.schedule_once(lambda dt: setattr(self.chat_scroll, 'scroll_y', 0), 0.05)

    def _buat_local_ai_sticker(self, instance: Any) -> None:
        teks = self.chat_input.text.strip()
        if not teks:
            teks = self.assistant_history[-1] if getattr(self, 'assistant_history', None) and len(self.assistant_history) > 0 else "Cute robot sticker"

        path = generate_local_sticker_from_prompt(teks)
        if path:
            img_bubble = ChatBubble(teks, dari_user=False, image_path=path)
            self.chat_container.add_widget(img_bubble)
        else:
            self._tambah_bubble(
                "AI sticker lokal tidak tersedia. Pastikan diffusers, torch, dan model Stable Diffusion sudah terpasang.",
                dari_user=False
            )
        Clock.schedule_once(lambda dt: setattr(self.chat_scroll, 'scroll_y', 0), 0.05)

    def _buat_hosted_ai_sticker(self, instance: Any) -> None:
        teks = self.chat_input.text.strip()
        if not teks:
            teks = self.assistant_history[-1] if getattr(self, 'assistant_history', None) and len(self.assistant_history) > 0 else "Cute robot sticker"

        path = generate_ai_sticker_from_prompt(teks)
        if path:
            img_bubble = ChatBubble(teks, dari_user=False, image_path=path)
            self.chat_container.add_widget(img_bubble)
        else:
            self._tambah_bubble(
                "Hosted AI sticker tidak tersedia. Pastikan OPENAI_API_KEY atau STABILITY_API_KEY sudah disetel.",
                dari_user=False
            )
        Clock.schedule_once(lambda dt: setattr(self.chat_scroll, 'scroll_y', 0), 0.05)

    def proses_pesan(self, pesan: str) -> None:
        pesan = pesan.strip()
        if not pesan:
            return
        self._tambah_bubble(pesan, dari_user=True)
        self.memory.catat("pesan_user", pesan)
        self.set_status_robot('thinking')

        bubble_mengetik = self._tambah_bubble("•••", dari_user=False)
        Clock.schedule_once(lambda dt: self._balas_sebagai_kivy(pesan, bubble_mengetik), 0.4)

    def _jawab_instan(self, balasan: str, bubble_mengetik: ChatBubble) -> None:
        self._hapus_bubble(bubble_mengetik)
        self._tambah_bubble(balasan, dari_user=False)
        self.panggil_suara_unik(balasan)
        self.memory.catat("balasan_kivy", balasan)

    def _balas_sebagai_kivy(self, pesan: str, bubble_mengetik: ChatBubble) -> None:
        teks_lower = pesan.lower().strip()

        if teks_lower.startswith("buka "):
            self._hapus_bubble(bubble_mengetik)
            nama_app = teks_lower.replace("buka ", "", 1).strip()
            self.buka_aplikasi_by_nama(nama_app)
            return

        if any(k in teks_lower for k in ["harga", "bitcoin", "crypto", "kripto", "pasar", "saham"]):
            balasan = self.ringkasan_pasar_chat
            self._jawab_instan(balasan, bubble_mengetik)
            return

        if any(k in teks_lower for k in ["trending", "viral", "berita", "rame", "ramai"]):
            balasan = "Cek kartu Video & Berita Trending di bawah ya Bos!"
            self._jawab_instan(balasan, bubble_mengetik)
            return

        if teks_lower.startswith("hitung"):
            ekspresi = pesan[6:].strip(" :")
            if not ekspresi:
                balasan = "Ketik soalnya juga ya Bos, misal: 'hitung 25*4-10'"
            else:
                hasil = self._kalkulator_aman(ekspresi)
                balasan = f"Hasilnya: {hasil}" if hasil is not None else "Maaf Bos, aku gak bisa hitung itu -- pastikan cuma angka dan +-*/()."
            self._jawab_instan(balasan, bubble_mengetik)
            return

        if teks_lower.startswith("ingatkan") or teks_lower.startswith("catat pengingat"):
            isi = pesan.split(" ", 1)[1].strip() if " " in pesan else ""
            if isi:
                self.memory.tambah_pengingat(isi)
                balasan = f"Oke Bos, aku catat pengingatnya: \"{isi}\""
            else:
                balasan = "Mau diingatkan soal apa, Bos? Contoh: 'ingatkan bayar listrik besok'"
            self._jawab_instan(balasan, bubble_mengetik)
            return

        if "lihat pengingat" in teks_lower or teks_lower == "pengingat" or "apa pengingatku" in teks_lower:
            daftar = self.memory.daftar_pengingat()
            if daftar:
                balasan = "📋 Pengingat kamu:\n" + "\n".join(f"• {p['teks']} ({p['waktu']})" for p in daftar[-10:])
            else:
                balasan = "Belum ada pengingat, Bos. Coba ketik 'ingatkan <sesuatu>'."
            self._jawab_instan(balasan, bubble_mengetik)
            return

        if "hapus pengingat" in teks_lower or "bersihkan pengingat" in teks_lower:
            self.memory.hapus_semua_pengingat()
            self._jawab_instan("Semua pengingat sudah dihapus, Bos.", bubble_mengetik)
            return

        if teks_lower.startswith("catat "):
            isi = pesan[6:].strip()
            if isi:
                self.memory.tambah_catatan(isi)
                balasan = f"Dicatat, Bos: \"{isi}\""
            else:
                balasan = "Mau catat apa, Bos? Contoh: 'catat beli kado ulang tahun ibu'"
            self._jawab_instan(balasan, bubble_mengetik)
            return

        if "lihat catatan" in teks_lower or teks_lower == "catatan":
            daftar = self.memory.daftar_catatan()
            if daftar:
                balasan = "📝 Catatan kamu:\n" + "\n".join(f"• {c['teks']}" for c in daftar[-10:])
            else:
                balasan = "Belum ada catatan, Bos. Coba ketik 'catat <sesuatu>'."
            self._jawab_instan(balasan, bubble_mengetik)
            return

        if teks_lower.startswith("cuaca"):
            kota = pesan[5:].strip() or "Jakarta"
            threading.Thread(target=self._cek_cuaca, args=(kota, bubble_mengetik), daemon=True).start()
            return

        threading.Thread(target=self._tanya_ai_groq, args=(pesan, bubble_mengetik), daemon=True).start()

    def _hapus_bubble(self, bubble: ChatBubble) -> None:
        if bubble and bubble.parent:
            self.chat_container.remove_widget(bubble)

    _OPERATOR_AMAN = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
        ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv,
    }

    def _kalkulator_aman(self, ekspresi: str) -> Optional[str]:
        try:
            node = ast.parse(ekspresi, mode='eval').body
            hasil = self._evaluasi_node(node)
            if isinstance(hasil, float) and hasil.is_integer():
                hasil = int(hasil)
            return str(hasil)
        except Exception:
            return None

    def _evaluasi_node(self, node: Any) -> Any:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in self._OPERATOR_AMAN:
            return self._OPERATOR_AMAN[type(node.op)](self._evaluasi_node(node.left), self._evaluasi_node(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._OPERATOR_AMAN:
            return self._OPERATOR_AMAN[type(node.op)](self._evaluasi_node(node.operand))
        raise ValueError("Ekspresi tidak didukung")

    def _cek_cuaca(self, kota: str, bubble_mengetik: ChatBubble) -> None:
        balasan = f"Gagal mengambil cuaca untuk {kota}."
        try:
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={kota}&count=1&language=id"
            geo_res = requests.get(geo_url, timeout=8).json()
            hasil_geo = geo_res.get("results")
            if not hasil_geo:
                balasan = f"Bos, aku gak nemu kota '{kota}'. Coba nama kota lain."
            else:
                lat = hasil_geo[0]["latitude"]
                lon = hasil_geo[0]["longitude"]
                nama_resmi = hasil_geo[0].get("name", kota)

                cuaca_url = (
                    f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                    "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
                )
                cuaca_res = requests.get(cuaca_url, timeout=8).json()
                current = cuaca_res.get("current", {})
                suhu = current.get("temperature_2m")
                kelembapan = current.get("relative_humidity_2m")
                angin = current.get("wind_speed_10m")
                kode = current.get("weather_code")

                deskripsi = self._deskripsi_kode_cuaca(kode)
                balasan = (
                    f"🌤️ Cuaca di {nama_resmi} sekarang:\n"
                    f"{deskripsi}, {suhu}°C\n"
                    f"Kelembapan: {kelembapan}%  |  Angin: {angin} km/jam"
                )
        except Exception as e:
            balasan = f"Gagal mengambil data cuaca: {e}"

        Clock.schedule_once(lambda dt: self._jawab_instan(balasan, bubble_mengetik), 0)

    @staticmethod
    def _deskripsi_kode_cuaca(kode: Optional[int]) -> str:
        peta = {
            0: "☀️ Cerah", 1: "🌤️ Cerah berawan sedikit", 2: "⛅ Berawan sebagian", 3: "☁️ Mendung",
            45: "🌫️ Berkabut", 48: "🌫️ Kabut es",
            51: "🌦️ Gerimis ringan", 53: "🌦️ Gerimis sedang", 55: "🌧️ Gerimis lebat",
            61: "🌧️ Hujan ringan", 63: "🌧️ Hujan sedang", 65: "🌧️ Hujan lebat",
            80: "🌦️ Hujan sebentar", 81: "🌧️ Hujan deras sebentar", 82: "⛈️ Hujan sangat deras",
            95: "⛈️ Badai petir", 96: "⛈️ Badai petir + hujan es", 99: "⛈️ Badai petir hebat",
        }
        return peta.get(kode if kode is not None else -1, "🌡️ Kondisi tidak diketahui")

    def _tanya_ai_groq(self, pesan: str, bubble_mengetik: ChatBubble) -> None:
        """
        Pakai Groq (https://console.groq.com) sebagai penyedia AI.
        Dipilih karena autentikasinya sederhana (cukup Bearer token biasa,
        tanpa drama restriction/OAuth seperti Google), key langsung aktif
        begitu dibuat, gratis, dan responsnya sangat cepat.
        """
        api_key = GROQ_API_KEY.strip()

        if not api_key or "MASUKKAN" in api_key.upper():
            balasan = (
                "Bos, API Key Groq belum diisi. Caranya gampang:\n"
                "1. Buka https://console.groq.com/keys\n"
                "2. Login/daftar pakai akun Google (gratis, tanpa kartu kredit)\n"
                "3. Klik 'Create API Key', copy key-nya (diawali 'gsk_')\n"
                "4. Copy 'secrets.env.example' jadi 'secrets.env', isi "
                "GROQ_API_KEY=key_kamu di situ (untuk PC), atau isi lewat "
                "GitHub Secrets kalau build via GitHub Actions"
            )
        elif not api_key.startswith("gsk_"):
            balasan = (
                "Bos, format API Key Groq kelihatannya salah (harus diawali "
                "'gsk_'). Cek lagi key-nya di https://console.groq.com/keys"
            )
        else:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                }
                body = {
                    "model": "openai/gpt-oss-120b",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                f"Kamu adalah {AI_NAME}, asisten AI pribadi yang ramah, santai, dan cerdas. "
                                "Jawab singkat, padat, berguna (maksimal 2-4 kalimat kecuali diminta detail), "
                                "gunakan Bahasa Indonesia, dan sesekali panggil pengguna dengan kata 'Bos'."
                            ),
                        },
                        {"role": "user", "content": pesan},
                    ],
                    "max_tokens": 500,
                    "temperature": 0.7,
                }
                res = requests.post(url, json=body, headers=headers, timeout=25)
                data = res.json()

                if "choices" in data and len(data["choices"]) > 0:
                    balasan = data["choices"][0].get("message", {}).get("content", "").strip()
                    if not balasan:
                        balasan = "Maaf Bos, balasan dari AI kosong. Coba tanya ulang."
                elif "error" in data:
                    err = data["error"]
                    err_msg = err.get("message", "Error tidak diketahui")
                    kode = res.status_code
                    if kode == 401:
                        balasan = (
                            "Groq Error (401): API Key tidak valid. Cek/buat ulang di "
                            "https://console.groq.com/keys lalu update di file secrets.env "
                            "(PC) atau GitHub Secrets (build cloud)."
                        )
                    elif kode == 429:
                        balasan = "Groq Error (429): Kuota/rate limit terlampaui, coba lagi sebentar Bos."
                    elif kode == 404:
                        balasan = (
                            f"Groq Error (404): Model tidak ditemukan/sudah dipensiunkan. "
                            "Cek daftar model terbaru di https://console.groq.com/docs/models "
                            "lalu update nilai 'model' di main.py."
                        )
                    else:
                        balasan = f"Groq Error ({kode}): {err_msg}"
                else:
                    balasan = f"Maaf Bos, server AI sedang tidak merespon dengan benar. (raw: {str(data)[:150]})"
            except requests.exceptions.Timeout:
                balasan = "Gagal terhubung ke AI: koneksi timeout, coba lagi Bos."
            except Exception as e:
                balasan = f"Gagal terhubung ke AI: {str(e)}"

        Clock.schedule_once(lambda dt: self._jawab_instan(balasan, bubble_mengetik), 0)

    def init_android_tts(self) -> None:
        try:
            listener = TTSListener(self._on_tts_ready)
            self.tts = TextToSpeech(activity, listener)
            self._tts_listener = listener
        except Exception as e:
            print(f"Gagal memuat Android TTS: {str(e)}")

    def _on_tts_ready(self, status: int) -> None:
        if self.tts is None:
            return
        if status == TextToSpeech.SUCCESS:
            try:
                self.tts.setLanguage(Locale('id', 'ID'))
            except Exception:
                self.tts.setLanguage(Locale.US)
            self.tts.setPitch(1.6)
            self.tts.setSpeechRate(1.0)

    def panggil_suara_unik(self, teks: str) -> None:
        self.set_status_robot('speaking')
        if platform == 'android' and self.tts:
            self.tts.speak(teks, TextToSpeech.QUEUE_FLUSH, None, None)
        else:
            print(f"[PC Suara]: {teks}")
        durasi_perkiraan = max(1.2, min(len(teks) * 0.05, 4.0))
        Clock.schedule_once(lambda dt: self.set_status_robot('idle'), durasi_perkiraan)

    def sambut_bos(self, dt: Any) -> None:
        sapaan = f"Halo Bos! Aku {AI_NAME}, AI Asisten siap membantumu. 👋"
        self._tambah_bubble(sapaan, dari_user=False)
        self.panggil_suara_unik(f"Halo Bos, aku {AI_NAME}")
        self.muat_informasi_hangat()
        self.muat_trending_video()
        self.muat_trending_berita()

    def mulai_dengar_perintah(self, instance: Any) -> None:
        if platform != 'android':
            self.status_label.text = "[PC Mode] Voice command hanya di Android."
            return

        if not self._has_audio_permission():
            self._request_audio_permission()
            return

        if not SpeechRecognizer.isRecognitionAvailable(activity):
            self.status_label.text = "Speech recognizer tidak tersedia."
            return

        self.set_status_robot('listening')
        try:
            recognizer = SpeechRecognizer.createSpeechRecognizer(activity)
            listener = RecognitionListenerImpl(on_result=self._on_voice_result, on_error=self._on_voice_error)
            self._recognition_listener = listener
            recognizer.setRecognitionListener(listener)

            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "id-ID")
            recognizer.startListening(intent)
            self._recognizer = recognizer
        except Exception as e:
            self.status_label.text = f"Error Mic: {str(e)}"
            self.set_status_robot('idle')

    def _on_voice_result(self, teks: str) -> None:
        Clock.schedule_once(lambda dt: self.proses_pesan(teks), 0)

    def _on_voice_error(self, pesan: str) -> None:
        Clock.schedule_once(lambda dt: self.set_status_robot('idle'), 0)

    def muat_daftar_aplikasi_terinstall(self) -> None:
        try:
            pm = activity.getPackageManager()
            PackageManager = autoclass('android.content.pm.PackageManager')
            apps = pm.getInstalledApplications(PackageManager.GET_META_DATA)
            for i in range(apps.size()):
                app_info = apps.get(i)
                try:
                    label = str(pm.getApplicationLabel(app_info))
                    self.daftar_app[label.lower()] = str(app_info.packageName)
                except Exception:
                    continue
        except Exception as e:
            print(f"Gagal muat daftar aplikasi: {e}")

    def buka_aplikasi_by_nama(self, nama_app: str) -> None:
        target_package: Optional[str] = None
        for label, package in self.daftar_app.items():
            if nama_app in label or label in nama_app:
                target_package = package
                break

        if target_package:
            self.buka_aplikasi_by_package(target_package, nama_tampilan=nama_app)
        else:
            balasan = f"Maaf Bos, aplikasi '{nama_app}' tidak ditemukan."
            self._tambah_bubble(balasan, dari_user=False)
            self.panggil_suara_unik(balasan)

    def buka_aplikasi_by_package(self, package_target: str, nama_tampilan: Optional[str] = None) -> None:
        label = nama_tampilan or package_target
        if platform == 'android':
            try:
                pm = activity.getPackageManager()
                intent = pm.getLaunchIntentForPackage(package_target)
                if intent:
                    activity.startActivity(intent)
                    balasan = f"Membuka {label}..."
                else:
                    balasan = f"Aplikasi {label} tidak terpasang, membuka Play Store..."
                    play_intent = Intent(Intent.ACTION_VIEW, Uri.parse(f"market://details?id={package_target}"))
                    activity.startActivity(play_intent)
            except Exception as e:
                balasan = f"Gagal membuka app: {str(e)}"
        else:
            balasan = f"[PC Mode] Buka {label}"

        self._tambah_bubble(balasan, dari_user=False)
        self.panggil_suara_unik(balasan)

    def muat_informasi_hangat(self) -> None:
        threading.Thread(target=self._fetch_market_dashboard, daemon=True).start()

    def _fetch_market_dashboard(self) -> None:
        """Ambil data global (kap pasar & volume) + daftar top koin dari CoinGecko."""
        global_data: Dict[str, Any] = {}
        daftar_koin: List[Dict[str, Any]] = []

        try:
            global_res = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
            global_data = global_res.get("data", {})
        except Exception as e:
            print(f"Gagal memuat data global pasar: {e}")

        try:
            markets_url = (
                "https://api.coingecko.com/api/v3/coins/markets"
                "?vs_currency=usd&order=market_cap_desc&per_page=10&page=1"
                "&price_change_percentage=24h&sparkline=true"
            )
            hasil = requests.get(markets_url, timeout=10).json()
            if isinstance(hasil, list):
                daftar_koin = hasil
        except Exception as e:
            print(f"Gagal memuat daftar top koin: {e}")

        Clock.schedule_once(lambda dt: self._tampilkan_market_dashboard(global_data, daftar_koin), 0)

    @staticmethod
    def _format_usd(nilai: float, angka_besar: bool = False) -> str:
        """Format angka USD gaya Indonesia: ribuan pakai titik, desimal pakai koma."""
        try:
            if angka_besar:
                teks = f"{nilai:,.0f}".replace(",", ".")
                return f"US${teks}"
            if nilai >= 1:
                teks = f"{nilai:,.2f}"
            elif nilai >= 0.01:
                teks = f"{nilai:,.4f}"
            else:
                teks = f"{nilai:,.6f}"
            teks = teks.replace(",", "#").replace(".", ",").replace("#", ".")
            return f"US${teks}"
        except Exception:
            return "US$-"

    def _tampilkan_market_dashboard(self, global_data: Dict[str, Any], daftar_koin: List[Dict[str, Any]]) -> None:
        # --- Kap Pasar & Volume 24 Jam ---
        try:
            total_cap = global_data.get("total_market_cap", {}).get("usd")
            total_vol = global_data.get("total_volume", {}).get("usd")
            perubahan_cap = global_data.get("market_cap_change_percentage_24h_usd")

            if total_cap is not None:
                self.stat_cap.set_nilai(self._format_usd(total_cap, angka_besar=True), perubahan_cap)
            else:
                self.stat_cap.set_nilai("Tidak tersedia", None)

            if total_vol is not None:
                self.stat_volume.set_nilai(self._format_usd(total_vol, angka_besar=True), None)
            else:
                self.stat_volume.set_nilai("Tidak tersedia", None)
        except Exception as e:
            print(f"Gagal render statistik pasar: {e}")

        # --- Daftar Top Koin ---
        self.list_koin.clear_widgets()
        baris_ringkasan: List[str] = []

        if daftar_koin:
            for koin in daftar_koin:
                simbol = koin.get("symbol", "?")
                nama = koin.get("name", "?")
                harga = koin.get("current_price", 0) or 0
                persen = koin.get("price_change_percentage_24h") or 0.0
                harga_teks = self._format_usd(harga)
                sparkline = koin.get("sparkline_in_7d", {}).get("price", []) or []
                image_url = koin.get("image", "") or ""
                self.list_koin.add_widget(CoinCard(simbol, nama, harga_teks, persen, sparkline, image_url))
                baris_ringkasan.append(f"{simbol.upper()}: {harga_teks} ({persen:+.1f}%)")
        else:
            self.list_koin.add_widget(Label(
                text="Data koin tidak tersedia saat ini.", font_size='11sp',
                color=(0.8, 0.8, 0.85, 1), size_hint=(1, None), height=dp(30)
            ))

        # Simpan ringkasan teks untuk dijawab lewat chat (kata kunci: harga/crypto/dst)
        if baris_ringkasan:
            self.ringkasan_pasar_chat = "📊 RINGKASAN PASAR KRIPTO\n" + "\n".join(f"• {b}" for b in baris_ringkasan)
        else:
            self.ringkasan_pasar_chat = "Data pasar belum termuat, coba lagi sebentar Bos."

        # Ticker ringkas untuk ditampilkan saat card dalam mode tertutup
        if daftar_koin:
            btc = next((k for k in daftar_koin if k.get("symbol") == "btc"), daftar_koin[0])
            persen_btc = btc.get("price_change_percentage_24h") or 0.0
            panah = "▲" if persen_btc >= 0 else "▼"
            self.label_ticker_pasar.text = (
                f"BTC {self._format_usd(btc.get('current_price', 0) or 0)} {panah}{abs(persen_btc):.1f}%"
            )

        self._update_tinggi_card_pasar()

    def muat_trending_video(self) -> None:
        threading.Thread(target=self._fetch_trending_video, daemon=True).start()

    def _fetch_trending_video(self) -> None:
        api_key = YOUTUBE_API_KEY.strip()
        if not api_key:
            return
        try:
            url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&chart=mostPopular&regionCode=ID&maxResults=15&key={api_key}"
            res = requests.get(url, timeout=10)
            data = res.json()

            items = data.get("items", [])
            videos = []
            for item in items:
                snippet = item.get("snippet", {})
                video_id = item.get("id", "")
                thumbnails = snippet.get("thumbnails", {})
                # Ambil kualitas terbaik yang tersedia, fallback berjenjang
                thumbnail_url = (
                    thumbnails.get("high", {}).get("url")
                    or thumbnails.get("medium", {}).get("url")
                    or thumbnails.get("default", {}).get("url")
                    or ""
                )

                if not thumbnail_url and video_id:
                    thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                videos.append({
                    "judul": snippet.get("title", "Video YouTube"),
                    "thumbnail_url": thumbnail_url,
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}"
                })
            Clock.schedule_once(lambda dt: self._tampilkan_trending_video(videos), 0)
        except Exception as e:
            print(f"Gagal memuat trending video: {e}")

    def _tampilkan_trending_video(self, videos: List[Dict[str, Any]]) -> None:
        self.grid_trending_video.clear_widgets()
        if not videos:
            return

        for v in videos:
            kartu = Card(bg_color=WARNA_CARD_VIDEO, radius=18, orientation='vertical',
                         size_hint=(None, None), width=dp(162), height=dp(210), spacing=dp(8), padding=(dp(8), dp(8)))

            thumbnail_url = v.get("thumbnail_url") or ""
            play_target = v.get("url", "")

            thumb_wrap = ClickableCardFloat(
                bg_color=(0.08, 0.10, 0.18, 1), radius=18,
                size_hint=(1, None), height=dp(134),
                on_press=lambda url=play_target: self._handle_video_play(url)
            )
            if thumbnail_url:
                thumb = buat_async_image_retry(
                    thumbnail_url, size_hint=(1, 1), allow_stretch=True,
                    keep_ratio=True, anim_delay=-1
                )
                thumb_wrap.add_widget(thumb)
            else:
                thumb_wrap.add_widget(Label(
                    text="Preview tidak tersedia", font_size='11sp', color=(0.88, 0.88, 0.92, 1),
                    halign='center', valign='middle', size_hint=(1, 1)
                ))

            ikon_play = Label(
                text="▶", font_size='26sp', color=(1, 1, 1, 0.88),
                size_hint=(None, None), size=(dp(40), dp(40)),
                pos_hint={'center_x': 0.5, 'center_y': 0.5}
            )
            thumb_wrap.add_widget(ikon_play)

            judul_label = Label(
                text=v["judul"], font_size='11sp', color=(0.96, 0.96, 0.98, 1),
                size_hint=(1, None), height=dp(50), halign='left', valign='top',
                shorten=True, shorten_from='right'
            )
            judul_label.bind(size=lambda s, w, lbl=judul_label: setattr(lbl, 'text_size', w))

            kartu.add_widget(thumb_wrap)
            kartu.add_widget(judul_label)
            self.grid_trending_video.add_widget(kartu)

    def _handle_video_play(self, url: str) -> None:
        threading.Thread(target=self._extract_and_open_video, args=(url,), daemon=True).start()

    def _extract_and_open_video(self, url: str) -> None:
        sumber_langsung = self._get_direct_video_source(url)
        if sumber_langsung:
            Clock.schedule_once(lambda dt: self._tampilkan_video_dalam_aplikasi(sumber_langsung), 0)
        else:
            Clock.schedule_once(lambda dt: self.buka_link_eksternal(url), 0)

    def _tampilkan_video_dalam_aplikasi(self, sumber: str) -> None:
        if self.video_modal is not None:
            parent = self.video_modal.parent
            if parent is not None:
                parent.remove_widget(self.video_modal)
            self.video_modal = None

        self.video_modal = VideoModal(source=sumber, on_close=self._tutup_video_modal)
        target_parent = self.parent if isinstance(self.parent, FloatLayout) else self
        if target_parent is not None:
            target_parent.add_widget(self.video_modal)

    def _tutup_video_modal(self) -> None:
        if self.video_modal is not None:
            parent = self.video_modal.parent
            if parent is not None:
                parent.remove_widget(self.video_modal)
            self.video_modal = None

    def _get_direct_video_source(self, youtube_url: str) -> Optional[str]:
        try:
            from yt_dlp import YoutubeDL
            options: Any = {
                'quiet': True,
                'skip_download': True,
                'format': 'best[ext=mp4]/best',
                'nocheckcertificate': True,
            }
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                if isinstance(info, dict):
                    url = info.get('url')
                    if url:
                        return url
                    for fmt in info.get('formats') or []:
                        if fmt.get('ext') in ('mp4', 'webm') and fmt.get('protocol', '').startswith('https'):
                            return fmt.get('url')
        except Exception as e:
            print(f"Tidak bisa ambil stream langsung: {e}")
        return None

    def buka_link_eksternal(self, url: str) -> None:
        if platform == 'android':
            try:
                browser_intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                activity.startActivity(browser_intent)
                return
            except Exception:
                pass
        webbrowser.open(url)

    def muat_trending_berita(self) -> None:
        threading.Thread(target=self._fetch_trending_berita, daemon=True).start()

    @staticmethod
    def _local_tag(tag: str) -> str:
        return tag.split('}')[-1] if '}' in tag else tag

    def _fetch_trending_berita(self) -> None:
        hasil: List[Dict[str, str]] = []
        try:
            url = "https://trends.google.com/trending/rss?geo=ID"
            res = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            root = ET.fromstring(res.content)

            for item in root.iter('item'):
                data = {"judul": "", "gambar": "", "ringkasan": "", "url": ""}
                for child in item:
                    tag = self._local_tag(child.tag)
                    if tag == 'title':
                        data["judul"] = (child.text or "").strip()
                    elif tag == 'link':
                        data["url"] = (child.text or "").strip()
                    elif tag in ('picture', 'thumbnail', 'content'):
                        data["gambar"] = child.attrib.get('url') or (child.text or "").strip()
                    elif tag == 'news_item' and not data["ringkasan"]:
                        for sub in child:
                            subtag = self._local_tag(sub.tag)
                            if subtag == 'news_item_snippet':
                                data["ringkasan"] = (sub.text or "").strip()
                            elif subtag == 'news_item_title' and not data["judul"]:
                                data["judul"] = (sub.text or "").strip()
                            elif subtag == 'news_item_url' and not data["url"]:
                                data["url"] = (sub.text or "").strip()
                            elif subtag in ('news_item_picture', 'thumbnail', 'content') and not data["gambar"]:
                                data["gambar"] = sub.attrib.get('url') or (sub.text or "").strip()
                if not data["gambar"]:
                    for sub in item.iter():
                        subtag = self._local_tag(sub.tag)
                        if subtag in ('thumbnail', 'content', 'media_thumbnail', 'media_content'):
                            data["gambar"] = sub.attrib.get('url') or (sub.text or "").strip()
                            if data["gambar"]:
                                break
                if data["judul"]:
                    hasil.append(data)
        except Exception:
            pass

        Clock.schedule_once(lambda dt: self._tampilkan_trending_berita(hasil[:6]), 0)

    def _tampilkan_trending_berita(self, daftar: List[Dict[str, str]]) -> None:
        self.list_berita.clear_widgets()
        if not daftar:
            self.list_berita.add_widget(Label(text="Berita tidak tersedia.", font_size='11sp', color=(0.8, 0.8, 0.8, 1)))
            return

        for d in daftar:
            kartu = NewsCard(
                judul=d["judul"], ringkasan=d["ringkasan"] or "Klik untuk membaca selengkapnya...",
                gambar=d["gambar"], url=d["url"], on_tap=self.buka_link_eksternal
            )
            self.list_berita.add_widget(kartu)

        cols = max(1, self.list_berita.cols)
        jumlah_baris = (len(daftar) + cols - 1) // cols
        self.card_berita.height = dp(24) + jumlah_baris * dp(84) + dp(16)


class AplikasiAI(App):
    def build(self) -> FloatLayout:
        self.title = AI_NAME
        root = FloatLayout()
        content = RobotAIVector(size_hint=(1, 1))
        root.add_widget(content)
        return root


if __name__ == '__main__':
    AplikasiAI().run()