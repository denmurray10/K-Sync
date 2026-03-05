import sys
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Prevent scheduler from running multiple times due to auto-reloader
        if 'runserver' in sys.argv and not sys.argv[0].endswith('manage.py'):
            # The underlying werkzeug reloader starts a second process. 
            # the RUN_MAIN env var is only set in the second "child" process.
            pass
        else:
             from . import scheduler
             scheduler.start_scheduler()
