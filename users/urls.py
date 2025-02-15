from django.urls import path
from .views import FetchEmployeesView, get_user_page, CreateAllFaceEncodings, FetchEmployeesProgressView, \
    CreateFaceEncodingProgressView, DeleteAllUsersView

urlpatterns = [
    path('fetch-employees/', FetchEmployeesView.as_view(), name='fetch_employees'),  # 📥 Foydalanuvchilarni yuklash
    path("create-all-face-encodings/", CreateAllFaceEncodings.as_view(), name="create_all_face_encodings"),
    path("fetch-employees-progress/", FetchEmployeesProgressView.as_view(), name="fetch_employees_progress"),
    path("face-encoding-progress/", CreateFaceEncodingProgressView.as_view(), name="face_encoding_progress"),

    path('users/', get_user_page, name='get_user_page'),  # 📄 Foydalanuvchilar ro‘yxati sahifasi
    path("delete-all-users/", DeleteAllUsersView.as_view(), name="delete_all_users"),
]
