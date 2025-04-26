# core/context.py
last_recognized_user = {"name": None}

def update_recognized_name(name):
    last_recognized_user["name"] = name
