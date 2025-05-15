import uuid
from datetime import datetime, date
from unittest.mock import patch, MagicMock
import cv2
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from .models import CustomUser, FaceEncoding, FaceRecognitionLog, Attendance, Camera, FaceSnapshot

class CustomUserTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create(
            id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            phone_number="+998901234567",
            gender="male",
            is_teacher=True
        )

    def test_custom_user_creation(self):
        self.assertEqual(self.user.full_name, "Test User")
        self.assertEqual(self.user.email, "test@example.com")
        self.assertTrue(self.user.is_teacher)
        self.assertFalse(self.user.is_student)
        self.assertFalse(self.user.is_admin)
        self.assertEqual(str(self.user), "Test User")

    def test_get_face_image_url(self):
        self.assertIsNone(self.user.get_face_image_url())
        self.user.face_image = SimpleUploadedFile("face.jpg", b"file_content", content_type="image/jpeg")
        self.user.save()
        self.assertTrue(self.user.get_face_image_url().endswith("face.jpg"))

class FaceEncodingTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create(
            id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            full_name="Test User",
            face_image=SimpleUploadedFile("face.jpg", b"file_content", content_type="image/jpeg")
        )

    @patch("cv2.imread")
    @patch("your_app.models.insightface.app.FaceAnalysis.get")
    def test_process_face_image_success(self, mock_insight_get, mock_cv2_imread):
        # Mock cv2.imread
        mock_cv2_imread.return_value = MagicMock()
        # Mock insightface
        mock_face = MagicMock()
        mock_face.embedding = [0.1, 0.2, 0.3]
        mock_face.kps = [[1, 2], [3, 4], [5, 6], [7, 8], [9, 10]]
        mock_insight_get.return_value = [mock_face]

        embedding, landmarks = FaceEncoding.process_face_image("/path/to/image.jpg", MagicMock())
        self.assertEqual(embedding, [0.1, 0.2, 0.3])
        self.assertEqual(landmarks, {
            "p0": [1.0, 2.0],
            "p1": [3.0, 4.0],
            "p2": [5.0, 6.0],
            "p3": [7.0, 8.0],
            "p4": [9.0, 10.0]
        })

    @patch("cv2.imread")
    def test_process_face_image_no_image(self, mock_cv2_imread):
        mock_cv2_imread.return_value = None
        embedding, landmarks = FaceEncoding.process_face_image("/path/to/image.jpg", MagicMock())
        self.assertIsNone(embedding)
        self.assertIsNone(landmarks)

    @patch("cv2.imread")
    @patch("your_app.models.insightface.app.FaceAnalysis.get")
    def test_create_or_update_encoding(self, mock_insight_get, mock_cv2_imread):
        mock_cv2_imread.return_value = MagicMock()
        mock_face = MagicMock()
        mock_face.embedding = [0.1, 0.2, 0.3]
        mock_face.kps = [[1, 2], [3, 4]]
        mock_insight_get.return_value = [mock_face]

        encoding_obj = FaceEncoding.create_or_update(self.user, MagicMock())
        self.assertIsNotNone(encoding_obj)
        self.assertEqual(encoding_obj.encoding, [0.1, 0.2, 0.3])
        self.assertEqual(encoding_obj.landmarks, {"p0": [1.0, 2.0], "p1": [3.0, 4.0]})

class FaceRecognitionLogTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create(
            id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            full_name="Test User"
        )
        self.camera = Camera.objects.create(
            name="Test Camera",
            type="usb",
            source="0",
            is_active=True
        )

    def test_log_recognition(self):
        log = FaceRecognitionLog.log_recognition(
            user=self.user,
            camera=self.camera,
            emotion_data={"emotion": "happy"},
            landmarks_data={"p0": [1.0, 2.0]},
            image_path=SimpleUploadedFile("captured.jpg", b"file_content", content_type="image/jpeg")
        )
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.camera, self.camera)
        self.assertEqual(log.emotion, {"emotion": "happy"})
        self.assertEqual(log.landmarks, {"p0": [1.0, 2.0]})
        self.assertTrue(log.captured_image.name.endswith("captured.jpg"))
        self.assertEqual(str(log), f"Test User - {log.detected_at.strftime('%Y-%m-%d %H:%M:%S')}")

class AttendanceTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create(
            id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            full_name="Test User"
        )
        self.attendance = Attendance.objects.create(
            user=self.user,
            date=date.today()
        )

    def test_attendance_creation(self):
        self.assertEqual(self.attendance.user, self.user)
        self.assertEqual(self.attendance.date, date.today())
        self.assertIsNotNone(self.attendance.check_in_time)
        self.assertIsNone(self.attendance.check_out_time)
        self.assertEqual(str(self.attendance), f"Test User - {self.attendance.date}")

    def test_check_out(self):
        self.attendance.check_out()
        self.assertIsNotNone(self.attendance.check_out_time)

    def test_unique_together_constraint(self):
        with self.assertRaises(Exception):
            Attendance.objects.create(user=self.user, date=date.today())

class CameraTests(TestCase):
    def test_camera_creation(self):
        camera = Camera.objects.create(
            name="IP Camera",
            type="ip",
            source="192.168.1.100",
            is_active=True
        )
        self.assertEqual(camera.name, "IP Camera")
        self.assertEqual(camera.type, "ip")
        self.assertEqual(camera.source, "192.168.1.100")
        self.assertTrue(camera.is_active)
        self.assertEqual(str(camera), "IP Camera (IP Kamera)")

    def test_toggle_active(self):
        camera = Camera.objects.create(name="Test Camera", type="usb", source="0", is_active=True)
        camera.toggle_active()
        self.assertFalse(camera.is_active)
        camera.toggle_active()
        self.assertTrue(camera.is_active)

    def test_clean_invalid_ip(self):
        camera = Camera(name="Invalid IP Camera", type="ip", source="invalid_ip")
        with self.assertRaises(ValidationError):
            camera.clean()

class FaceSnapshotTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create(
            id=uuid.uuid4(),
            username="testuser",
            email="test@example.com",
            full_name="Test User"
        )
        self.camera = Camera.objects.create(
            name="Test Camera",
            type="usb",
            source="0"
        )
        self.snapshot = FaceSnapshot.objects.create(
            user=self.user,
            camera=self.camera,
            image=SimpleUploadedFile("snapshot.jpg", b"file_content", content_type="image/jpeg")
        )

    def test_snapshot_creation(self):
        self.assertEqual(self.snapshot.user, self.user)
        self.assertEqual(self.snapshot.camera, self.camera)
        self.assertTrue(self.snapshot.image.name.endswith("snapshot.jpg"))
        self.assertIsNone(self.snapshot.video)
        self.assertEqual(
            str(self.snapshot),
            f"Test User snapshot - {self.snapshot.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    def test_snapshot_with_video(self):
        snapshot = FaceSnapshot.objects.create(
            user=self.user,
            camera=self.camera,
            image=SimpleUploadedFile("snapshot.jpg", b"file_content", content_type="image/jpeg"),
            video=SimpleUploadedFile("video.mp4", b"video_content", content_type="video/mp4")
        )
        self.assertTrue(snapshot.video.name.endswith("video.mp4"))