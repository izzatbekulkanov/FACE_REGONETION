import json

from django.shortcuts import render
from django.core.paginator import Paginator
import time, datetime

from django.http import JsonResponse
from django.utils.timezone import now
from django.views import View
from asgiref.sync import sync_to_async
from users.utils.api_requests import fetch_employees_from_api
from users.models import CustomUser, FaceEncoding
from users.utils.format_data import convert_timestamp_to_date
from users.utils.image_utils import fetch_and_save_image
import face_recognition


def get_user_page(request):
    search_query = request.GET.get("q", "").strip()  # Qidiruv so‘rovi
    page_number = request.GET.get("page", 1)  # Hozirgi sahifa

    users = CustomUser.objects.all()

    # Agar qidiruv bo‘lsa, filterlash
    if search_query: users = users.filter(full_name__icontains=search_query)  # Foydalanuvchi nomiga ko‘ra qidirish

    # Pagination (har bir sahifada 10 ta foydalanuvchi)
    paginator = Paginator(users, 50)
    page_obj = paginator.get_page(page_number)

    return render(request, "users/users.html", {
        "users": page_obj,
        "search_query": search_query
    })


class FetchEmployeesView(View):
    """ 🔄 API orqali hodimlarni yuklash va bazaga qo‘shish """

    async def get(self, request):
        print("\n🔄 [START] Hodimlarni yuklash boshlandi...\n")

        employees_saved = 0

        # ✅ API dan xodimlarni yuklab olish (ASYNC)
        employees, total_count = await sync_to_async(fetch_employees_from_api)()

        if not employees or total_count == 0:
            print("❌ [ERROR] API dan ma'lumot olishda xatolik!")
            return JsonResponse({"success": False, "message": "❌ API ma'lumot olishda xatolik!", "progress": 0},
                                status=500)

        page_size = len(employees)
        total_pages = (total_count // page_size) + (1 if total_count % page_size else 0)

        print(f"📊 [INFO] Jami foydalanuvchilar: {total_count}, Sahifalar soni: {total_pages}")

        for page in range(1, total_pages + 1):
            print(f"\n📥 [PAGE {page}] - Hodimlar yuklanmoqda...")

            # ✅ Asinxron API chaqiruv
            employees, _ = await sync_to_async(fetch_employees_from_api)(page=page)
            if not employees:
                print(f"⚠️ [PAGE {page}] - API dan ma'lumot kelmadi!")
                break

            for emp in employees:
                try:
                    print(f"🔍 [CHECK] Foydalanuvchi ID: {emp['id']} - {emp.get('full_name', 'Noma’lum')}")

                    # 🔄 Tug‘ilgan sanani to‘g‘ri formatga o‘tkazish
                    birth_date = None
                    if emp.get("birth_date"):
                        if isinstance(emp["birth_date"], str):
                            try:
                                birth_date = datetime.date.fromisoformat(emp["birth_date"])
                            except ValueError:
                                birth_date = None
                        elif isinstance(emp["birth_date"], int):
                            birth_date = convert_timestamp_to_date(emp["birth_date"])

                    # ✅ Foydalanuvchi mavjudligini tekshirish yoki yaratish (ASYNC)
                    user, created = await sync_to_async(CustomUser.objects.update_or_create, thread_sensitive=True)(
                        email=f"{emp.get('short_name', 'user').replace(' ', '').lower()}@namspi.uz",
                        defaults={
                            "full_name": emp.get("full_name", "Noma’lum"),
                            "username": emp.get("short_name", "").replace(" ", "_").lower(),
                            "phone_number": f"99899{emp['id']:06}",
                            "birth_date": birth_date,
                            "gender": "male" if emp.get("gender", {}).get("code") == "11" else "female",
                            "department": emp.get("department", {}).get("name"),
                            "position": emp.get("staffPosition", {}).get("name"),
                            "is_teacher": True if emp.get("employeeType", {}).get("code") == "12" else False,
                        }
                    )

                    if created:
                        print(f"✅ [NEW] Yangi foydalanuvchi yaratildi: {user.full_name} ({user.email})")
                    else:
                        print(f"♻️ [UPDATE] Mavjud foydalanuvchi yangilandi: {user.full_name} ({user.email})")

                    # ✅ Foydalanuvchi rasmi mavjud bo‘lsa, uni yuklab olish va saqlash
                    image_url = emp.get("image")
                    if image_url and created:
                        print(f"📸 [IMAGE] Rasm yuklanmoqda: {image_url}")

                        file_name, _ = await sync_to_async(fetch_and_save_image)(image_url, emp["id"])
                        if file_name:
                            user.face_image.name = file_name
                            await sync_to_async(user.save, thread_sensitive=True)()
                            print(f"🖼 [SAVED] Rasm saqlandi: {file_name}")
                        else:
                            print(f"⚠️ [ERROR] Rasm yuklashda xatolik: {image_url}")

                    employees_saved += 1

                    # **✅ PROGRESS yangilashni async ishlatish kerak**
                    if employees_saved % 10 == 0:
                        await sync_to_async(self.update_progress)(request, employees_saved, total_count)

                except Exception as e:
                    print(f"❌ [ERROR] Foydalanuvchi ID {emp['id']} saqlashda xatolik: {e}")

            time.sleep(0.5)

        await sync_to_async(self.update_progress)(request, total_count, total_count)  # **Jarayon yakunlandi**
        print("\n✅ [COMPLETE] Barcha foydalanuvchilar yuklandi!\n")
        return JsonResponse(
            {"success": True, "message": f"✅ {employees_saved} ta foydalanuvchi yuklandi!", "progress": 100})

    def update_progress(self, request, saved, total):
        """📊 **Progressni saqlash uchun asinxron yordamchi funksiya**"""
        try:
            progress = round((saved / total) * 100, 2)
            request.session["progress"] = progress
            request.session.modified = True
            print(f"📊 [PROGRESS] Yuklash jarayoni: {progress}%")
        except Exception as e:
            print(f"❌ [SESSION ERROR] Progress saqlashda xatolik: {e}")


class FetchEmployeesProgressView(View):
    """📊 Foydalanuvchilar yuklanish progressini qaytarish"""

    def get(self, request):
        progress = request.session.get("progress", 0)
        print(f"📊 [PROGRESS CHECK] Hozirgi progress: {progress}%")
        return JsonResponse({"progress": progress})


# 📊 **Progressni global obyekt sifatida saqlash**
progress_data = {"progress": 0}


class CreateAllFaceEncodings(View):
    """📌 Barcha foydalanuvchilar uchun `FaceEncoding` yaratish yoki yangilash"""

    async def get(self, request):
        global progress_data  # 📊 Global progressni olish
        print("🔄 [START] Foydalanuvchilar uchun encoding yaratish boshlandi...")

        users = await sync_to_async(list)(CustomUser.objects.all())  # 🔄 Barcha foydalanuvchilarni olish
        total_users = len(users)
        encodings_created = 0
        encodings_updated = 0
        errors = 0

        print(f"🔹 [INFO] Umumiy foydalanuvchilar soni: {total_users}")

        if total_users == 0:
            progress_data["progress"] = 100  # Hech qanday foydalanuvchi bo‘lmasa progressni 100% qilish
            return JsonResponse({"success": False, "message": "⚠️ Foydalanuvchilar topilmadi!"})

        for index, user in enumerate(users, start=1):
            if user.face_image:
                print(f"📸 [PROCESS] {index}/{total_users} - {user.full_name} uchun encoding yaratilmoqda...")

                face_encoding, landmarks = await sync_to_async(self.generate_face_encoding)(user)

                if face_encoding:
                    # 🔄 FaceEncoding obyektini yaratish yoki yangilash
                    face_encoding_obj, created = await sync_to_async(FaceEncoding.objects.update_or_create,
                                                                     thread_sensitive=True)(
                        user=user,
                        defaults={
                            "encoding": face_encoding,
                            "face_landmarks": landmarks
                        }
                    )
                    if created:
                        encodings_created += 1
                        print(f"✅ [SUCCESS] Yangi encoding yaratildi: {user.full_name}")
                    else:
                        encodings_updated += 1
                        print(f"🔄 [UPDATE] Encoding yangilandi: {user.full_name}")
                else:
                    errors += 1
                    print(f"❌ [ERROR] {user.full_name} uchun yuz kodlashda xatolik!")

            # 📊 **Progressni hisoblash va yangilash**
            progress_data["progress"] = round((index / total_users) * 100, 2)
            print(f"📊 [PROGRESS] {progress_data['progress']}% yakunlandi")

        progress_data["progress"] = 100  # ✅ **Jarayon tugadi**
        print("✅ [FINISHED] Encoding yaratish jarayoni yakunlandi!")
        print(f"📊 [RESULT] Yangi yaratildi: {encodings_created}, Yangilandi: {encodings_updated}, Xatoliklar: {errors}")

        return JsonResponse({
            "success": True,
            "message": f"{encodings_created} ta yangi encoding yaratildi, {encodings_updated} ta yangilandi, {errors} ta xatolik yuz berdi!",
            "progress": 100
        })

    def generate_face_encoding(self, user):
        """📌 Foydalanuvchi rasmidan encoding yaratish"""
        try:
            image_path = user.face_image.path  # 📸 Rasm yo‘li
            print(f"📥 [LOAD] Rasm yuklanmoqda: {image_path}")

            image = face_recognition.load_image_file(image_path)
            encodings = face_recognition.face_encodings(image)
            face_landmarks_list = face_recognition.face_landmarks(image)

            if encodings:
                print(f"🔹 [INFO] Encoding yaratildi: {user.full_name}")
                return json.dumps(encodings[0].tolist()), face_landmarks_list[0] if face_landmarks_list else None
            else:
                print(f"❌ [ERROR] Encoding topilmadi: {user.full_name}")
        except Exception as e:
            print(f"❌ [ERROR] {user.full_name} yuz kodlashda xatolik: {e}")

        return None, None


class CreateFaceEncodingProgressView(View):
    """📊 Face encoding yaratish progressini qaytarish"""

    def get(self, request):
        global progress_data
        print(f"📊 [PROGRESS] Face encoding progress: {progress_data['progress']}%")
        return JsonResponse({"progress": progress_data["progress"]})


class DeleteAllUsersView(View):
    """🗑 Superuserdan tashqari barcha foydalanuvchilarni o‘chirish"""

    async def delete(self, request):
        non_superusers = await sync_to_async(list)(CustomUser.objects.filter(is_superuser=False))

        if not non_superusers:
            return JsonResponse({"success": False, "message": "🛑 O‘chiriladigan foydalanuvchilar topilmadi!"},
                                status=400)

        deleted_count, _ = await sync_to_async(CustomUser.objects.filter(is_superuser=False).delete)()

        return JsonResponse({"success": True, "message": f"✅ {deleted_count} ta foydalanuvchi o‘chirildi!"})
