import json

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.utils.html import format_html
from django.utils.timezone import now
from .models import CustomUser, FaceEncoding, FaceRecognitionLog
from django.urls import path


class FaceEncodingInline(admin.StackedInline):
    """📌 Foydalanuvchining yuz encodinglarini admin panelda ko‘rsatish"""
    model = FaceEncoding
    extra = 0
    readonly_fields = ("encoding", "face_landmarks", "created_at")


class FaceRecognitionLogInline(admin.TabularInline):
    """📌 Foydalanuvchini tanib olish loglari"""
    model = FaceRecognitionLog
    extra = 0
    readonly_fields = ("emotion", "detected_at", "face_landmarks")


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    """📌 Foydalanuvchi admin paneli"""

    list_display = (
    "full_name", "email", "phone_number", "department", "position", "is_teacher", "is_student", "admin_photo")
    list_filter = ("is_teacher", "is_student", "is_admin", "department")
    search_fields = ("full_name", "email", "phone_number")
    readonly_fields = ("date_joined", "updated_at")
    inlines = [FaceEncodingInline, FaceRecognitionLogInline]
    actions = ["activate_users", "deactivate_users", "update_face_encodings"]

    def admin_photo(self, obj):
        """📌 Foydalanuvchi rasmni admin panelda ko‘rsatish"""
        if obj.face_encoding:
            return format_html('<img src="{}" width="50" height="50" style="border-radius: 50%;" />',
                               obj.face_image.url)
        return "No Image"

    admin_photo.short_description = "Rasm"

    @admin.action(description="✅ Tanlangan foydalanuvchilarni faollashtirish")
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, "✅ Foydalanuvchilar faollashtirildi!")

    @admin.action(description="❌ Tanlangan foydalanuvchilarni o‘chirish")
    def deactivate_users(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, "❌ Foydalanuvchilar o‘chirildi!")

    @admin.action(description="🔄 Tanlangan foydalanuvchilar yuz kodlash ma'lumotlarini yangilash")
    def update_face_encodings(self, request, queryset):
        updated_count = 0
        for user in queryset:
            if user.face_image:
                encoding, landmarks = FaceEncoding.process_face_image(user.face_image.path)
                if encoding:
                    FaceEncoding.objects.update_or_create(
                        user=user,
                        defaults={"encoding": encoding, "face_landmarks": landmarks, "created_at": now()}
                    )
                    updated_count += 1
        self.message_user(request, f"✅ {updated_count} foydalanuvchi yuz kodlash ma'lumotlari yangilandi!")


@admin.register(FaceEncoding)
class FaceEncodingAdmin(admin.ModelAdmin):
    """📌 Foydalanuvchi yuz kodlash ma'lumotlari"""
    list_display = ("user", "created_at")
    search_fields = ("user__full_name",)
    readonly_fields = ("encoding", "face_landmarks", "created_at")


@admin.register(FaceRecognitionLog)
class FaceRecognitionLogAdmin(admin.ModelAdmin):
    """📌 Foydalanuvchini tanib olish loglari"""

    list_display = ("user", "formatted_emotion", "detected_at", "delete_old_logs_button")
    search_fields = ("user__full_name", "emotion")
    list_filter = ("detected_at",)
    readonly_fields = ("formatted_emotion", "detected_at", "face_landmarks")

    # 🔹 JSON emotion maydonini formatlash
    def formatted_emotion(self, obj):
        if not obj.emotion:  # Agar emotion maydoni None yoki bo‘sh bo‘lsa
            return "Mavjud emas"

        try:
            emotion_data = json.loads(obj.emotion)  # JSON deserializatsiya
            if isinstance(emotion_data, dict):
                dominant_emotion = emotion_data.get("dominant_emotion", "Noma'lum")
                confidence = emotion_data.get("confidence", 0)
                return f"{dominant_emotion} ({confidence:.1f}%)"
            return str(emotion_data)
        except json.JSONDecodeError:
            return "Mavjud emas"

    formatted_emotion.short_description = "Emotion"

    # 🔹 Eski loglarni o‘chirish tugmachasi
    def delete_old_logs_button(self, obj):
        return format_html('<a class="button" href="delete-old-logs/">🗑 Eski loglarni o‘chirish</a>')

    delete_old_logs_button.short_description = "Eski loglarni o‘chirish"
    delete_old_logs_button.allow_tags = True

    # 🔹 Admin panelga yangi URL qo‘shish
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('delete-old-logs/', self.admin_site.admin_view(self.delete_old_logs), name='delete_old_logs'),
        ]
        return custom_urls + urls

    # 🔹 Loglar 10,000 dan oshsa o‘chirish
    def delete_old_logs(self, request):
        max_logs = 10000  # ⚡ Cheklov
        total_logs = FaceRecognitionLog.objects.count()

        if total_logs > max_logs:
            logs_to_delete = total_logs - max_logs
            old_logs = FaceRecognitionLog.objects.order_by("detected_at")[:logs_to_delete]
            deleted_count, _ = old_logs.delete()

            self.message_user(request, f"✅ {deleted_count} ta eski log o‘chirildi!", messages.SUCCESS)
        else:
            self.message_user(request, "📌 Hozircha loglar yetarlicha kam, o‘chirish shart emas!", messages.WARNING)

        return redirect("..")
