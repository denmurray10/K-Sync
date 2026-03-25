import base64
import hashlib
import mimetypes
from pathlib import Path
from urllib.parse import quote

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Upload local image/video assets to Backblaze B2 and print Cloudinary fetch URLs."

    def add_arguments(self, parser):
        parser.add_argument("--video", action="append", default=[], help="Local video file path to upload.")
        parser.add_argument("--image", action="append", default=[], help="Local image file path to upload.")
        parser.add_argument("--video-prefix", default="Videos", help="B2 folder prefix for uploaded videos.")
        parser.add_argument("--image-prefix", default="Images", help="B2 folder prefix for uploaded images.")

    def _get_b2_config(self):
        key_id = str(getattr(settings, "B2_KEY_ID", "") or "").strip()
        app_key = str(getattr(settings, "B2_APPLICATION_KEY", "") or "").strip()
        bucket_name = str(getattr(settings, "B2_BUCKET_NAME", "") or "").strip()
        download_url = str(getattr(settings, "B2_DOWNLOAD_URL", "") or "").strip()
        if not key_id or not app_key or not bucket_name or not download_url:
            raise CommandError("Missing B2 configuration.")
        return key_id, app_key, bucket_name, download_url

    def _b2_authorize(self, key_id, app_key):
        auth = base64.b64encode(f"{key_id}:{app_key}".encode("utf-8")).decode("ascii")
        response = requests.get(
            "https://api.backblazeb2.com/b2api/v2/b2_authorize_account",
            headers={"Authorization": f"Basic {auth}"},
            timeout=20,
        )
        if response.status_code != 200:
            raise CommandError(f"B2 authorize failed: {response.status_code} {response.text[:300]}")
        return response.json()

    def _b2_get_bucket_id(self, api_url, auth_token, account_id, bucket_name):
        response = requests.get(
            f"{api_url}/b2api/v2/b2_list_buckets",
            headers={"Authorization": auth_token},
            params={"accountId": account_id},
            timeout=20,
        )
        if response.status_code != 200:
            raise CommandError(f"B2 list buckets failed: {response.status_code} {response.text[:300]}")
        bucket = next((item for item in response.json().get("buckets", []) if item.get("bucketName") == bucket_name), None)
        if not bucket:
            raise CommandError(f"B2 bucket not found: {bucket_name}")
        return bucket["bucketId"]

    def _b2_get_upload_url(self, api_url, auth_token, bucket_id):
        response = requests.post(
            f"{api_url}/b2api/v2/b2_get_upload_url",
            headers={"Authorization": auth_token},
            json={"bucketId": bucket_id},
            timeout=20,
        )
        if response.status_code != 200:
            raise CommandError(f"B2 get upload URL failed: {response.status_code} {response.text[:300]}")
        payload = response.json()
        return payload["uploadUrl"], payload["authorizationToken"]

    def _upload_b2_file(self, upload_url, upload_auth, file_name, content, content_type):
        sha1 = hashlib.sha1(content).hexdigest()
        headers = {
            "Authorization": upload_auth,
            "X-Bz-File-Name": quote(file_name, safe="/"),
            "Content-Type": content_type,
            "X-Bz-Content-Sha1": sha1,
        }
        response = requests.post(upload_url, headers=headers, data=content, timeout=120)
        if response.status_code not in (200, 201):
            raise CommandError(f"B2 upload failed: {response.status_code} {response.text[:300]}")
        return response.json()

    def _cloudinary_fetch_url(self, source_url, kind):
        cloud_name = str(getattr(settings, "CLOUDINARY_CLOUD_NAME", "") or "").strip()
        if not cloud_name:
            return ""
        if kind == "video":
            transform = "f_mp4,q_auto"
            resource = "video"
        else:
            transform = "f_auto,q_auto"
            resource = "image"
        encoded = quote(source_url, safe="")
        if transform:
            return f"https://res.cloudinary.com/{cloud_name}/{resource}/fetch/{transform}/{encoded}"
        return f"https://res.cloudinary.com/{cloud_name}/{resource}/fetch/{encoded}"

    def _normalize_targets(self, values):
        targets = []
        for value in values:
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = Path.cwd() / path
            if not path.exists() or not path.is_file():
                raise CommandError(f"File not found: {path}")
            targets.append(path)
        return targets

    def handle(self, *args, **options):
        videos = self._normalize_targets(options["video"])
        images = self._normalize_targets(options["image"])
        if not videos and not images:
            raise CommandError("Provide at least one --video or --image path.")

        key_id, app_key, bucket_name, download_url = self._get_b2_config()
        auth = self._b2_authorize(key_id, app_key)
        bucket_id = self._b2_get_bucket_id(auth["apiUrl"], auth["authorizationToken"], auth["accountId"], bucket_name)
        upload_url, upload_auth = self._b2_get_upload_url(auth["apiUrl"], auth["authorizationToken"], bucket_id)

        results = []

        def upload_group(paths, prefix, kind):
            nonlocal upload_url, upload_auth
            for path in paths:
                content_type = mimetypes.guess_type(path.name)[0] or ("video/mp4" if kind == "video" else "application/octet-stream")
                content = path.read_bytes()
                target_name = f"{prefix.strip('/')}/{path.name}"
                try:
                    self._upload_b2_file(upload_url, upload_auth, target_name, content, content_type)
                except CommandError as error:
                    if "expired_auth_token" in str(error).lower():
                        upload_url, upload_auth = self._b2_get_upload_url(auth["apiUrl"], auth["authorizationToken"], bucket_id)
                        self._upload_b2_file(upload_url, upload_auth, target_name, content, content_type)
                    else:
                        raise
                b2_url = f"{download_url.rstrip('/')}/file/{bucket_name}/{quote(target_name, safe='/')}"
                cloudinary_url = self._cloudinary_fetch_url(b2_url, kind)
                results.append((kind, str(path), b2_url, cloudinary_url))

        upload_group(videos, options["video_prefix"], "video")
        upload_group(images, options["image_prefix"], "image")

        for kind, local_path, b2_url, cloudinary_url in results:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(f"{kind.upper()}: {local_path}"))
            self.stdout.write(f"B2: {b2_url}")
            self.stdout.write(f"Cloudinary: {cloudinary_url}")
