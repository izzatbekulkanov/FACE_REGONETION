# core/apps.py
from django.apps import AppConfig
import threading

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        from core.live import get_camera_instance

        def start_camera_thread():
            try:
                cam = get_camera_instance()
                if cam:
                    print(f"🚀 Tanlangan kamera ishga tushdi: {cam.camera.name}")
            except Exception as e:
                print(f"❌ Kamera fon rejimda ishga tushmadi: {e}")

        if not hasattr(self, 'camera_thread_started'):
            self.camera_thread_started = True
            threading.Thread(target=start_camera_thread, daemon=True).start()
