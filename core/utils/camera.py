# camera.py (Django views for IP kamera tizimi - yangicha login modalga asoslangan)
import asyncio
import json
import re
import subprocess
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from ..models import Camera
from channels.generic.websocket import AsyncWebsocketConsumer

import urllib.parse


@require_GET
def get_camera_info(request, ip_or_id):
    print(f"🛜 [get_camera_info] So'rov olindi | Parametr: {ip_or_id}")
    try:
        # Parametr raqammi (id) yoki IP manzilmi aniqlaymiz
        is_id = ip_or_id.isdigit()

        if is_id:
            cam = get_object_or_404(Camera, id=int(ip_or_id))
        else:
            cam = get_object_or_404(Camera, source=ip_or_id)

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

        # Kamera mavjudligini tekshirib, yangilash yoki yaratish
        camera, created = Camera.objects.update_or_create(
            type=cam_type,
            source=source,
            defaults={
                'name': name,
                'username': username,
                'password': password
            }
        )

        if created:
            message = "✅ Kamera muvaffaqiyatli saqlandi."
        else:
            message = "✅ Kamera ma'lumotlari yangilandi."

        return JsonResponse({'status': 'ok', 'message': message})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f"Xatolik: {str(e)}"}, status=500)


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


class CameraStreamConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            self.ip = self.scope['url_route']['kwargs']['ip']
            query_params = urllib.parse.parse_qs(self.scope['query_string'].decode())
            self.username = query_params.get('username', ['admin'])[0]
            self.password = query_params.get('password', ['Qwerty@123456.'])[0]

            await self.accept()
            print(f"🟢 WebSocket connect: {self.ip} | Username: {self.username}")

            asyncio.create_task(self.stream_camera())

        except Exception as e:
            print(f"❌ [connect] Xatolik: {e}")
            await self.close()

    async def disconnect(self, close_code):
        print(f"🔴 WebSocket disconnect: {self.ip}")
        if hasattr(self, 'process') and self.process:
            try:
                self.process.kill()
                print(f"🛑 FFMPEG process to‘xtatildi (PID: {self.process.pid})")
            except Exception as e:
                print(f"⚠️ [disconnect] Process kill xatolik: {e}")

    async def stream_camera(self):
        try:
            username_encoded = urllib.parse.quote(self.username, safe='')
            password_encoded = urllib.parse.quote(self.password, safe='')
            rtsp_url = f"rtsp://{username_encoded}:{password_encoded}@{self.ip}:554/cam/realmonitor?channel=1&subtype=0"

            print(f"🔗 RTSP URL: {rtsp_url}")

            cmd = [
                "ffmpeg",
                "-fflags", "nobuffer",
                "-rtsp_transport", "tcp",
                "-i", rtsp_url,
                "-vf", "scale=1280:720",
                "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-b:v", "1500k",
                "-an",
                "-f", "mpegts",
                "-"
            ]
            print(f"⚙️ FFMPEG komandasi tayyorlandi")

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10 ** 8
            )
            print(f"🚀 FFMPEG process ishga tushdi (PID: {self.process.pid})")

            async def read_stdout():
                packet_count = 0
                try:
                    while True:
                        data = await asyncio.get_event_loop().run_in_executor(None, self.process.stdout.read, 4096)
                        if not data:
                            print("⚠️ STDOUT oqimi tugadi")
                            break
                        await self.send(bytes_data=data)
                        packet_count += 1
                        if packet_count % 50 == 0:
                            print(f"📦 Oqim davom etmoqda... ({packet_count * 4} KB uzatildi)")
                except Exception as e:
                    print(f"❌ STDOUT o'qishda xatolik: {e}")

            async def read_stderr():
                last_error = ""
                try:
                    while True:
                        error_line = await asyncio.get_event_loop().run_in_executor(None, self.process.stderr.readline)
                        if not error_line:
                            print("⚠️ STDERR oqimi tugadi")
                            break
                        error_message = error_line.decode(errors='ignore').strip()
                        if error_message and error_message != last_error:
                            last_error = error_message
                            print(f"🛑 FFMPEG STDERR: {error_message}")
                except Exception as e:
                    print(f"❌ STDERR o'qishda xatolik: {e}")

            await asyncio.gather(read_stdout(), read_stderr())

            return_code = self.process.wait()
            if return_code != 0:
                print(f"❌ FFMPEG jarayoni xato kodi bilan yakunlandi: {return_code}")
            else:
                print("✅ FFMPEG jarayoni muvaffaqiyatli tugadi")

        except Exception as e:
            import traceback
            print("\n" + "=" * 80)
            print(f"❌ [stream_camera] YAKUNIY XATOLIK:")
            print("-" * 80)
            print(traceback.format_exc())
            print("=" * 80 + "\n")
        finally:
            if hasattr(self, 'process') and self.process:
                try:
                    self.process.kill()
                    print(f"🛑 [finally] FFMPEG process to‘xtatildi (PID: {self.process.pid})")
                except Exception as e:
                    print(f"⚠️ [finally] Process kill xatolik: {e}")


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
    saved_cameras = Camera.objects.all().order_by('-created_at').values(
        'id', 'name', 'type', 'source', 'is_active', 'selected'
    )
    saved_ips = set(cam['source'] for cam in saved_cameras if cam['type'] == 'ip')

    found_cameras = scan_rtsp_enabled_cameras_parallel('10.10.4.0/24')
    ip_cameras = [cam for cam in found_cameras if cam['ip'] not in saved_ips]

    return JsonResponse({
        'cameras': list(saved_cameras),
        'ip_cameras': ip_cameras
    })


@require_POST
@csrf_exempt
def delete_camera(request, pk):
    try:
        cam = get_object_or_404(Camera, id=pk)
        cam.delete()
        return JsonResponse({'status': 'ok', 'message': 'Kamera muvaffaqiyatli o‘chirildi'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Xatolik: {str(e)}'}, status=500)
