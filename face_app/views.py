import cv2
import subprocess
import numpy as np
from django.http import StreamingHttpResponse, JsonResponse
from django.shortcuts import render

from face_app.utils.face_detection import detect_face

# ✅ PTZ Kamera RTSP URL (Parolni URL Encoding qilish esdan chiqmasin!)
PTZ_CAMERA_URL = "rtsp://admin:Qwerty%40123456.@10.10.4.253:554/Streaming/Channels/101"


def get_available_cameras():
    """🟢 PTZ va USB kameralarni avtomatik aniqlash"""
    available_cameras = []

    # ✅ PTZ kamerani tekshiramiz
    print(f"🎥 [INFO] PTZ kamera {PTZ_CAMERA_URL} tekshirilmoqda...")
    cap = cv2.VideoCapture(PTZ_CAMERA_URL, cv2.CAP_FFMPEG)
    if cap.isOpened():
        available_cameras.append("PTZ")
        print("✅ [SUCCESS] PTZ kamera qo‘shildi!")
    else:
        print("🚨 [ERROR] PTZ kamera ulanib bo‘lmadi!")
    cap.release()

    # ✅ USB kameralarni tekshirish
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                available_cameras.append(str(i))
                print(f"✅ [SUCCESS] USB Kamera {i} qo‘shildi!")
        cap.release()

    print(f"📡 [INFO] Topilgan kameralar: {available_cameras}")
    return available_cameras


def generate_frames(camera_index):
    """
    📷 Kamera oqimini olish (PTZ yoki USB) va aniqlangan yuzlarni ramka ichiga olish.
    """
    camera_index = str(camera_index).upper()

    print(f"🔄 [INFO] Kamera ishga tushyapti: {camera_index}")

    if camera_index == "PTZ":
        print(f"🎥 [INFO] PTZ kamera ulanyapti: {PTZ_CAMERA_URL}")
        process = subprocess.Popen(
            [
                "ffmpeg",
                "-rtsp_transport", "tcp",
                "-i", PTZ_CAMERA_URL,
                "-f", "image2pipe",
                "-pix_fmt", "bgr24",
                "-vcodec", "rawvideo",
                "-s", "640x480",  # ✅ Kichik format
                "-"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=10 ** 8
        )
    else:
        try:
            camera_index = int(camera_index)
            print(f"🎥 [INFO] USB Kamera {camera_index} ochilmoqda...")
            camera = cv2.VideoCapture(camera_index)

            if not camera.isOpened():
                print(f"🚨 [ERROR] Kamera {camera_index} ochilmadi! Tekshirib ko‘ring.")
                return

        except ValueError:
            print(f"🚨 [ERROR] Noto‘g‘ri kamera indeksi: {camera_index}")
            return

    while True:
        if camera_index == "PTZ":
            raw_frame = process.stdout.read(640 * 480 * 3)
            if not raw_frame:
                print("🚨 [ERROR] PTZ kameradan tasvir olinmadi!")
                break

            # ✅ PTZ kamera tasvirini `writeable=True` qilish uchun nusxa olish
            frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((480, 640, 3)).copy()

        else:
            success, frame = camera.read()
            if not success:
                print(f"🚨 [ERROR] Kamera {camera_index} tasvirni o‘qiy olmadi!")
                break

        # ✅ **Tasvirni o‘zgaruvchan qilish (endi xatolik bermaydi)**
        frame.flags.writeable = True

        # ✅ Yuzlarni aniqlash
        recognized_users = detect_face(frame)

        for user_name, (top, right, bottom, left), emotion, color in recognized_users:
            if color == "green":
                box_color = (0, 255, 0)  # 🟢 Yashil ramka (Bazadagi foydalanuvchi)
                text_color = (0, 255, 0)
            else:
                box_color = (0, 0, 255)  # 🔴 Qizil ramka (Bazaga kiritilmagan foydalanuvchi)
                text_color = (0, 0, 255)

            # 🔲 Yuzni ramka ichiga olish
            cv2.rectangle(frame, (left, top), (right, bottom), box_color, 2)

            # 🏷 Foydalanuvchi ismi va emotionni ekranga chiqarish
            cv2.putText(frame, user_name, (left, top - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, text_color, 2)
            cv2.putText(frame, emotion, (left, top - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, text_color, 2)

        _, buffer = cv2.imencode(".jpg", frame)
        frame_bytes = buffer.tobytes()

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")

    print(f"🔴 [INFO] Kamera {camera_index} yopilyapti...")

    if camera_index == "PTZ":
        process.terminate()
    else:
        camera.release()
def face_stream(request, camera_id):
    """
    📡 Kamerani translatsiya qilish (PTZ yoki USB)
    """
    camera_id = str(camera_id).upper()  # ✅ Raqam yoki PTZ bo‘lsa, string formatda bo‘lishi kerak

    print(f"📡 [INFO] Kamera stream ochilmoqda: {camera_id}")

    if camera_id == "PTZ":
        return StreamingHttpResponse(generate_frames("PTZ"),
                                     content_type="multipart/x-mixed-replace; boundary=frame")
    else:
        try:
            camera_index = int(camera_id)  # ✅ Agar raqam bo‘lsa, integer formatga o‘tkazamiz
        except ValueError:
            print(f"🚨 [ERROR] Noto‘g‘ri kamera indeksi: {camera_id}")
            return StreamingHttpResponse(b"Xato!", content_type="text/plain")

        return StreamingHttpResponse(generate_frames(camera_index),
                                     content_type="multipart/x-mixed-replace; boundary=frame")


def camera_list(request):
    """
    🎥 Mavjud kameralar ro‘yxatini qaytarish
    """
    cameras = get_available_cameras()
    return JsonResponse({'cameras': cameras})


def face_detection_page(request):
    """
    🖥 Yuzni aniqlash sahifasini yuklash
    """
    return render(request, "face/stream.html")
