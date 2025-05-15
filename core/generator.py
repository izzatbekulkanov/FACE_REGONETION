import cv2
from django.http import StreamingHttpResponse
from .live import get_camera_instance

def gen(camera):
    """
    Kamera kadrlarni JPEG formatida uzluksiz oqim sifatida qaytaradi.
    """
    while True:
        frame = camera.get_frame()
        if frame is not None:
            # Kadrni JPEG formatiga o‘girish
            _, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')
        else:
            # Kadr o‘qilmagan bo‘lsa, qisqa pauza
            import time
            time.sleep(0.1)

def video_feed(request):
    """
    PTZ kamera oqimini veb-interfeysga uzatadi.
    """
    camera = get_camera_instance()
    if not camera:
        raise ValueError("❌ Faol kamera mavjud emas!")

    return StreamingHttpResponse(gen(camera),
                                content_type='multipart/x-mixed-replace; boundary=frame')