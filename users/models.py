import json
import uuid
import dlib
import numpy as np

import face_recognition
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.timezone import now


class CustomUser(AbstractUser):
    """📌 Maxsus foydalanuvchi modeli"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255, verbose_name="To'liq ismi")
    phone_number = models.CharField(max_length=20, unique=True, verbose_name="Telefon raqami")
    email = models.EmailField(unique=True, verbose_name="Email")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Tug'ilgan sana")
    gender = models.CharField(
        max_length=10,
        choices=[("male", "Erkak"), ("female", "Ayol")],
        verbose_name="Jinsi",
    )

    # Institut va ish joyi ma'lumotlari
    institute = models.CharField(max_length=255, blank=True, null=True, verbose_name="Institut nomi")
    department = models.CharField(max_length=255, blank=True, null=True, verbose_name="Bo'lim")
    position = models.CharField(max_length=255, blank=True, null=True, verbose_name="Lavozim")

    face_image = models.ImageField(upload_to="faces/", blank=True, null=True, verbose_name="Foydalanuvchi rasmi")

    is_teacher = models.BooleanField(default=False, verbose_name="O'qituvchi")
    is_student = models.BooleanField(default=False, verbose_name="Talaba")
    is_admin = models.BooleanField(default=False, verbose_name="Admin")

    date_joined = models.DateTimeField(auto_now_add=True, verbose_name="Ro'yxatdan o'tgan sana")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Yangilangan sana")

    def __str__(self):
        return f"{self.full_name} ({self.username})"


class FaceEncoding(models.Model):
    """📌 Foydalanuvchi yuz raqamli ma'lumotlarini saqlash"""

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="face_encoding",
                                verbose_name="Foydalanuvchi")
    encoding = models.JSONField(verbose_name="Yuz kodlash ma'lumotlari", null=True, blank=True)
    face_landmarks = models.JSONField(null=True, blank=True, verbose_name="Yuz landmarks")
    created_at = models.DateTimeField(default=now, verbose_name="Yaratilgan vaqt")

    @staticmethod
    def process_face_image(image_path):
        """📌 Foydalanuvchi rasmini qayta ishlash va encoding, landmarks olish"""
        try:
            image = face_recognition.load_image_file(image_path)
            encodings = face_recognition.face_encodings(image)
            face_landmarks_list = face_recognition.face_landmarks(image)

            if encodings:
                # ✅ Encodingni JSON saqlashdan oldin float64 turiga o'tkazamiz
                encoding_float = np.array(encodings[0], dtype=np.float64).tolist()
                return encoding_float, face_landmarks_list[0] if face_landmarks_list else None
            return None, None
        except Exception as e:
            print(f"❌ [ERROR] Yuzni qayta ishlashda xatolik: {e}")
            return None, None

    @classmethod
    def create_or_update_from_user(cls, user):
        """📌 Foydalanuvchi rasmidan `FaceEncoding` yaratish yoki yangilash"""
        if user.face_image:
            encoding, landmarks = cls.process_face_image(user.face_image.path)
            if encoding:
                face_encoding_obj, created = cls.objects.update_or_create(
                    user=user,
                    defaults={"encoding": json.dumps(encoding), "face_landmarks": landmarks}
                )
                return face_encoding_obj
        return None


class FaceRecognitionLog(models.Model):
    """📌 Foydalanuvchini tanib olish va ma'lumotlarni saqlash"""

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="face_logs",
                             verbose_name="Foydalanuvchi")
    emotion = models.JSONField(verbose_name="Hissiy holat", null=True, blank=True)
    detected_at = models.DateTimeField(default=now, verbose_name="Aniqlangan vaqt")
    face_landmarks = models.JSONField(null=True, blank=True, verbose_name="Aniqlangan yuz landmarks")

    def __str__(self):
        return f"{self.user.full_name} - {self.detected_at.strftime('%Y-%m-%d %H:%M:%S')}"

    @classmethod
    def create_log(cls, user, emotion, landmarks):
        """📌 Foydalanuvchi aniqlanganda `FaceRecognitionLog` yaratish"""
        return cls.objects.create(user=user, emotion=json.dumps(emotion), face_landmarks=landmarks)
