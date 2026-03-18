import sys
import os
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        command = sys.argv[1] if len(sys.argv) > 1 else ''
        is_runserver = command == 'runserver'
        is_web_process = is_runserver or os.environ.get('DYNO', '').startswith('web')

        if not is_web_process:
            return

        if is_runserver and os.environ.get('RUN_MAIN') != 'true':
            return

        from . import scheduler
        scheduler.start_scheduler()
