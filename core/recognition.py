import cv2
import numpy as np
import threading
import time
import logging
import os
import asyncio
import websockets
from django.utils.timezone import now
from django.core.files.base import ContentFile
from core.models import Camera, CustomUser, FaceEncoding, FaceRecognitionLog, FaceSnapshot, Attendance
from core.live import get_camera_instance, get_current_camera
from insightface.app import FaceAnalysis
from face_recognition_project import settings

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('face_recognition.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WebSocketStream:
    """WebSocket orqali MPEG-TS oqimini boshqarish sinfi."""
    def __init__(self, camera):
        self.camera = camera
        self.running = False
        self.websocket = None
        self.frame = None
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.start()

    async def connect_websocket(self):
        """WebSocket ulanishini ochish."""
        username = self.camera.username or "admin"
        password = self.camera.password or "Qwerty@123456."
        ws_url = f"ws://localhost:8000/ws/stream/{self.camera.source}/?username={username}&password={password}"
        try:
            self.websocket = await websockets.connect(ws_url)
            logger.info(f"WebSocket ulandi: {ws_url}")
            print(f"🟢 WebSocket ulandi: {self.camera.source}")
            self.running = True
        except Exception as e:
            logger.error(f"WebSocket ulanish xatosi: {e}")
            print(f"❌ WebSocket ulanish xatosi: {e}")
            self.running = False

    async def receive_frames(self):
        """WebSocket dan MPEG-TS kadrlarini olish."""
        try:
            while self.running and self.websocket:
                data = await self.websocket.recv()
                # MPEG-TS ni OpenCV bilan dekod qilish uchun numpy massiviga aylantirish
                nparr = np.frombuffer(data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if frame is not None:
                    self.frame = frame
                else:
                    logger.warning("Kadr dekod qilinmadi")
        except Exception as e:
            logger.error(f"WebSocket kadr olish xatosi: {e}")
            print(f"❌ WebSocket kadr olish xatosi: {e}")
            self.running = False

    def start(self):
        """WebSocket oqimini boshlash."""
        self.loop.run_until_complete(self.connect_websocket())
        if self.running:
            asyncio.ensure_future(self.receive_frames(), loop=self.loop)
            threading.Thread(target=self.loop.run_forever, daemon=True).start()

    def get_frame(self):
        """Joriy kadrni olish."""
        return self.frame if self.frame is not None else None

    def stop(self):
        """WebSocket oqimini yopish."""
        self.running = False
        if self.websocket:
            self.loop.run_until_complete(self.websocket.close())
        self.loop.stop()
        self.loop.close()
        logger.info(f"WebSocket oqimi yopildi: {self.camera.source}")
        print(f"🔴 WebSocket oqimi yopildi: {self.camera.source}")

    def __del__(self):
        self.stop()

class FaceRecognizer:
    """Yuz aniqlash va tanish sinfi."""
    def __init__(self, similarity_threshold=0.65):
        self.similarity_threshold = similarity_threshold
        self.face_app = FaceAnalysis(name='buffalo_l', providers=["CPUExecutionProvider"])
        self.face_app.prepare(ctx_id=0, det_size=(640, 640))
        self.running = False
        self.thread = None
        self.known_encodings, self.known_users = self.load_known_faces()

    def load_known_faces(self):
        """Ma'lum yuz encodinglarini yuklash."""
        encodings, users = [], []
        for face in FaceEncoding.objects.select_related('user').all():
            try:
                encoding = np.array(face.encoding, dtype=np.float32)
                if encoding.shape == (512,):
                    encodings.append(encoding)
                    users.append(face.user)
            except Exception as e:
                logger.error(f"Yuz yuklash xatoligi: {e}")
        return np.array(encodings, dtype=np.float32), users

    def cosine_similarity(self, emb1, emb2):
        """Ikkita embedding o‘rtasidagi kosinus o‘xshashligini hisoblash."""
        emb1 = np.array(emb1)
        emb2 = np.array(emb2)
        return np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))

    def process_frame(self, frame):
        """Kadrni qayta ishlab, yuzlarni aniqlash va taqqoslash."""
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        faces = self.face_app.get(rgb)
        results = []

        for face in faces:
            embedding = np.array(face.embedding, dtype=np.float32)
            best_match = None
            best_similarity = -1

            if self.known_encodings.shape[0] == 0:
                continue

            for idx, known_encoding in enumerate(self.known_encodings):
                similarity = self.cosine_similarity(embedding, known_encoding)
                if similarity > best_similarity and similarity > self.similarity_threshold:
                    best_similarity = similarity
                    best_match = self.known_users[idx]

            if best_match:
                print(f"👤 Tanildi: {best_match.full_name} (O‘xshashlik: {best_similarity:.2f})")
                self.log_recognition(best_match, frame, face)
                results.append((best_match, best_similarity))

        return results

    def log_recognition(self, user, frame, face):
        """Yuz aniqlanganda log va snapshot yozish."""
        try:
            timestamp = now().strftime('%Y%m%d_%H%M%S')
            image_name = f"recognized/{user.id}_{timestamp}.jpg"
            _, buffer = cv2.imencode('.jpg', frame)
            image_file = ContentFile(buffer.tobytes(), name=image_name)

            landmarks = {
                f"p{i}": [float(p[0]), float(p[1])] for i, p in enumerate(face.kps)
            } if face.kps is not None else {}

            camera = get_current_camera()

            FaceRecognitionLog.objects.create(
                user=user,
                camera=camera,
                captured_image=image_file,
                emotion={},
                landmarks=landmarks,
                detected_at=now()
            )

            FaceSnapshot.objects.create(
                user=user,
                camera=camera,
                image=image_file
            )

            Attendance.objects.get_or_create(
                user=user,
                date=now().date(),
                defaults={'check_in_time': now()}
            )

            logger.info(f"Yuz aniqlandi: {user.full_name}, o‘xshashlik: {best_similarity:.2f}")
        except Exception as e:
            logger.error(f"Log yozishda xato: {str(e)}")

    def start(self):
        """Yuz aniqlash jarayonini orqa fonda boshlash."""
        if self.running:
            logger.warning("FaceRecognizer allaqachon ishlamoqda.")
            return

        self.running = True
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()
        logger.info("FaceRecognizer boshlandi.")

    def stop(self):
        """Yuz aniqlashni to‘xtatish."""
        self.running = False
        if self.thread:
            self.thread.join()
        logger.info("FaceRecognizer to‘xtatildi.")

    def run(self):
        """Asosiy yuz aniqlash tsikli."""
        while self.running:
            camera = get_camera_instance()
            if not camera:
                logger.warning("Kamera topilmadi, qayta urinish...")
                time.sleep(5)
                continue

            frame = camera.get_frame()
            if frame is None:
                logger.warning("Kadr o‘qilmadi, qayta urinish...")
                time.sleep(1)
                continue

            results = self.process_frame(frame)

            time.sleep(0.1)

        camera = get_camera_instance()
        if camera:
            camera.stop()
        logger.info("Yuz aniqlash tsikli yakunlandi.")