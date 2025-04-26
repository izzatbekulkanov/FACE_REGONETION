import cv2
import numpy as np
import threading
import time
from insightface.app import FaceAnalysis
from .models import FaceEncoding, FaceRecognitionLog, Camera, FaceSnapshot
import os

class VideoCamera:
    def __init__(self, camera_obj):
        self.camera = camera_obj
        source = int(camera_obj.source) if camera_obj.type == "usb" else camera_obj.source
        print(f"🎥 Kamera manbasi: {source}")

        self.cap = cv2.VideoCapture(source)
        if not self.cap.isOpened():
            print(f"❌ Kamera ochilmadi: {source}")
            raise Exception(f"Kamera ochilmadi: {source}")
        else:
            print(f"✅ Kamera ochildi: {source}")

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self.app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        self.app.prepare(ctx_id=0)

        self.known_encodings, self.known_users = self.load_known_faces()
        self.last_seen_users = {}
        self.stable_counts = {}
        self.video_writers = {}  # user_id -> {writer, start, path}

        self.frame = None
        self.running = True
        threading.Thread(target=self.update, daemon=True).start()

    def load_known_faces(self):
        encodings, users = [], []
        for face in FaceEncoding.objects.select_related('user').all():
            try:
                encoding = np.array(face.encoding, dtype=np.float32)
                if encoding.shape == (512,):
                    encodings.append(encoding)
                    users.append(face.user)
            except Exception as e:
                print(f"⚠️ Yuz yuklash xatoligi: {e}")
        return np.array(encodings, dtype=np.float32), users

    def update(self):
        while self.running and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                print("🔴 Kamera oqimi yo‘q")
                time.sleep(0.5)
                continue

            self.process_user_videos(frame)
            self.frame = self.process_frame(frame)

    def get_frame(self, jpeg_quality=75):
        if self.frame is not None:
            _, jpeg = cv2.imencode('.jpg', self.frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
            return jpeg.tobytes()
        return None

    def stop(self):
        self.running = False
        self.cap.release()

    def start_user_video(self, user_id):
        timestamp = int(time.time())
        filename = f"video_{user_id}_{timestamp}.mp4"
        path = f"media/videos/{filename}"
        os.makedirs("media/videos", exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        writer = cv2.VideoWriter(path, fourcc, 20, (width, height))
        self.video_writers[user_id] = {'writer': writer, 'start': time.time(), 'path': path}
        return path

    def process_user_videos(self, frame):
        finished_users = []

        for user_id, info in self.video_writers.items():
            if time.time() - info['start'] < 2.0:
                info['writer'].write(frame)
            else:
                info['writer'].release()
                finished_users.append(user_id)

        for user_id in finished_users:
            video_path = self.video_writers[user_id]['path']
            del self.video_writers[user_id]

            user = next((u for u in self.known_users if u.id == user_id), None)
            if user and self.frame is not None:
                self.save_snapshot(user, self.frame, video_path)

    def process_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        faces = self.app.get(rgb)

        for face in faces:
            name = "Noma'lum"
            color = (0, 0, 255)
            embedding = np.array(face.embedding, dtype=np.float32)

            if self.known_encodings.shape[0] == 0:
                continue

            distances = np.linalg.norm(self.known_encodings - embedding, axis=1)
            best_idx = np.argmin(distances)
            best_distance = distances[best_idx]
            second_best = np.partition(distances, 1)[1] if len(distances) > 1 else float('inf')
            confidence_gap = second_best - best_distance

            if best_distance < 30.0 and confidence_gap > 3.5:
                user = self.known_users[best_idx]
                now_ts = time.time()

                count_data = self.stable_counts.get(user.id, {'count': 0, 'last_ts': 0})
                if now_ts - count_data['last_ts'] > 5:
                    count_data['count'] = 0
                count_data['count'] += 1
                count_data['last_ts'] = now_ts
                self.stable_counts[user.id] = count_data

                if count_data['count'] == 3:
                    last_seen = self.last_seen_users.get(user.id)
                    if not last_seen or now_ts - last_seen > 60:
                        try:
                            self.start_user_video(user.id)
                            FaceRecognitionLog.log_recognition(user, camera=self.camera)
                            self.last_seen_users[user.id] = now_ts
                            print(f"✅ Aniqlangan (stabil): {user.full_name} (Masofa: {best_distance:.2f})")
                        except Exception as e:
                            print(f"⚠️ Log/snapshot xatoligi: {e}")

                name = user.full_name
                color = (0, 255, 0)

            x1, y1, x2, y2 = map(int, face.bbox)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label_y = y1 - 10 if y1 - 10 > 10 else y1 + 20
            cv2.putText(frame, name, (x1, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        return frame

    def save_snapshot(self, user, frame, video_path=None):
        snapshots = FaceSnapshot.objects.filter(user=user).order_by('-created_at')
        if snapshots.count() >= 10:
            for s in snapshots[10:]:
                s.image.delete(save=False)
                if s.video:
                    s.video.delete(save=False)
                s.delete()

        timestamp = int(time.time())
        os.makedirs("media/snapshots", exist_ok=True)
        image_filename = f"snapshot_{user.id}_{timestamp}.jpg"
        image_path = f"media/snapshots/{image_filename}"
        cv2.imwrite(image_path, frame)

        FaceSnapshot.objects.create(
            user=user,
            camera=self.camera,
            image=f"snapshots/{image_filename}",
            video=video_path.replace('media/', '') if video_path else None
        )
