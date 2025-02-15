import os
import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import load_model
from deepface import DeepFace

# ✅ Model yo‘lini avtomatik aniqlash
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "gan_model.keras")

# ✅ GAN modelini yuklash (agar mavjud bo‘lmasa, xato chiqariladi)
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"🚨 GAN modeli topilmadi: {MODEL_PATH}")

generator = load_model(MODEL_PATH, compile=False)
print(f"✅ GAN modeli yuklandi: {MODEL_PATH}")

# ✅ DeepFace modelini yuklash (emotion uchun)
deepface_model = DeepFace.build_model("Facenet")
print(f"✅ Model yuklandi: Facenet")

# ✅ Emotion tarjimalari (o‘zbek tilida)
emotion_translations = {
    "angry": "G‘azablangan",
    "disgust": "Jirkanish",
    "fear": "Qo‘rqish",
    "happy": "Baxtli",
    "sad": "Xafa",
    "surprise": "Hayratlangan",
    "neutral": "Betaraf"
}


def analyze_emotion(image):
    """
    📊 Yuz tasviridan hissiy holatni aniqlash.
    :param image: NumPy formatidagi yuz tasviri
    :return: Hissiy holat (uzbekcha)
    """
    try:
        if image is None or image.size == 0:
            return "Aniqlanmadi"

        analysis = DeepFace.analyze(image, actions=['emotion'], enforce_detection=False, silent=True)

        if isinstance(analysis, list) and analysis:
            analysis = analysis[0]  # **Birinchi natijani olish**

        emotion = analysis.get("dominant_emotion", "Unknown") if isinstance(analysis, dict) else "Unknown"
        return emotion_translations.get(emotion, "Noma'lum")

    except Exception as e:
        print(f"🚨 Emotion tahlili xatolik: {e}")

    return "Aniqlanmadi"


def enhance_face(image):
    """
    🎨 GAN modeli yordamida yuz tasvirini sifatliroq holga keltirish.
    :param image: NumPy formatidagi yuz tasviri
    :return: Yaxshilangan yuz tasviri
    """
    try:
        if image is None or image.size == 0:
            return image  # **Agar rasm bo'lmasa, qaytariladi**

        # ✅ Rasmni mos formatga o‘tkazish
        image = cv2.resize(image, (100, 100))  # **100x100 qilish**

        # ✅ Grayscale va RGB formatlarini tekshirish
        if len(image.shape) == 2:  # **Agar grayscale bo‘lsa**
            image = np.expand_dims(image, axis=-1)  # **(100,100,1)**

        # ✅ Modelga mos keladigan format
        image = np.expand_dims(image, axis=0)  # **(1, 100, 100, X)** shakl
        image = image.astype("float32") / 255.0  # **Normalize qilish**

        # ✅ GAN modelidan o'tkazish
        enhanced_image = generator.predict(image)

        # ✅ Natijani qayta o'zgartirish
        enhanced_image = (enhanced_image[0] * 255).astype(np.uint8)

        return enhanced_image
    except Exception as e:
        print(f"🚨 GAN modeli xatolik: {e}")

    return image  # **Agar xatolik bo'lsa, asl rasmni qaytarish**
