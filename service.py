# ==============================================================================
# FILE: service.py
# DESKRIPSI: Foreground Service yang menampilkan ikon robot kecil mengambang
#            di atas semua aplikasi lain (seperti chat-head Messenger).
#
# CATATAN PENTING (baca sebelum pakai):
# - Ini FITUR TINGKAT LANJUT. Kivy tidak mendukung overlay sistem secara
#   resmi, jadi di sini kita akses langsung API Android (WindowManager) lewat
#   Pyjnius. Ini butuh testing & kemungkinan debugging langsung di HP asli.
# - User HARUS memberi izin "Tampil di atas aplikasi lain" secara manual
#   lewat Settings, karena SYSTEM_ALERT_WINDOW tidak bisa di-grant otomatis
#   di Android 6+ (harus dari halaman Settings khusus).
# - Service ini didaftarkan di buildozer.spec bagian "services".
# ==============================================================================

from jnius import autoclass, PythonJavaClass, java_method

PythonService = autoclass('org.kivy.android.PythonService')
service = PythonService.mService

WindowManager = autoclass('android.view.WindowManager')
LayoutParams = autoclass('android.view.WindowManager$LayoutParams')
PixelFormat = autoclass('android.graphics.PixelFormat')
ImageView = autoclass('android.widget.ImageView')
Gravity = autoclass('android.view.Gravity')
Build = autoclass('android.os.Build')
MotionEvent = autoclass('android.view.MotionEvent')
Intent = autoclass('android.content.Intent')
PythonActivity = autoclass('org.kivy.android.PythonActivity')

window_manager = service.getSystemService(service.WINDOW_SERVICE)

# Tipe overlay window beda antara Android versi lama & baru (8.0+)
if Build.VERSION.SDK_INT >= 26:
    layout_type = LayoutParams.TYPE_APPLICATION_OVERLAY
else:
    layout_type = LayoutParams.TYPE_PHONE

params = LayoutParams(
    LayoutParams.WRAP_CONTENT,
    LayoutParams.WRAP_CONTENT,
    layout_type,
    LayoutParams.FLAG_NOT_FOCUSABLE | LayoutParams.FLAG_LAYOUT_IN_SCREEN,
    PixelFormat.TRANSLUCENT
)
params.gravity = Gravity.TOP | Gravity.START
params.x = 0
params.y = 200


class TouchListener(PythonJavaClass):
    """Menangani sentuhan pada ikon robot: geser (drag) untuk pindah posisi,
    tap singkat untuk membuka kembali aplikasi utama."""
    __javainterfaces__ = ['android/view/View$OnTouchListener']
    __javacontext__ = 'app'

    def __init__(self, view, wm, params):
        super().__init__()
        self.view = view
        self.wm = wm
        self.params = params
        self.initial_x = 0
        self.initial_y = 0
        self.touch_x = 0
        self.touch_y = 0

    @java_method('(Landroid/view/View;Landroid/view/MotionEvent;)Z')
    def onTouch(self, view, event):
        action = event.getAction()
        if action == MotionEvent.ACTION_DOWN:
            self.initial_x = self.params.x
            self.initial_y = self.params.y
            self.touch_x = event.getRawX()
            self.touch_y = event.getRawY()
            return True
        elif action == MotionEvent.ACTION_MOVE:
            self.params.x = int(self.initial_x + (event.getRawX() - self.touch_x))
            self.params.y = int(self.initial_y + (event.getRawY() - self.touch_y))
            self.wm.updateViewLayout(self.view, self.params)
            return True
        elif action == MotionEvent.ACTION_UP:
            # Kalau posisi hampir tidak bergeser, anggap ini "tap" -> buka app utama
            jarak = abs(event.getRawX() - self.touch_x) + abs(event.getRawY() - self.touch_y)
            if jarak < 15:
                buka_app_utama()
            return True
        return False


def buka_app_utama():
    intent = Intent(service, PythonActivity)
    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    service.startActivity(intent)


def tampilkan_overlay():
    icon_view = ImageView(service)
    # Ganti dengan drawable robot kecil yang sudah dibundel ke folder res/drawable
    # (lihat catatan di README soal cara menambahkan drawable custom)
    icon_view.setImageResource(service.getApplicationInfo().icon)

    listener = TouchListener(icon_view, window_manager, params)
    icon_view.setOnTouchListener(listener)

    window_manager.addView(icon_view, params)
    return icon_view, listener  # simpan referensi supaya tidak di-GC


# Jalankan begitu service dimulai
_overlay_refs = tampilkan_overlay()