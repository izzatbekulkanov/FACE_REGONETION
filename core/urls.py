from django.urls import path
from .utils.camera import (
    camera_list, save_camera, delete_camera,
    toggle_camera_active, get_camera_info, toggle_camera_selected,
    ajax_camera_list, try_custom_login
)
from .views import (
    staff_list, upload_progress, upload_employees,
    FaceRecognitionLogListView, create_encodings, encoding_progress,
    latest_logs
)

urlpatterns = [
    # 🔴 Yuz aniqlash sahifalari
    path('', FaceRecognitionLogListView.as_view(), name='index'),  # Loglar sahifasi
    path('latest-logs/', latest_logs, name='latest_logs'),  # Real vaqtda loglarni olish
    # 👤 Hodimlar (Staff) CRUD
    path('staff/', staff_list, name='staff_list'),  # Hodimlar ro'yxati
    path('staff/upload/', upload_employees, name='upload_employees'),  # Hodimlarni yuklash
    path('staff/upload/progress/', upload_progress, name='upload_progress'),  # Yuklash jarayoni progressi

    # 🔄 Yuz encodinglari
    path('create_encodings/', create_encodings, name='create_encodings'),  # Encodinglar yaratish
    path('encoding_progress/', encoding_progress, name='encoding_progress'),  # Encoding jarayoni progressi

    # 📷 Kameralarni boshqarish
    path('cameras/', camera_list, name='camera_list'),  # Kamera ro'yxati
    path('cameras/save/', save_camera, name='camera_save'),  # Kamera saqlash
    path('cameras/delete/<int:pk>/', delete_camera, name='camera_delete'),  # Kamera o'chirish
    path('cameras/toggle/<int:pk>/', toggle_camera_active, name='camera_toggle'),  # Kamera faol holatni o'zgartirish
    path('cameras/edit/<str:ip_or_id>/', get_camera_info, name='camera_edit'),  # Kamera ma'lumotlarini olish
    path('cameras/select/<int:pk>/', toggle_camera_selected, name='toggle_camera_selected'),  # Tanlangan kamera
    path('cameras/ajax-list/', ajax_camera_list, name='ajax_camera_list'),  # AJAX kamera ro'yxat
    path('cameras/try-login/', try_custom_login, name='camera_try_login'),
]
