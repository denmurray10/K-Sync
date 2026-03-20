"""
PRE-LAUNCH MIDDLEWARE
Restricts the live site to only the Coming Soon page and Games.
To undo: remove 'core.middleware.PreLaunchMiddleware' from MIDDLEWARE in settings.py
"""
from django.shortcuts import redirect
from django.conf import settings
from django.http.response import StreamingHttpResponse
import re


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
    CONSENT_SCRIPT_MARKER = 'id="ksync-consent-mode"'
    CONSENT_BANNER_MARKER = 'id="ksync-consent-banner"'
    META_PIXEL_SCRIPT_MARKER = 'id="ksync-meta-pixel"'
    META_PIXEL_NOSCRIPT_MARKER = 'id="ksync-meta-pixel-noscript"'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if not getattr(settings, 'ENABLE_THIRD_PARTY_TRACKING', True):
            return response

        if isinstance(response, StreamingHttpResponse):
            return response

        content_type = (response.get('Content-Type') or '').lower()
        if 'text/html' not in content_type:
            return response

        gtm_id = getattr(settings, 'GOOGLE_TAG_MANAGER_ID', '').strip()
        pixel_id = str(getattr(settings, 'FACEBOOK_PIXEL_ID', '') or '').strip()
        if not gtm_id:
            gtm_id = ''

        content = response.content
        charset = getattr(response, 'charset', None) or 'utf-8'
        html = content.decode(charset, errors='ignore')

        has_gtm = (
            f'googletagmanager.com/gtm.js?id={gtm_id}' in html
            or f"dataLayer','{gtm_id}'" in html
            or f'googletagmanager.com/ns.html?id={gtm_id}' in html
        ) if gtm_id else True

        has_pixel = (
            f"fbq('init', '{pixel_id}')" in html
            or f'facebook.com/tr?id={pixel_id}' in html
            or 'connect.facebook.net/en_US/fbevents.js' in html
        ) if pixel_id else True

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

        pixel_head_script = (
            "<!-- Meta Pixel Code -->\n"
            "<script id=\"ksync-meta-pixel\">"
            "!function(f,b,e,v,n,t,s)"
            "{if(f.fbq)return;n=f.fbq=function(){n.callMethod?"
            "n.callMethod.apply(n,arguments):n.queue.push(arguments)};"
            "if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';"
            "n.queue=[];t=b.createElement(e);t.async=!0;"
            "t.src=v;s=b.getElementsByTagName(e)[0];"
            "s.parentNode.insertBefore(t,s)}(window, document,'script',"
            "'https://connect.facebook.net/en_US/fbevents.js');"
            "fbq('init', '%s');"
            "fbq('track', 'PageView');"
            "</script>\n"
            "<!-- End Meta Pixel Code -->"
        ) % pixel_id

        pixel_body_noscript = (
            "<!-- Meta Pixel (noscript) -->\n"
            "<noscript id=\"ksync-meta-pixel-noscript\">"
            "<img height=\"1\" width=\"1\" style=\"display:none\" "
            "src=\"https://www.facebook.com/tr?id=%s&ev=PageView&noscript=1\"/>"
            "</noscript>\n"
            "<!-- End Meta Pixel (noscript) -->"
        ) % pixel_id

        consent_mode_script = (
            "<!-- K-Sync Consent Mode -->\n"
            "<script id=\"ksync-consent-mode\">"
            "(function(){"
            "var STORAGE_KEY='ksync_cookie_consent_v1';"
            "window.dataLayer=window.dataLayer||[];"
            "window.gtag=window.gtag||function(){window.dataLayer.push(arguments);};"
            "var defaults={"
            "ad_storage:'denied',"
            "analytics_storage:'denied',"
            "ad_user_data:'denied',"
            "ad_personalization:'denied',"
            "functionality_storage:'granted',"
            "security_storage:'granted'"
            "};"
            "window.gtag('consent','default',defaults);"
            "window.gtag('set','ads_data_redaction',true);"
            "window.gtag('set','url_passthrough',true);"
            "window.ksyncApplyConsent=function(choice){"
            "var analytics=!!(choice&&choice.analytics);"
            "var ads=!!(choice&&choice.ads);"
            "var update={"
            "ad_storage:ads?'granted':'denied',"
            "analytics_storage:analytics?'granted':'denied',"
            "ad_user_data:ads?'granted':'denied',"
            "ad_personalization:ads?'granted':'denied',"
            "functionality_storage:'granted',"
            "security_storage:'granted'"
            "};"
            "window.gtag('consent','update',update);"
            "try{localStorage.setItem(STORAGE_KEY,JSON.stringify({analytics:analytics,ads:ads,updated_at:new Date().toISOString()}));}catch(e){}"
            "};"
            "try{"
            "var saved=localStorage.getItem(STORAGE_KEY);"
            "if(saved){"
            "var parsed=JSON.parse(saved)||{};"
            "window.ksyncApplyConsent({analytics:!!parsed.analytics,ads:!!parsed.ads});"
            "}"
            "}catch(e){}"
            "})();"
            "</script>\n"
            "<!-- End K-Sync Consent Mode -->"
        )

        consent_banner = (
            "<!-- K-Sync Consent Banner -->\n"
            "<style id=\"ksync-consent-style\">"
            "#ksync-consent-banner input[type=checkbox]{-webkit-appearance:checkbox !important;appearance:checkbox !important;accent-color:#F425c0 !important;color:#F425c0 !important;background-image:none !important;background-color:#0a0a0a !important;border:1px solid #F425c0 !important;border-radius:2px !important;}"
            "#ksync-consent-banner input[type=checkbox]:checked{-webkit-appearance:checkbox !important;appearance:checkbox !important;accent-color:#F425c0 !important;color:#F425c0 !important;background-image:none !important;background-color:#F425c0 !important;border-color:#F425c0 !important;}"
            "#ksync-consent-banner input[type=checkbox]:focus{outline:none !important;box-shadow:0 0 0 2px rgba(244,37,192,.35) !important;}"
            "#ksync-consent-banner input[type=checkbox]:disabled{accent-color:#F425c0 !important;opacity:1 !important;}"
            "@media (max-width:768px){"
            "#ksync-consent-banner{left:10px!important;right:10px!important;bottom:10px!important;padding:14px 14px!important;max-height:68vh;overflow:auto;}"
            "#ksync-consent-banner strong{font-size:15px!important;letter-spacing:.06em!important;}"
            "#ksync-consent-banner p{font-size:11px!important;line-height:1.45!important;}"
            "#ksync-consent-banner [data-consent-actions]{width:100%;display:flex;gap:8px;}"
            "#ksync-consent-banner [data-consent-actions] button{flex:1;min-height:40px;}"
            "#ksync-open-consent-settings{right:10px!important;bottom:10px!important;padding:9px 10px!important;font-size:9px!important;}"
            "}"
            "</style>"
            "<div id=\"ksync-consent-banner\" style=\"display:none;position:fixed;left:16px;right:16px;bottom:16px;z-index:2147483647;background:rgba(0,0,0,.96);color:#fff;padding:18px 20px;border:1px solid rgba(255,255,255,.2);box-shadow:0 0 0 1px rgba(244,37,192,.45),0 16px 32px rgba(0,0,0,.65);font-family:Montserrat,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;\">"
            "<div style=\"display:flex;justify-content:space-between;gap:14px;flex-wrap:wrap;align-items:flex-start;\">"
            "<div style=\"max-width:760px;\">"
            "<strong style=\"display:block;font-size:18px;margin-bottom:7px;font-weight:900;letter-spacing:.08em;text-transform:uppercase;\">Privacy choices</strong>"
            "<p style=\"margin:0 0 10px 0;font-size:13px;line-height:1.5;color:#cbd5e1;letter-spacing:.04em;text-transform:uppercase;\">We use cookies and similar technologies for essential site security, analytics, and ads personalization. See our <a href=\"/legal/privacy-policy/\" style=\"color:#F425c0;text-decoration:none;border-bottom:1px solid #F425c0;\">Privacy Policy</a> and <a href=\"/legal/cookie-policy/\" style=\"color:#F425c0;text-decoration:none;border-bottom:1px solid #F425c0;\">Cookie Policy</a>. Choose Accept All, Reject All, or manage your preferences.</p>"
            "<button id=\"ksync-open-preferences\" type=\"button\" style=\"background:transparent;color:#F425c0;border:0;padding:0;cursor:pointer;text-transform:uppercase;letter-spacing:.16em;font-size:11px;font-weight:700;\">Manage preferences</button>"
            "</div>"
            "<div data-consent-actions=\"1\" style=\"display:flex;gap:10px;align-items:center;flex-wrap:wrap;\">"
            "<button id=\"ksync-reject-all\" type=\"button\" style=\"padding:11px 16px;border:1px solid rgba(255,255,255,.35);background:transparent;color:#fff;cursor:pointer;font-weight:800;letter-spacing:.14em;text-transform:uppercase;font-size:10px;\">Reject all</button>"
            "<button id=\"ksync-accept-all\" type=\"button\" style=\"padding:11px 16px;border:1px solid #F425c0;background:#F425c0;color:#fff;cursor:pointer;font-weight:900;letter-spacing:.14em;text-transform:uppercase;font-size:10px;box-shadow:3px 3px 0 rgba(255,255,255,1);\">Accept all</button>"
            "</div>"
            "</div>"
            "<div id=\"ksync-consent-preferences\" style=\"display:none;margin-top:14px;padding-top:14px;border-top:1px solid rgba(255,255,255,.18);\">"
            "<label style=\"display:block;margin-bottom:9px;font-size:12px;text-transform:uppercase;letter-spacing:.11em;color:#e2e8f0;\"><input type=\"checkbox\" checked disabled style=\"margin-right:8px;accent-color:#F425c0;\">Strictly necessary (always on)</label>"
            "<label style=\"display:block;margin-bottom:9px;font-size:12px;text-transform:uppercase;letter-spacing:.11em;color:#e2e8f0;\"><input id=\"ksync-consent-analytics\" type=\"checkbox\" style=\"margin-right:8px;accent-color:#F425c0;\">Analytics measurement</label>"
            "<label style=\"display:block;margin-bottom:12px;font-size:12px;text-transform:uppercase;letter-spacing:.11em;color:#e2e8f0;\"><input id=\"ksync-consent-ads\" type=\"checkbox\" style=\"margin-right:8px;accent-color:#F425c0;\">Ad storage and personalization</label>"
            "<button id=\"ksync-save-preferences\" type=\"button\" style=\"padding:10px 14px;border:1px solid #F425c0;background:#F425c0;color:#fff;cursor:pointer;font-weight:900;text-transform:uppercase;letter-spacing:.14em;font-size:10px;box-shadow:3px 3px 0 rgba(255,255,255,1);\">Save preferences</button>"
            "</div>"
            "</div>"
            "<button id=\"ksync-open-consent-settings\" type=\"button\" style=\"display:none;position:fixed;bottom:16px;right:16px;z-index:2147483646;padding:10px 14px;border:1px solid rgba(255,255,255,.3);background:#000;color:#fff;cursor:pointer;font-size:10px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;\">Cookie settings</button>"
            "<script>"
            "(function(){"
            "var STORAGE_KEY='ksync_cookie_consent_v1';"
            "var banner=document.getElementById('ksync-consent-banner');"
            "var openBtn=document.getElementById('ksync-open-consent-settings');"
            "if(!banner||!openBtn){return;}"
            "var prefs=document.getElementById('ksync-consent-preferences');"
            "var analytics=document.getElementById('ksync-consent-analytics');"
            "var ads=document.getElementById('ksync-consent-ads');"
            "var openPrefs=document.getElementById('ksync-open-preferences');"
            "var acceptAll=document.getElementById('ksync-accept-all');"
            "var rejectAll=document.getElementById('ksync-reject-all');"
            "var savePrefs=document.getElementById('ksync-save-preferences');"
            "function apply(choice){if(typeof window.ksyncApplyConsent==='function'){window.ksyncApplyConsent(choice);}}"
            "function hideBanner(){banner.style.display='none';openBtn.style.display='none';}"
            "function showBanner(){banner.style.display='block';}"
            "function hasSaved(){try{return !!localStorage.getItem(STORAGE_KEY);}catch(e){return false;}}"
            "function readSaved(){try{return JSON.parse(localStorage.getItem(STORAGE_KEY)||'{}')||{};}catch(e){return {};}}"
            "function setBoxes(){var saved=readSaved();analytics.checked=saved.analytics!==false;ads.checked=saved.ads!==false;}"
            "function openFromPolicy(){showBanner();prefs.style.display='block';setBoxes();}"
            "openPrefs.addEventListener('click',function(){prefs.style.display='block';setBoxes();});"
            "acceptAll.addEventListener('click',function(){apply({analytics:true,ads:true});hideBanner();});"
            "rejectAll.addEventListener('click',function(){apply({analytics:false,ads:false});hideBanner();});"
            "savePrefs.addEventListener('click',function(){apply({analytics:!!analytics.checked,ads:!!ads.checked});hideBanner();});"
            "openBtn.addEventListener('click',function(){showBanner();prefs.style.display='block';setBoxes();});"
            "window.ksyncOpenConsentSettings=openFromPolicy;"
            "window.addEventListener('ksync:open-consent-settings',openFromPolicy);"
            "if(hasSaved()){hideBanner();}else{showBanner();}"
            "})();"
            "</script>\n"
            "<!-- End K-Sync Consent Banner -->"
        )

        lower_html = html.lower()

        head_match = re.search(r'<head[^>]*>', lower_html)
        if head_match:
            insert_at = head_match.end()
            if self.CONSENT_SCRIPT_MARKER not in html:
                html = html[:insert_at] + "\n" + consent_mode_script + html[insert_at:]
                lower_html = html.lower()
                head_match = re.search(r'<head[^>]*>', lower_html)
                insert_at = head_match.end() if head_match else insert_at
            if not has_gtm:
                html = html[:insert_at] + "\n" + head_script + html[insert_at:]
            if pixel_id and not has_pixel and self.META_PIXEL_SCRIPT_MARKER not in html:
                html = html[:insert_at] + "\n" + pixel_head_script + html[insert_at:]

        lower_html = html.lower()
        body_match = re.search(r'<body[^>]*>', lower_html)
        if body_match:
            insert_at = body_match.end()
            if not has_gtm:
                html = html[:insert_at] + "\n" + body_noscript + html[insert_at:]
                lower_html = html.lower()
            if pixel_id and not has_pixel and self.META_PIXEL_NOSCRIPT_MARKER not in html:
                html = html[:insert_at] + "\n" + pixel_body_noscript + html[insert_at:]
                lower_html = html.lower()
            if self.CONSENT_BANNER_MARKER not in html:
                body_close_match = re.search(r'</body>', lower_html)
                if body_close_match:
                    html = html[:body_close_match.start()] + "\n" + consent_banner + "\n" + html[body_close_match.start():]
                else:
                    html = html + "\n" + consent_banner

        response.content = html.encode(charset)
        if response.has_header('Content-Length'):
            response['Content-Length'] = str(len(response.content))
        return response
