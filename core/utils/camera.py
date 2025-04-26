# camera.py (Django views for IP kamera tizimi - yangicha login modalga asoslangan)
import asyncio
import json
import re
import subprocess
import ipaddress
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

from asgiref.sync import sync_to_async
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from ..models import Camera
from starlette.responses import StreamingResponse

@require_GET
def get_camera_info(request, ip):
    print(f"🛜 [get_camera_info] So'rov olindi | IP: {ip}")
    try:
        cam = get_object_or_404(Camera, source=ip)
        print(f"✅ [get_camera_info] Kamera topildi: {cam.name}")
        return JsonResponse({
            'id': cam.id,
            'name': cam.name,
            'type': cam.type,
            'source': cam.source,
            'is_active': cam.is_active,
            'selected': cam.selected,
            'username': cam.username,
            'password': cam.password
        })
    except Exception as e:
        print(f"❌ [get_camera_info] Kamera topilmadi yoki xatolik: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_POST
def save_camera(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        name = data.get('name')
        cam_type = data.get('type')
        source = data.get('source')
        username = data.get('username')
        password = data.get('password')

        if not (username and password):
            return JsonResponse({'status': 'error', 'message': 'Username va parol kiritilishi shart!'}, status=400)

        if cam_type == 'ip':
            if not re.match(r'^\d{1,3}(\.\d{1,3}){3}$', source):
                return JsonResponse({'status': 'error', 'message': 'IP manzil noto‘g‘ri!'}, status=400)

        if Camera.objects.filter(type=cam_type, source=source).exists():
            return JsonResponse({'status': 'error', 'message': 'Bu kamera allaqachon saqlangan!'}, status=400)

        camera = Camera(
            name=name,
            type=cam_type,
            source=source,
            username=username,
            password=password
        )
        camera.save()

        return JsonResponse({'status': 'ok', 'message': 'Kamera muvaffaqiyatli saqlandi'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Xatolik: {str(e)}'}, status=500)


@csrf_exempt
@require_POST
def try_custom_login(request):
    try:
        data = json.loads(request.body.decode('utf-8'))
        ip = data.get("ip")
        username = data.get("username")
        password = data.get("password")
        rtsp_url = f"rtsp://{username}:{password}@{ip}:554"
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-rtsp_transport', 'tcp', '-i', rtsp_url
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=4, text=True)

        if "401 Unauthorized" in result.stderr or "Connection refused" in result.stderr:
            return JsonResponse({'status': 'error', 'message': 'Login yoki parol noto‘g‘ri'})
        return JsonResponse({'status': 'ok', 'message': 'Ulanish muvaffaqiyatli'})
    except subprocess.TimeoutExpired:
        return JsonResponse({'status': 'error', 'message': 'Kamera javob bermadi'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


@csrf_exempt
@require_POST
def toggle_camera_active(request, pk):
    try:
        cam = get_object_or_404(Camera, id=pk)
        cam.toggle_active()
        return JsonResponse({'status': 'ok', 'is_active': cam.is_active})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_POST
def toggle_camera_selected(request, pk):
    try:
        Camera.objects.all().update(selected=False)
        cam = get_object_or_404(Camera, id=pk)
        cam.selected = True
        cam.save()
        return JsonResponse({'status': 'ok', 'selected': cam.selected})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def generate_ffmpeg_stream(ip, username, password, stream_type="main"):
    print("\n================ 📡 [generate_ffmpeg_stream] Boshlanishi ================\n")
    try:
        # 1. Stream turi aniqlanadi (main yoki sub)
        channel_id = "101" if stream_type == "main" else "102"
        print(f"🔎 Stream turi: {stream_type} (channel_id={channel_id})")

        # 2. Username va password URL uchun tayyorlanadi
        username_encoded = urllib.parse.quote(username)
        password_encoded = urllib.parse.quote(password)
        print(f"🔐 Username (encoded): {username_encoded}")
        print(f"🔐 Password (encoded): {password_encoded}")

        # 3. RTSP URL yasash
        rtsp_url = f"rtsp://{username_encoded}:{password_encoded}@{ip}:554/Streaming/Channels/{channel_id}/"
        print(f"🔗 RTSP URL: {rtsp_url}")

        # 4. ffmpeg komandasi tayyorlanadi
        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-f", "mjpeg",
            "-q", "5",
            "-r", "25",
            "-"
        ]
        print(f"⚙️ FFMPEG komandasi: {' '.join(cmd)}")

        # 5. ffmpeg jarayonini boshlaymiz
        pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10**8)
        print("✅ FFMPEG jarayoni muvaffaqiyatli ishga tushdi")

        # 6. Stream generator funksiya
        def stream():
            try:
                while True:
                    chunk = pipe.stdout.read(4096)
                    if not chunk:
                        print("⚠️ [stream] Pipe stdout bo'sh - oqim tugadi yoki uzildi")
                        break
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + chunk + b"\r\n")
            except Exception as e:
                print(f"❌ [stream] Stream davomida xatolik: {e}")
            finally:
                print("🛑 [stream] FFMPEG jarayonini to'xtatyapmiz")
                pipe.kill()

        print("\n================ 📡 [generate_ffmpeg_stream] Tugadi ================\n")

        # 7. stream(), err=None, va pipe obyektni qaytaramiz
        return stream, None, pipe

    except Exception as e:
        print(f"💥 [generate_ffmpeg_stream] Umumiy xatolik: {e}")
        print("\n================ 📡 [generate_ffmpeg_stream] Xatolikda tugadi ================\n")
        return None, str(e), None


async def async_stream(pipe):
    try:
        jpeg_start = b'\xff\xd8'
        jpeg_end = b'\xff\xd9'
        buffer = b''

        while True:
            chunk = await asyncio.get_running_loop().run_in_executor(None, pipe.stdout.read, 4096)
            if not chunk:
                print("⚠️ [async_stream] Pipe stdout bo'sh - oqim tugadi yoki uzildi")
                break

            buffer += chunk
            start = buffer.find(jpeg_start)
            end = buffer.find(jpeg_end)

            if start != -1 and end != -1 and end > start:
                frame = buffer[start:end + 2]
                buffer = buffer[end + 2:]

                multipart_frame = (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" +
                    frame +
                    b"\r\n"
                )

                yield multipart_frame
    except Exception as e:
        print(f"❌ [async_stream] Stream davomida xatolik: {e}")
    finally:
        print("🛑 [async_stream] FFMPEG jarayonini to'xtatyapmiz")
        pipe.kill()


# Kamera oqimi view
@csrf_exempt
async def camera_stream_mjpeg(request, ip):
    print("\n================ 🎥 [camera_stream_mjpeg] Boshlanishi ================\n")
    print(f"🛜 Oqim so'rovi qabul qilindi | IP: {ip}")

    try:
        camera = await sync_to_async(get_object_or_404)(Camera, source=ip)
        username = camera.username or "admin"
        password = camera.password or "Qwerty@1234560"
        print(f"✅ Kamera bazadan topildi: {camera.name} (username: {username})")
    except Camera.DoesNotExist:
        print("⚠️ Kamera topilmadi, GET parametrlaridan olamiz")
        username = request.GET.get("username", "admin")
        password = request.GET.get("password", "Qwerty@1234560")

    stream_type = request.GET.get("stream", "main").lower()
    if stream_type not in ["main", "sub"]:
        print(f"⚠️ Noto'g'ri stream_type '{stream_type}', 'main' qilib belgilayapmiz")
        stream_type = "main"
    else:
        print(f"🔎 So'ralgan stream turi: {stream_type}")

    print("🔧 Oqim tayyorlash uchun generate_ffmpeg_stream chaqirilmoqda...")

    stream_func, err, pipe = generate_ffmpeg_stream(ip, username, password, stream_type)

    if stream_func and pipe:
        print("✅ Stream generator tayyorlandi, StreamingHttpResponse yuborilmoqda")
        print("\n================ 🎥 [camera_stream_mjpeg] Tugadi ================\n")

        # Django StreamingHttpResponse bilan qaytaramiz
        response = StreamingHttpResponse(
            async_stream(pipe),
            content_type='multipart/x-mixed-replace; boundary=frame'
        )
        return response

    print(f"❌ Stream tayyorlanmadi: {err}")
    print("\n================ 🎥 [camera_stream_mjpeg] Xatolikda tugadi ================\n")
    from django.http import HttpResponse
    return HttpResponse(f"❌ Kamera oqimi mavjud emas: {err}", status=404)

def try_rtsp_login(ip):
    return {'ip': ip, 'info': 'Aniqlandi'}  # Faqat aniqlangan deb qaytariladi


def scan_rtsp_enabled_cameras_parallel(subnet='10.10.4.0/24', max_threads=40):
    net = ipaddress.ip_network(subnet, strict=False)
    ip_list = [str(ip) for ip in net.hosts()]
    cameras = []
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = {executor.submit(try_rtsp_login, ip): ip for ip in ip_list}
        for future in as_completed(futures):
            result = future.result()
            if result:
                cameras.append(result)
    return cameras


def camera_list(request):
    return render(request, 'camera_list.html')


def ajax_camera_list(request):
    cameras = list(Camera.objects.all().order_by('-created_at').values(
        'id', 'name', 'type', 'source', 'is_active', 'selected'))
    ip_cameras = scan_rtsp_enabled_cameras_parallel('10.10.4.0/24')
    return JsonResponse({'cameras': cameras, 'ip_cameras': ip_cameras})


@require_POST
@csrf_exempt
def delete_camera(request, pk):
    try:
        cam = get_object_or_404(Camera, id=pk)
        cam.delete()
        return JsonResponse({'status': 'ok', 'message': 'Kamera muvaffaqiyatli o‘chirildi'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Xatolik: {str(e)}'}, status=500)
