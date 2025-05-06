# core/apps.py
from django.apps import AppConfig
import threading

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """
        Django start bo‘lganda tanlangan kamerani tekshiradi.
        Agar mavjud bo‘lsa — konsolga chiqadi.
        """
        from core.recognition import get_selected_camera  # 🔥 Endi recognition dan chaqiriladi

        def start_camera_check():
            try:
                camera = get_selected_camera()
                if camera:
                    print(f"🚀 Tanlangan kamera topildi: {camera.name} ({camera.type.upper()})")
                else:
                    print("⚠️ Faol va tanlangan kamera mavjud emas.")
            except Exception as e:
                print(f"❌ Kamera tekshiruvda xatolik: {e}")

        # Bir martalik ishga tushirish
        if not hasattr(self, '_camera_checked'):
            self._camera_checked = True
            threading.Thread(target=start_camera_check, daemon=True).start()
