from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('face_app.urls')),  # face_app URL-larini bog‘lash
    path('', include('users.urls')),  # face_app URL-larini bog‘lash
]

# Media fayllarga ruxsat berish
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
