# core/apps.py
from django.apps import AppConfig
import threading
import logging
from django.db.utils import OperationalError


logger = logging.getLogger(__name__)

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        try:
            from core.recognition import get_selected_camera
            get_selected_camera()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"core.apps.ready xatoligi: {e}")