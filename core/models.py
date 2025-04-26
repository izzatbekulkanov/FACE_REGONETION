import traceback
import uuid
import cv2
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.timezone import now


class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=[("male", "Erkak"), ("female", "Ayol")],
    )

    institute = models.CharField(max_length=255, blank=True, null=True)
    department = models.CharField(max_length=255, blank=True, null=True)
    position = models.CharField(max_length=255, blank=True, null=True)

    face_image = models.ImageField(upload_to="faces/", blank=True, null=True)

    is_teacher = models.BooleanField(default=False)
    is_student = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_face_image_url(self):
        return self.face_image.url if self.face_image else None

    def __str__(self):
        return self.full_name


class FaceEncoding(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="face_encoding")
    encoding = models.JSONField()
    landmarks = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def process_face_image(image_path, insight_app):
        try:
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError("Tasvirni o‘qib bo‘lmadi.")

            faces = insight_app.get(img)
            if not faces:
                raise ValueError("Yuz aniqlanmadi.")

            face = faces[0]

            # Encoding
            embedding = [float(x) for x in face.embedding]

            # Landmarks
            landmarks = {}
            if hasattr(face, 'kps') and face.kps is not None:
                landmarks = {
                    f"p{i}": [float(p[0]), float(p[1])] for i, p in enumerate(face.kps)
                }

            return embedding, landmarks

        except Exception as e:
            traceback.print_exc()
            return None, None

    @classmethod
    def create_or_update(cls, user, insight_app):
        if user.face_image and hasattr(user.face_image, 'path'):
            encoding, landmarks = cls.process_face_image(user.face_image.path, insight_app)
            if encoding:
                obj, created = cls.objects.update_or_create(
                    user=user,
                    defaults={
                        "encoding": encoding,
                        "landmarks": landmarks
                    }
                )
                return obj
        return None


class FaceRecognitionLog(models.Model):
    camera = models.ForeignKey('Camera', on_delete=models.SET_NULL, null=True, blank=True)
    captured_image = models.ImageField(upload_to="recognized/", blank=True, null=True)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="recognition_logs")
    emotion = models.JSONField(null=True, blank=True)
    landmarks = models.JSONField(null=True, blank=True)
    detected_at = models.DateTimeField(default=now)

    def __str__(self):
        return f"{self.user.full_name} - {self.detected_at.strftime('%Y-%m-%d %H:%M:%S')}"

    @classmethod
    def log_recognition(cls, user, emotion_data=None, landmarks_data=None, camera=None, image_path=None):
        return cls.objects.create(
            user=user,
            camera=camera,
            captured_image=image_path,
            emotion=emotion_data or {},
            landmarks=landmarks_data or {}
        )


class Attendance(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="attendance_records")
    date = models.DateField(default=now)
    check_in_time = models.DateTimeField(auto_now_add=True)
    check_out_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']

    def check_out(self):
        self.check_out_time = now()
        self.save()

    def __str__(self):
        return f"{self.user.full_name} - {self.date}"


class Camera(models.Model):
    CAMERA_TYPES = [
        ('usb', 'USB Kamera'),
        ('ip', 'IP Kamera'),
        ('ptz', 'PTZ Kamera'),
    ]

    name = models.CharField(max_length=100, verbose_name="Kamera nomi")
    type = models.CharField(max_length=10, choices=CAMERA_TYPES, verbose_name="Kamera turi")
    source = models.CharField(max_length=255, verbose_name="Manba (index yoki URL)")
    is_active = models.BooleanField(default=True, verbose_name="Faol")
    selected = models.BooleanField(default=False, verbose_name="Joriy ro'yxatga olayotgan kamera")
    hardware_path = models.CharField(max_length=255, null=True, blank=True)
    username = models.CharField(max_length=100, null=True, blank=True, verbose_name="Foydalanuvchi nomi")
    password = models.CharField(max_length=100, null=True, blank=True, verbose_name="Parol")

    created_at = models.DateTimeField(auto_now_add=True)

    def toggle_active(self):
        self.is_active = not self.is_active
        self.save()

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.type == 'ip':
            import ipaddress
            try:
                ipaddress.ip_address(self.source)
            except ValueError:
                raise ValidationError("IP manzili noto‘g‘ri kiritilgan.")

    def __str__(self):
        return f"{self.name} ({self.get_type_display()})"



class FaceSnapshot(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="face_snapshots")
    camera = models.ForeignKey(Camera, on_delete=models.SET_NULL, null=True, blank=True)
    image = models.ImageField(upload_to="snapshots/")
    video = models.FileField(upload_to="videos/", null=True, blank=True)  # 🆕 video field
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.full_name} snapshot - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
