from tensorflow.keras.models import load_model

def load_face_model(model_path="models/face_recognition_model.h5"):
    """Yuzni tanish modeli yuklash"""
    return load_model(model_path)
