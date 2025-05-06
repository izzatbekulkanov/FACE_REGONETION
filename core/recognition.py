# core/recognition.py
import cv2
import numpy as np
import threading
import time
import subprocess
import re
import urllib.parse
from urllib.parse import quote
from core.models import Camera, CustomUser, FaceEncoding, FaceRecognitionLog
from insightface.app import FaceAnalysis
import os

from face_recognition_project import settings

# Global tanlangan kamera instansiyasi
camera_instance = None


import cv2
import numpy as np
import threading
import time
import os
from urllib.parse import quote
from core.models import Camera, CustomUser, FaceEncoding, FaceRecognitionLog
from insightface.app import FaceAnalysis
from face_recognition_project import settings

class VideoCamera:
    """
    Barqaror RTSP TCP oqimi, InsightFace bilan yuqori aniqlikda (4K qo‘llab-quvvatlash) yuz tanish,
    va media/snapshots/ ichiga yo‘qotishsiz PNG formatida tiniq rasm saqlash funksiyasi.
    Foydalanuvchi aniqlanganda faqat yetarlicha ishonchli tanilgandan keyin ro‘yxatga olinadi.
    """

    def __init__(self, camera_obj, source=None):
        self.camera = camera_obj
        self.name = camera_obj.name
        self.type = camera_obj.type
        self.username = camera_obj.username
        self.password = camera_obj.password
        self.source = source or self._prepare_source(camera_obj)

        # Sozlamalar
        self.match_distance_threshold = 0.6  # Yuz mosligi chegarasi
        self.detection_threshold = 10  # Ketma-ket aniqlash chegarasi (ko‘proq ishonch uchun oshirildi)
        self.cooldown_period = 30  # Sekundlarda, foydalanuvchi qayta ro‘yxatga olinmasligi uchun
        self.unknown_cooldown = 10  # Noma'lum shaxslar uchun snapshotlar orasidagi vaqt

        print(f"🎥 [VideoCamera] Kamera ochilmoqda | Source: {self.source}")
        self.cap = self._open_camera(self.source)
        self._configure_camera()

        self.app = self._prepare_insightface_model()

        self.known_encodings, self.known_users = self.load_known_faces()

        # Aniqlash hisoblagichlari va vaqt belgilarini saqlash
        self.detection_counts = {}  # Foydalanuvchi ID bo‘yicha aniqlash soni
        self.detected_users = {}  # Foydalanuvchi ID bo‘yicha oxirgi ro‘yxat vaqti
        self.last_unknown_snapshot = 0  # Oxirgi noma'lum snapshot vaqti

        self.running = True
        self.frame = None

        threading.Thread(target=self.update, daemon=True).start()

    def _prepare_source(self, camera_obj):
        """Kamera manbasini tayyorlash (RTSP yoki USB)."""
        if camera_obj.type == "usb":
            return int(camera_obj.source)
        if camera_obj.type in ["ip", "ptz"]:
            ip_part = camera_obj.source.replace("rtsp://", "")
            username_encoded = quote(camera_obj.username or "admin")
            password_encoded = quote(camera_obj.password or "admin")
            base_url = f"rtsp://{username_encoded}:{password_encoded}@{ip_part}"
            return base_url + ("&transport=tcp" if "?" in base_url else "?transport=tcp")
        return camera_obj.source

    def _open_camera(self, source):
        """Kamera oqimini ochish."""
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Live oqim uchun minimal bufer
        if not cap.isOpened():
            raise Exception(f"❌ Kamera ochilmadi: {source}")
        print(f"✅ [VideoCamera] Kamera ochildi: {source}")
        return cap

    def _configure_camera(self):
        """Kamera sozlamalarini yuqori sifat uchun optimallashtirish."""
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)  # 4K o‘lcham
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)  # 4K o‘lcham
        self.cap.set(cv2.CAP_PROP_FPS, 30)  # 30 FPS
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))  # H.264 kodek
        self.cap.set(cv2.CAP_PROP_BITRATE, 8000000)  # 8 Mbps bitrate

    def _prepare_insightface_model(self):
        """InsightFace modelini standart sozlamalar bilan tayyorlash."""
        print("🛠️ [VideoCamera] InsightFace model tayyorlanmoqda...")
        app = FaceAnalysis(name="buffalo_l", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        app.prepare(ctx_id=0, det_size=(640, 640))  # Standart sozlama
        print("✅ [VideoCamera] InsightFace model tayyor!")
        return app

    def load_known_faces(self):
        """Ma'lum yuzlarni yuklash va o‘lchamlarni tekshirish."""
        print("🔎 [VideoCamera] Yuz ma'lumotlari yuklanmoqda...")
        encodings, users, error_count = [], [], 0
        expected_shape = (512,)  # buffalo_l modelining odatiy embedding uzunligi
        for face in FaceEncoding.objects.select_related('user').all():
            try:
                encoding = np.array(face.encoding, dtype=np.float32)
                if encoding.shape == expected_shape:
                    encodings.append(encoding)
                    users.append(face.user)
                else:
                    print(f"⚠️ Noto‘g‘ri encoding o‘lchami: {encoding.shape}, kutilgan: {expected_shape}")
                    error_count += 1
            except Exception as e:
                print(f"⚠️ Encoding xatosi: {e}")
                error_count += 1
        print(f"✅ [VideoCamera] {len(encodings)} ta yuz tayyor | Xatoliklar: {error_count}")
        return np.array(encodings, dtype=np.float32), users

    def update(self):
        """Doimiy ravishda ramkalarni o‘qish va qayta ishlash."""
        last_reset = time.time()
        while self.running and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                print("🔴 Kamera oqimi yo‘q...")
                time.sleep(0.5)
                continue

            self.frame = self.process_frame(frame)

            # Har 3 sekundda detection count ni pasaytirish
            if time.time() - last_reset > 3:
                for uid in list(self.detection_counts.keys()):
                    self.detection_counts[uid] = max(0, self.detection_counts[uid] - 1)
                    # Agar foydalanuvchi uzoq vaqt ko‘rinmasa, detected_users dan o‘chirish
                    if self.detection_counts[uid] == 0 and uid in self.detected_users:
                        del self.detected_users[uid]
                last_reset = time.time()

    def process_frame(self, frame):
        """Ramkani qayta ishlash va yuzlarni aniqlash."""
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = self.app.get(rgb)
        except Exception as e:
            print(f"⚠️ Freymda xatolik: {e}")
            return frame

        for face in faces:
            name = "Noma'lum"
            color = (0, 0, 255)
            embedding = np.array(face.embedding, dtype=np.float32)

            if self.known_encodings.shape[0] == 0:
                print("❌ Noma'lum inson kameradan o'tdi (bazada hech kim yo'q)")
                self.save_unknown_snapshot(frame)
                continue

            if embedding.shape != (512,):
                print(f"⚠️ Noto‘g‘ri embedding o‘lchami: {embedding.shape}, kutilgan: (512,)")
                continue

            try:
                distances = np.linalg.norm(self.known_encodings - embedding, axis=1)
                best_idx = np.argmin(distances)
                best_distance = distances[best_idx]
            except Exception as e:
                print(f"⚠️ Embedding solishtirishda xatolik: {e}")
                continue

            if best_distance < self.match_distance_threshold:
                user = self.known_users[best_idx]
                uid = user.id

                # Yuz to‘g‘ri qaraganligini tekshirish
                if hasattr(face, 'kps') and face.kps is not None:
                    left_eye, right_eye = face.kps[0], face.kps[1]
                    eye_distance = np.linalg.norm(np.array(left_eye) - np.array(right_eye))
                    if eye_distance < 20:  # Ko‘zlar juda yaqin — burilgan yuz
                        continue

                # Aniqlash hisoblagichini oshirish
                self.detection_counts[uid] = self.detection_counts.get(uid, 0) + 1

                # Foydalanuvchi yetarlicha aniqlangan va cooldown davrida emasligini tekshirish
                current_time = time.time()
                last_detected = self.detected_users.get(uid, 0)
                if (self.detection_counts[uid] >= self.detection_threshold and
                    current_time - last_detected > self.cooldown_period):
                    try:
                        FaceRecognitionLog.log_recognition(user, camera=self.camera)
                        self.save_snapshot(frame, user.full_name, face.bbox)
                        self.detected_users[uid] = current_time  # Oxirgi ro‘yxat vaqtini yangilash
                        print(f"✅ Yuz ANIQLANDI: {user.full_name} (Masofa: {best_distance:.2f})")
                    except Exception as e:
                        print(f"⚠️ Log yozishda xatolik: {e}")

                name = user.full_name
                color = (0, 255, 0)

            else:
                # Noma'lum shaxs, cooldown ichida snapshot saqlash
                current_time = time.time()
                if current_time - self.last_unknown_snapshot > self.unknown_cooldown:
                    self.save_unknown_snapshot(frame)
                    self.last_unknown_snapshot = current_time
                print("❌ Noma'lum inson kameradan o'tdi")

            x1, y1, x2, y2 = map(int, face.bbox)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label_y = y1 - 10 if y1 - 10 > 10 else y1 + 20
            cv2.putText(frame, name, (x1, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return frame

    def save_unknown_snapshot(self, frame):
        """Noma'lum inson uchun snapshotni saqlash."""
        unknown_dir = os.path.join(settings.MEDIA_ROOT, "unknown_snapshots")
        os.makedirs(unknown_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"unknown_{timestamp}.jpg"
        filepath = os.path.join(unknown_dir, filename)

        try:
            cv2.imwrite(filepath, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 100])
            print(f"🖼 Noma'lum snapshot saqlandi: {filepath}")
        except Exception as e:
            print(f"⚠️ Noma’lum snapshot saqlashda xatolik: {e}")

    def save_snapshot(self, frame, full_name, face_bbox=None):
        """Yo‘qotishsiz PNG formatida snapshot saqlash, yuz hududini kesish imkoniyati bilan."""
        snapshots_dir = os.path.join(settings.MEDIA_ROOT, "snapshots")
        os.makedirs(snapshots_dir, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() else "_" for c in full_name)
        filename = f"{safe_name}_{timestamp}.png"
        filepath = os.path.join(snapshots_dir, filename)

        if face_bbox:
            x1, y1, x2, y2 = map(int, face.bbox)
            margin = 50
            x1, y1 = max(0, x1 - margin), max(0, y1 - margin)
            x2, y2 = min(frame.shape[1], x2 + margin), min(frame.shape[0], y2 + margin)
            cropped_frame = frame[y1:y2, x1:x2]
            cv2.imwrite(filepath, cropped_frame, [int(cv2.IMWRITE_PNG_COMPRESSION), 0])
        else:
            cv2.imwrite(filepath, frame, [int(cv2.IMWRITE_PNG_COMPRESSION), 0])

        print(f"🖼 Snapshot saqlandi: {filepath}")

    def get_frame(self, jpeg_quality=95):
        """Ramkani JPEG sifatida qaytarish."""
        if self.frame is not None:
            _, jpeg = cv2.imencode('.jpg', self.frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
            return jpeg.tobytes()
        return None

    def stop(self):
        """Kamera resurslarini tozalash."""
        print("🛑 [VideoCamera] Kamera to‘xtatilmoqda...")
        self.running = False
        self.cap.release()
        print("✅ [VideoCamera] Kamera resurslari tozalandi.")


def get_index_from_hardware_path(hardware_path):
    """
    USB kamera uchun /dev/videoX indeksini olish.
    """
    try:
        result = subprocess.run(['v4l2-ctl', '--list-devices'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)
        lines = result.stdout.split('\n')

        current_path = None
        for line in lines:
            if not line.startswith('\t'):
                match = re.search(r'\((usb-[^)]+)\)', line)
                if match:
                    current_path = match.group(1)
            elif current_path == hardware_path:
                video_match = re.search(r'/dev/video(\d+)', line.strip())
                if video_match:
                    return int(video_match.group(1))
    except Exception as e:
        print(f"⚠️ USB index aniqlashda xatolik: {e}")
    return None


def get_selected_camera():
    global camera_instance

    if camera_instance is None or not getattr(camera_instance, 'running', False):
        print("🔍 [get_selected_camera] Yangi kamera ochilmoqda...")

        camera_obj = Camera.objects.filter(is_active=True, selected=True).first()

        if camera_obj:
            try:
                if camera_obj.type == "usb":
                    print(f"🔌 USB kamera aniqlanmoqda: {camera_obj.name}")
                    index = get_index_from_hardware_path(camera_obj.source)
                    if index is not None:
                        source = str(index)
                        print(f"✅ USB kamera indeksi: /dev/video{source}")
                    else:
                        raise Exception(f"USB kamera indeksi topilmadi: {camera_obj.source}")
                elif camera_obj.type in ["ip", "ptz"]:
                    print(f"🌐 IP/PTZ kamera aniqlanmoqda: {camera_obj.name}")
                    if not (camera_obj.username and camera_obj.password):
                        raise Exception(f"IP/PTZ kamerada username yoki password mavjud emas: {camera_obj.name}")
                    username = urllib.parse.quote(camera_obj.username)
                    password = urllib.parse.quote(camera_obj.password)
                    source = f"rtsp://{username}:{password}@{camera_obj.source}:554/cam/realmonitor?channel=1&subtype=0"
                    print(f"✅ RTSP manzil: {source}")
                else:
                    raise Exception(f"Noma'lum kamera turi: {camera_obj.type}")

                camera_instance = VideoCamera(camera_obj, source=source)
                print(f"🎥 Kamera ishga tushdi: {camera_obj.name} ({camera_obj.type.upper()})")

            except Exception as e:
                print(f"❌ Kamera ochishda xatolik: {e}")
                camera_instance = None
        else:
            print("⚠️ Faol va tanlangan kamera topilmadi.")

    else:
        print("♻️ Avvalgi camera_instance ishlayapti, yangi yuklanmaydi.")

    return camera_instance
