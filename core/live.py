import logging
from core.models import Camera
from core.recognition import WebSocketStream

logger = logging.getLogger(__name__)

camera_instance = None  # Global kamera obyekti

def get_camera_instance():
    """
    Faol va tanlangan PTZ kamerani qaytaradi yoki yangisini yaratadi.
    """
    global camera_instance
    if camera_instance is None or not getattr(camera_instance, 'running', False):
        active_camera = Camera.objects.filter(is_active=True, selected=True, type='ptz').first()
        if active_camera:
            try:
                camera_instance = WebSocketStream(active_camera)
                logger.info(f"📸 PTZ kamera ishga tushdi: {active_camera.name} ({active_camera.source})")
                print(f"📸 PTZ kamera ishga tushdi: {active_camera.name}")
            except Exception as e:
                logger.error(f"❌ Kamera yuklashda xatolik: {str(e)}")
                print(f"❌ Kamera yuklashda xatolik: {e}")
                camera_instance = None
        else:
            logger.warning("⚠️ Tanlangan va faol PTZ kamera topilmadi.")
            print("⚠️ Tanlangan va faol PTZ kamera topilmadi.")
    return camera_instance

def get_current_camera():
    """
    Joriy kamera modelini qaytaradi.
    """
    return camera_instance.camera if camera_instance else None