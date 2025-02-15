import os
import json
import cv2
import face_recognition
import numpy as np
import requests
from django.utils.timezone import now
from concurrent.futures import ThreadPoolExecutor
from users.models import CustomUser, FaceEncoding, FaceRecognitionLog
from face_app.utils.emotion_detection import analyze_emotion, enhance_face

# ✅ Telegram bot ma'lumotlari
BOT_TOKEN = "7956587996:AAGMHkx5iYmcCjND0Y-aKLnmwC-A4qCOlQI"
CHANNEL_ID = "@namspi_psychological"

# ✅ Paralel ishlash uchun ThreadPool
executor = ThreadPoolExecutor(max_workers=2)

# 📂 Rasm saqlanadigan katalog
FACE_DIR = "media/detected_faces/"

# ✅ Katalog mavjudligini tekshirish va yaratish
if not os.path.exists(FACE_DIR):
    os.makedirs(FACE_DIR)
    print(f"📂 [INFO] `{FACE_DIR}` katalogi yaratildi!")


def send_to_telegram(user_name, detected_at, emotion, image_path):
    """ 📤 Telegram kanalga foydalanuvchi natijalarini rasm bilan yuborish """
    if not os.path.exists(image_path):
        print(f"🚨 [ERROR] Rasm topilmadi: {image_path}")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    message = (
        f"📊 *Foydalanuvchi: {user_name}*\n"
        f"🕒 *Vaqt:* {detected_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"😊 *Emotion:* {emotion}\n"
    )

    with open(image_path, "rb") as photo:
        data = {
            "chat_id": CHANNEL_ID,
            "caption": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, data=data, files={"photo": photo})

    if response.status_code == 200:
        print(f"✅ {user_name} uchun Telegram kanalga yuborildi!")
    else:
        print(f"🚨 Telegram xato ({user_name}): {response.text}")


def detect_face(frame):
    """
    📷 Kameradan kelayotgan tasvirda foydalanuvchini tanib olish va hissiy holatni aniqlash.
    """
    # 🎥 OpenCV tasvirni RGB formatga o'tkazish
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # 🔹 Yuzlarni aniqlash
    face_locations = face_recognition.face_locations(rgb_frame, model="hog")

    # 🔹 Yuz kodlashni parallellashtirish
    future_encodings = executor.submit(face_recognition.face_encodings, rgb_frame, face_locations)
    face_encodings = future_encodings.result()

    recognized_users = []

    for face_encoding, (top, right, bottom, left) in zip(face_encodings, face_locations):
        users = FaceEncoding.objects.exclude(encoding=None)

        best_match = None
        best_distance = float("inf")

        for user_enc in users:
            try:
                # ✅ JSONField ichidan saqlangan encodingni numpy float64 turiga o'tkazamiz
                known_encoding = np.array(json.loads(user_enc.encoding), dtype=np.float64)

                # 🔹 Masofani hisoblashni optimallashtirish
                face_distance = np.linalg.norm(known_encoding - face_encoding)

                if face_distance < 0.5 and face_distance < best_distance:
                    best_match = user_enc.user
                    best_distance = face_distance

            except Exception as e:
                print(f"❌ [ERROR] Encodingni float turiga o‘tkazishda xatolik: {e}")

        detected_at = now()
        image_filename = f"{best_match.username if best_match else 'unknown'}_{detected_at.strftime('%Y%m%d_%H%M%S')}.jpg"
        image_path = os.path.join(FACE_DIR, image_filename)

        if best_match:
            # ✅ Yuz tasvirini olish
            face_roi = frame[top:bottom, left:right]

            # 🎨 GAN bilan yaxshilash
            enhanced_face = enhance_face(face_roi)

            # 🧠 Emotionni aniqlash
            emotion_result = analyze_emotion(enhanced_face)

            # 📸 Rasmni saqlash
            cv2.imwrite(image_path, face_roi)

            # 🔄 Log saqlash (agar allaqachon kun davomida saqlanmagan bo‘lsa)
            if not FaceRecognitionLog.objects.filter(user=best_match, detected_at__date=now().date()).exists():
                FaceRecognitionLog.objects.create(
                    user=best_match,
                    detected_at=detected_at,
                    emotion=json.dumps(emotion_result),  # JSON formatida saqlash
                    face_landmarks=None
                )

                # 📤 Telegramga natijalarni yuborish
                send_to_telegram(best_match.full_name, detected_at, emotion_result, image_path)

            recognized_users.append((best_match.full_name, (top, right, bottom, left), emotion_result, "green"))

        else:
            # 🚨 Noma'lum shaxs (qizil ramka)
            cv2.imwrite(image_path, frame[top:bottom, left:right])

            # 📤 Telegramga noma'lum shaxs haqida xabar yuborish
            send_to_telegram("Noma'lum shaxs", detected_at, "❗ Noma'lum", image_path)

            recognized_users.append(("Noma'lum shaxs", (top, right, bottom, left), "❗ Noma'lum", "red"))

    return recognized_users
