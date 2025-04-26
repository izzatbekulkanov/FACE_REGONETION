# core/live.py
import subprocess
import re
from core.camera import VideoCamera
from core.models import Camera

camera_instance = None  # Global kamera obyekti

def get_index_from_hardware_path(hardware_path):
    """
    USB hardware_path asosida /dev/videoX indexini qaytaradi.
    """
    result = subprocess.run(['v4l2-ctl', '--list-devices'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lines = result.stdout.split('\n')

    current_path = None
    for i, line in enumerate(lines):
        if not line.startswith('\t'):
            match = re.search(r'\((usb-[^)]+)\)', line)
            if match:
                current_path = match.group(1)
        elif current_path == hardware_path:
            video_match = re.search(r'/dev/video(\d+)', line.strip())
            if video_match:
                return int(video_match.group(1))
    return None


def get_camera_instance():
    global camera_instance

    if camera_instance is None or not getattr(camera_instance, 'running', False):
        active_camera = Camera.objects.filter(is_active=True, selected=True).first()
        if active_camera:
            if active_camera.type == "usb":
                index = get_index_from_hardware_path(active_camera.source)
                if index is not None:
                    active_camera.source = str(index)  # Yangilangan indexni source sifatida uzatamiz
                    try:
                        camera_instance = VideoCamera(active_camera)
                        print(f"📸 USB kamera (hardware_path asosida): {active_camera.name} (/dev/video{index})")
                    except Exception as e:
                        print(f"❌ Kamera ochilmadi: {e}")
                        camera_instance = None
                else:
                    print(f"❌ USB kamera hardware_path topilmadi: {active_camera.source}")
            else:
                try:
                    camera_instance = VideoCamera(active_camera)
                    print(f"📸 IP/PTZ kamera ishga tushdi: {active_camera.name}")
                except Exception as e:
                    print(f"❌ Kamera yuklashda xatolik: {e}")
                    camera_instance = None
        else:
            print("⚠️ Tanlangan va faol kamera topilmadi.")
    return camera_instance


def get_current_camera():
    return camera_instance.camera if camera_instance else None
