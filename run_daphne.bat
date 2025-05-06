@echo off
set DJANGO_SETTINGS_MODULE=face_recognition_project.settings
daphne -b 0.0.0.0 -p 8000 face_recognition_project.asgi:application
pause
