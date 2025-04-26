# core/generator.py
from django.http import StreamingHttpResponse
from .live import get_camera_instance

def gen(camera):
    while True:
        frame = camera.get_frame()
        if frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

def video_feed(request):
    camera = get_camera_instance()
    if not camera:
        raise ValueError("❌ Faol kamera mavjud emas!")

    return StreamingHttpResponse(gen(camera),
                                 content_type='multipart/x-mixed-replace; boundary=frame')
