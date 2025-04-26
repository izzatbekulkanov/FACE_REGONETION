import requests
import tempfile
from datetime import datetime
from django.core.files import File
from core.models import CustomUser
from django.utils.text import slugify
from random import randint

API_URL = "https://student.namspi.uz/rest/v1/data/employee-list"
AUTH_TOKEN = "t9MPsdyX_oGFeUbpTxdL9Yy10V_8_Je6"  # .env dan olinsa yaxshi bo'ladi

def sync_employees_from_api(progress_tracker=None):
    page = 1
    limit = 200
    total_saved = 0

    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "accept": "application/json"
    }

    # Mavjud userlarni tekshirish uchun
    existing_usernames = set(CustomUser.objects.values_list("username", flat=True))
    existing_emails = set(CustomUser.objects.values_list("email", flat=True))

    # ✅ Avval sahifalar sonini aniqlaymiz
    first_res = requests.get(API_URL, headers=headers, params={"type": "all", "page": 1, "limit": 1})
    if first_res.status_code != 200:
        return 0

    pagination = first_res.json().get("data", {}).get("pagination", {})
    page_count = pagination.get("pageCount", 1)

    # 🚀 Sahifa bo‘yicha yuramiz
    for page in range(1, page_count + 1):
        res = requests.get(API_URL, headers=headers, params={"type": "all", "page": page, "limit": limit})
        if res.status_code != 200:
            break

        items = res.json().get("data", {}).get("items", [])
        if not items:
            continue

        if progress_tracker:
            progress_tracker["total"] += len(items)

        for emp in items:
            hash_id = emp.get("hash", f"user_{emp['id']}")

            if hash_id in existing_usernames:
                if progress_tracker:
                    progress_tracker["current"] += 1
                continue

            full_name = emp.get("full_name", "").strip()
            print(f"📥 Saqlanmoqda: {full_name}")

            # ✅ Email generatsiya qilish
            raw_email = emp.get("email") or f"{hash_id}@namspi.uz"
            email = raw_email
            while email in existing_emails:
                prefix = slugify(full_name.split()[0]) or "user"
                email = f"{prefix}{randint(1000, 9999)}@namspi.uz"
            existing_emails.add(email)

            # ✅ Tug‘ilgan sana
            birth_ts = emp.get("birth_date")
            birth_date = None
            if birth_ts and birth_ts > 0:
                try:
                    birth_date = datetime.fromtimestamp(birth_ts).date()
                except:
                    pass

            # ✅ Gender
            gender = emp.get("gender", {}).get("name", "").lower()
            gender = "male" if "erkak" in gender else "female" if "ayol" in gender else ""

            # ✅ Department va lavozim
            department = emp.get("department", {}).get("name", "")
            position = emp.get("staffPosition", {}).get("name", "")

            # ✅ Foydalanuvchini yaratish
            user = CustomUser(
                username=hash_id,
                full_name=full_name,
                email=email,
                gender=gender,
                department=department,
                position=position,
                birth_date=birth_date,
                is_teacher=True
            )

            # ✅ Rasm yuklash
            image_url = emp.get("image")
            if image_url and image_url.startswith("http"):
                try:
                    img_resp = requests.get(image_url, stream=True, timeout=10)
                    if img_resp.status_code == 200:
                        file_name = image_url.split("/")[-1]
                        temp_img = tempfile.NamedTemporaryFile(delete=True)
                        for chunk in img_resp.iter_content(chunk_size=1024):
                            temp_img.write(chunk)
                        temp_img.flush()
                        user.face_image.save(file_name, File(temp_img), save=False)
                except Exception as e:
                    print(f"⚠️ Rasm yuklab bo‘lmadi: {e}")

            # 🔐 Saqlaymiz
            try:
                user.save()
                existing_usernames.add(hash_id)
                total_saved += 1
            except Exception as e:
                print(f"❌ Xatolik: {e}")

            if progress_tracker:
                progress_tracker["current"] += 1

    if progress_tracker:
        progress_tracker["done"] = True

    return total_saved