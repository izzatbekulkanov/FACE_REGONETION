import os
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO

def fetch_and_save_image(image_url, user_id):
    """
    📥 API orqali foydalanuvchi rasmini yuklab olish va `media/faces/` papkasiga saqlash.
    """
    try:
        response = requests.get(image_url, timeout=10)  # ⏳ Rasmni yuklash
        response.raise_for_status()

        # Fayl kengaytmasini tekshirish
        ext = image_url.split(".")[-1].lower()
        if ext not in ["jpg", "jpeg", "png"]:  # ❌ Noto‘g‘ri format bo‘lsa
            ext = "jpg"

        file_name = f"{user_id}.{ext}"  # 🔖 Fayl nomi

        # 🔄 Saqlash yo‘lini to‘g‘ri yaratish (MEDIA_ROOT ichida faces/ katalogi)
        save_path = os.path.join(settings.MEDIA_ROOT, "faces", file_name)

        # 🔄 Agar katalog mavjud bo‘lmasa, yaratish
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        image = Image.open(BytesIO(response.content))  # 🖼 Rasmni ochish
        image = image.convert("RGB")  # RGB formatga o‘tkazish
        image.thumbnail((400, 400))  # 📏 O‘lchamni moslashtirish

        # 📥 JPG formatda saqlash
        image.save(save_path, format="JPEG", quality=90)

        # 🔄 Django `ImageField` uchun to‘g‘ri `media/` yo‘lini qaytarish
        return f"faces/{file_name}", None

    except requests.exceptions.RequestException as e:
        print(f"❌ Rasmni yuklashda xatolik: {e}")
        return None, None
