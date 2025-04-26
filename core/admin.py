from django.contrib import admin
from django.utils.html import format_html
from .models import CustomUser, FaceEncoding, FaceRecognitionLog, Attendance, Camera, FaceSnapshot


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = (
    'full_name', 'email', 'phone_number', 'position', 'is_teacher', 'is_student', 'is_admin', 'date_joined')
    list_filter = ('is_teacher', 'is_student', 'is_admin', 'gender', 'department')
    search_fields = ('full_name', 'email', 'phone_number')
    readonly_fields = ('id', 'date_joined', 'updated_at', 'face_image_preview')

    def face_image_preview(self, obj):
        if obj.face_image:
            return format_html(f'<img src="{obj.face_image.url}" width="100" height="100" style="object-fit:cover;"/>')
        return "Rasm yo'q"

    face_image_preview.short_description = 'Face Image Preview'


@admin.register(FaceEncoding)
class FaceEncodingAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    search_fields = ('user__full_name', 'user__email')
    readonly_fields = ('user', 'encoding', 'landmarks', 'created_at')


@admin.register(FaceRecognitionLog)
class FaceRecognitionLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'detected_at', 'emotion_summary')
    search_fields = ('user__full_name', 'user__email')
    list_filter = ('detected_at',)
    readonly_fields = ('user', 'detected_at', 'emotion', 'landmarks')

    def emotion_summary(self, obj):
        return ", ".join([f"{key}: {value:.2f}" for key, value in obj.emotion.items()]) if obj.emotion else "-"

    emotion_summary.short_description = 'Emotion Summary'


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'check_in_time', 'check_out_time')
    list_filter = ('date',)
    search_fields = ('user__full_name', 'user__email')
    readonly_fields = ('user', 'date', 'check_in_time', 'check_out_time')


@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'source', 'is_active', 'created_at')
    list_filter = ('type', 'is_active')
    search_fields = ('name', 'source')
    readonly_fields = ('created_at',)

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)


@admin.register(FaceSnapshot)
class FaceSnapshotAdmin(admin.ModelAdmin):
    list_display = ("user", "camera", "created_at")
    search_fields = ("user__full_name",)
    list_filter = ("camera", "created_at")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)
