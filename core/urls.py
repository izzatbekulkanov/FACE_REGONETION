from django.urls import path
from django.views.generic import TemplateView
from . import views
from .generator import video_feed
from .utils.camera import (
    camera_list, save_camera, delete_camera,
    toggle_camera_active, get_camera_info, toggle_camera_selected,
    ajax_camera_list, camera_stream_mjpeg, try_custom_login
)
from .views import (
    staff_list, upload_progress, upload_employees,
    FaceRecognitionLogListView, create_encodings, encoding_progress,
    latest_logs
)

urlpatterns = [
    # 🔴 Kamera va yuz aniqlash sahifalari
    path('live/', TemplateView.as_view(template_name="live_camera.html"), name='live_camera'),
    path('', FaceRecognitionLogListView.as_view(), name='index'),
    path('latest-logs/', latest_logs, name='latest_logs'),

    # 🎥 Video stream
    path('video_feed/', video_feed, name='video_feed'),

    # 👤 Hodimlar
    path('staff/', staff_list, name='staff_list'),
    path('staff/upload/', upload_employees, name='upload_employees'),
    path('staff/upload/progress/', upload_progress, name='upload_progress'),

    # 🔄 Encodings
    path('create_encodings/', create_encodings, name='create_encodings'),
    path('encoding_progress/', encoding_progress, name='encoding_progress'),

    # 📷 Kameralar
    path('cameras/', camera_list, name='camera_list'),
    path('cameras/save/', save_camera, name='camera_save'),
    path('cameras/delete/<int:pk>/', delete_camera, name='camera_delete'),
    path('cameras/toggle/<int:pk>/', toggle_camera_active, name='camera_toggle'),
    path('cameras/edit/<str:ip>/', get_camera_info, name='camera_edit'),
    path('cameras/select/<int:pk>/', toggle_camera_selected, name='toggle_camera_selected'),
    path('cameras/ajax-list/', ajax_camera_list, name='ajax_camera_list'),
    path('cameras/live/<str:ip>/', camera_stream_mjpeg, name='camera_live'),
    path('cameras/try-login/', try_custom_login, name='camera_try_login'),
]