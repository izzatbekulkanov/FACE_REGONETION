# routing.py
from django.urls import re_path

from core.utils.camera import CameraStreamConsumer

websocket_urlpatterns = [
    re_path(r'ws/stream/(?P<ip>[^/]+)/$', CameraStreamConsumer.as_asgi()),
]
