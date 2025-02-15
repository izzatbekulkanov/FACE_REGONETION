from django.urls import path
from .views import face_stream, face_detection_page, camera_list

urlpatterns = [
    path("stream/", face_detection_page, name="face_detection_page"),
    path("video_feed/<str:camera_id>/", face_stream, name="face_stream"),
    path("camera_list/", camera_list, name="camera_list"),
]
