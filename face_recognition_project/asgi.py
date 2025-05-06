import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

# ✅ MUHIM! Django settingsni to'g'rilab olamiz
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'face_recognition_project.settings')
django.setup()

from core.routing import websocket_urlpatterns  # django.setup()dan keyin import qilamiz!

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(websocket_urlpatterns),
})