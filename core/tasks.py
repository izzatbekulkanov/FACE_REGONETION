import time
import numpy as np
import cv2
from insightface.app import FaceAnalysis
from .models import Camera, FaceEncoding, FaceRecognitionLog, FaceSnapshot
from django.utils.timezone import now
from background_task import background

known_encodings = []
known_users = []
last_seen_users = {}

def load_known_faces():
    global known_encodings, known_users
    known_encodings = []
    known_users = []

    for face in FaceEncoding.objects.select_related('user').all():
        try:
            encoding = np.array(face.encoding, dtype=np.float32)
            if encoding.shape == (512,):
                known_encodings.append(encoding)
                known_users.append(face.user)
        except:
            continue
    known_encodings = np.array(known_encodings, dtype=np.float32)

@background(schedule=1)
def monitor_cameras_background():
    print("📷 [BG] Kamera monitoring ishladi")

    load_known_faces()
    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0)

    active_cameras = Camera.objects.filter(is_active=True)
    for camera in active_cameras:
        try:
            cap = cv2.VideoCapture(camera.source if camera.type != "usb" else int(camera.source))
            ret, frame = cap.read()
            if not ret:
                cap.release()
                continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            faces = app.get(rgb)

            for face in faces:
                embedding = np.array(face.embedding, dtype=np.float32)
                if known_encodings.shape[0] == 0:
                    continue

                distances = np.linalg.norm(known_encodings - embedding, axis=1)
                best_idx = np.argmin(distances)
                best_distance = distances[best_idx]

                if best_distance < 28.0:
                    user = known_users[best_idx]
                    now_ts = time.time()

                    if user.id not in last_seen_users or now_ts - last_seen_users[user.id] > 20:
                        FaceRecognitionLog.log_recognition(user, camera=camera)
                        save_snapshot(user, frame, camera)
                        last_seen_users[user.id] = now_ts
                        print(f"✅ Aniqlangan: {user.full_name}")

            cap.release()

        except Exception as e:
            print(f"❌ Kamera xatosi: {e}")

def save_snapshot(user, frame, camera):
    from django.core.files.base import ContentFile
    import io

    snapshots = FaceSnapshot.objects.filter(user=user).order_by('-created_at')
    if snapshots.count() >= 10:
        for s in snapshots[10:]:
            s.image.delete(save=False)
            s.delete()

    filename = f"{user.id}_{int(time.time())}.jpg"
    path = f"snapshots/{filename}"
    retval, buffer = cv2.imencode('.jpg', frame)
    content = ContentFile(buffer.tobytes())

    snapshot = FaceSnapshot(user=user, camera=camera)
    snapshot.image.save(path, content, save=True)
