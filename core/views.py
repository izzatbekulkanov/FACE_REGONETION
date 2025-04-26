import threading
import math
from datetime import timedelta
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from face_recognition_project import settings
from .generator import gen
from .models import CustomUser, FaceRecognitionLog, FaceEncoding, FaceSnapshot
import time
from django.views.decorators.csrf import csrf_exempt
import traceback
import cv2
from django.db.models import Q
import gc
import os
from .utils.employee_sync import sync_employees_from_api
import logging
from insightface.app import FaceAnalysis
from django.views.generic import ListView
from django.utils.timezone import now


def get_snapshot_video_url(self):
    if self.video:
        return self.video.url if self.video.url.startswith('/') else settings.MEDIA_URL + self.video.name
    return ''

class FaceRecognitionLogListView(ListView):
    model = FaceRecognitionLog
    template_name = 'index.html'
    context_object_name = 'logs'
    paginate_by = 10

    def get_queryset(self):
        today = now().date()
        query = Q(detected_at__date=today)

        search = self.request.GET.get('search')
        if search:
            query &= Q(user__full_name__icontains=search)

        day_filter = self.request.GET.get('day')
        if day_filter == 'yesterday':
            yesterday = today - timedelta(days=1)
            query = Q(detected_at__date=yesterday)

        return FaceRecognitionLog.objects.select_related('user').filter(query).order_by('-detected_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['users_count'] = CustomUser.objects.count()
        context['logs_count'] = self.get_queryset().count()
        return context

def latest_logs(request):
    today = now().date()

    logs = FaceRecognitionLog.objects.filter(
        detected_at__date=today
    ).select_related('user').order_by('-detected_at')[:1]

    if logs:
        log = logs[0]
        user = log.user

        snapshot = FaceSnapshot.objects.filter(user=user).order_by('-created_at').first()

        return JsonResponse({
            'id': log.id,
            'full_name': user.full_name,
            'position': user.position,
            'department': user.department,
            'institute': user.institute,
            'detected_at': log.detected_at.strftime('%Y-%m-%d %H:%M:%S'),
            'image': snapshot.image.url if snapshot and snapshot.image else '',
            'video': snapshot.video.url if snapshot and snapshot.video else '',
        })

    return JsonResponse({}, status=204)

# Global o'zgaruvchi progressni ushlab turish uchun
upload_progress_data = {"current": 0, "total": 0}

def staff_list(request):
    query = request.GET.get('q', '')
    staff = CustomUser.objects.filter(
        Q(full_name__icontains=query) | Q(email__icontains=query),
        is_teacher=True
    ).order_by('-date_joined')

    paginator = Paginator(staff, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'staff_list.html', {
        'staff_list': page_obj,
        'query': query,
        'total_count': staff.count()
    })


def upload_progress(request):
    return JsonResponse(upload_progress_data)


def upload_employees(request):
    def run_sync():
        upload_progress_data.update({"current": 0, "total": 0, "done": False})
        sync_employees_from_api(upload_progress_data)

    threading.Thread(target=run_sync).start()
    return JsonResponse({"status": "started"})

logger = logging.getLogger(__name__)

# InsightFace ilovasi faqat bir marta yaratiladi
insight_app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
insight_app.prepare(ctx_id=0)

encoding_progress_data = {
    "current": 0,
    "total": 0,
    "is_processing": False,
    "last_error": "",
}

@csrf_exempt
def create_encodings(request):
    global encoding_progress_data

    if encoding_progress_data["is_processing"]:
        return JsonResponse({"status": "error", "message": "Jarayon allaqachon boshlangan."})

    try:
        users = list(CustomUser.objects.filter(face_image__isnull=False))
        total_users = len(users)

        encoding_progress_data.update({
            "total": total_users,
            "current": 0,
            "is_processing": True,
            "last_error": "",
        })

        print(f"\n👥 Foydalanuvchilar soni: {total_users}")
        logger.info(f"Foydalanuvchilar soni: {total_users}")

        batch_size = 20
        num_batches = math.ceil(total_users / batch_size)

        for batch_index in range(num_batches):
            print(f"\n📦 Batch {batch_index + 1} ishga tushdi")
            logger.info(f"Batch {batch_index + 1} ishga tushdi")

            start = batch_index * batch_size
            end = min(start + batch_size, total_users)
            batch_users = users[start:end]

            for user in batch_users:
                try:
                    full_name = user.full_name or "[ISMSIZ]"
                    print(f"🔄 {encoding_progress_data['current'] + 1}/{total_users} | {full_name}")

                    if not user.face_image or not user.face_image.path or not os.path.exists(user.face_image.path):
                        msg = f"⚠️ Rasm yo‘q: {full_name}"
                        print(msg)
                        logger.warning(msg)
                        encoding_progress_data["current"] += 1
                        continue

                    print(f"🖼️ Yuklanmoqda: {user.face_image.path}")
                    img = cv2.imread(user.face_image.path)

                    if img is None:
                        msg = f"❌ Rasmni o‘qib bo‘lmadi: {user.face_image.path} | {full_name}"
                        print(msg)
                        logger.error(msg)
                        encoding_progress_data["current"] += 1
                        continue

                    faces = insight_app.get(img)
                    if not faces:
                        msg = f"🚫 Yuz aniqlanmadi: {full_name}"
                        print(msg)
                        logger.warning(msg)
                        encoding_progress_data["current"] += 1
                        continue

                    face = faces[0]
                    encoding = [float(x) for x in face.embedding]

                    landmarks = {}
                    if hasattr(face, 'kps') and face.kps is not None:
                        landmarks = {
                            f"p{i}": [float(p[0]), float(p[1])]
                            for i, p in enumerate(face.kps)
                        }

                    FaceEncoding.objects.update_or_create(
                        user=user,
                        defaults={
                            "encoding": encoding,
                            "landmarks": landmarks
                        }
                    )
                    msg = f"✅ Yaratildi: {full_name}"
                    print(msg)
                    logger.info(msg)

                except Exception as e:
                    err_msg = f"❌ Xatolik {user.id} ({user.full_name}): {str(e)}"
                    print(err_msg)
                    logger.error(err_msg)
                    traceback.print_exc()
                    encoding_progress_data["last_error"] = err_msg

                encoding_progress_data["current"] += 1
                gc.collect()
                time.sleep(0.01)

            gc.collect()
            time.sleep(0.5)

        print("\n🎉 Barcha encodinglar yakunlandi!")
        logger.info("Barcha encodinglar yakunlandi.")
        encoding_progress_data["is_processing"] = False

        return JsonResponse({
            "status": "success",
            "total_processed": total_users,
            "last_error": encoding_progress_data["last_error"]
        })

    except Exception as e:
        err_msg = f"🚨 Umumiy xatolik: {e}"
        print(err_msg)
        logger.error(err_msg)
        traceback.print_exc()
        encoding_progress_data.update({
            "is_processing": False,
            "last_error": err_msg
        })
        return JsonResponse({"status": "error", "message": err_msg})

def encoding_progress(request):
    return JsonResponse(encoding_progress_data)
