"""
PRE-LAUNCH MIDDLEWARE
Restricts the live site to only the Coming Soon page and Games.
To undo: remove 'core.middleware.PreLaunchMiddleware' from MIDDLEWARE in settings.py
"""
from django.shortcuts import redirect


class PreLaunchMiddleware:
    ALLOWED_PREFIXES = (
        '/',            # exact homepage (coming soon)
        '/coming-soon/',
        '/games/',
        '/game/',       # all individual game pages
        '/api/prelaunch-signup/',
        '/admin/',      # keep admin accessible
        '/static/',
        '/media/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Allow exact homepage
        if path == '/':
            return self.get_response(request)

        # Allow any path that starts with an allowed prefix
        if any(path.startswith(p) for p in self.ALLOWED_PREFIXES if p != '/'):
            return self.get_response(request)

        # Everything else → redirect to homepage (coming soon)
        return redirect('/')
