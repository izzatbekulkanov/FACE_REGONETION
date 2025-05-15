#!/bin/bash

# Virtual muhitni faollashtirish (agar kerak bo‘lsa)
source venv/bin/activate

# Django sozlamalar modulini o‘rnatish
export DJANGO_SETTINGS_MODULE=face_recognition_project.settings

# Daphne serverini ishga tushirish
daphne -b 0.0.0.0 -p 8000 face_recognition_project.asgi:application

# Pauza o‘rniga terminalda davom etish uchun
echo "Daphne serveri ishlamoqda. To‘xtatish uchun Ctrl+C bosing."