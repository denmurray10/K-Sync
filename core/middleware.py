"""
PRE-LAUNCH MIDDLEWARE
Restricts the live site to only the Coming Soon page and Games.
To undo: remove 'core.middleware.PreLaunchMiddleware' from MIDDLEWARE in settings.py
"""
from django.shortcuts import redirect
from django.conf import settings
from django.http.response import StreamingHttpResponse


class PreLaunchMiddleware:
    ALLOWED_PREFIXES = (
        '/',            # exact homepage (coming soon)
        '/coming-soon/',
        '/games/',
        '/game/',       # all individual game pages
        '/bias-selector/',
        '/news/',       # blog / news page
        '/blog/',       # individual blog articles
        '/api/prelaunch-signup/',
        '/api/bias-quiz-result/',
        '/staff/',      # staff dashboard
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


class GoogleTagManagerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if isinstance(response, StreamingHttpResponse):
            return response

        content_type = (response.get('Content-Type') or '').lower()
        if 'text/html' not in content_type:
            return response

        gtm_id = getattr(settings, 'GOOGLE_TAG_MANAGER_ID', '').strip()
        if not gtm_id:
            return response

        content = response.content
        charset = getattr(response, 'charset', None) or 'utf-8'
        html = content.decode(charset, errors='ignore')

        if (
            f'googletagmanager.com/gtm.js?id={gtm_id}' in html
            or f"dataLayer','{gtm_id}'" in html
            or f'googletagmanager.com/ns.html?id={gtm_id}' in html
        ):
            return response

        head_script = (
            "<!-- Google Tag Manager -->\n"
            "<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':"
            "new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],"
            "j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src="
            "'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);"
            "})(window,document,'script','dataLayer','%s');</script>\n"
            "<!-- End Google Tag Manager -->"
        ) % gtm_id

        body_noscript = (
            "<!-- Google Tag Manager (noscript) -->\n"
            "<noscript><iframe src=\"https://www.googletagmanager.com/ns.html?id=%s\" "
            "height=\"0\" width=\"0\" style=\"display:none;visibility:hidden\"></iframe></noscript>\n"
            "<!-- End Google Tag Manager (noscript) -->"
        ) % gtm_id

        lower_html = html.lower()

        head_index = lower_html.find('<head>')
        if head_index != -1:
            insert_at = head_index + len('<head>')
            html = html[:insert_at] + "\n" + head_script + html[insert_at:]

        lower_html = html.lower()
        body_index = lower_html.find('<body')
        if body_index != -1:
            body_close = lower_html.find('>', body_index)
            if body_close != -1:
                insert_at = body_close + 1
                html = html[:insert_at] + "\n" + body_noscript + html[insert_at:]

        response.content = html.encode(charset)
        if response.has_header('Content-Length'):
            response['Content-Length'] = str(len(response.content))
        return response
