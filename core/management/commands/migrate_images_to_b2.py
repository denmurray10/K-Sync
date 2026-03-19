import csv
import hashlib
import mimetypes
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import BlogArticle, KPopGroup, KPopMember


class Command(BaseCommand):
    help = (
        "Download idol/blog image URLs, upload them to Backblaze B2, generate old->new mapping, "
        "optionally apply DB updates, and optionally run Cloudinary fetch canary checks."
    )

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default='media_url_map_b2.csv', help='Output mapping CSV path')
        parser.add_argument('--apply', action='store_true', help='Apply updates to DB fields')
        parser.add_argument('--limit', type=int, default=0, help='Limit unique URLs processed (0 = all)')
        parser.add_argument('--canary-check', action='store_true', help='Check Cloudinary image/fetch for migrated URLs')

    def _get_b2_config(self):
        key_id = str(getattr(settings, 'B2_KEY_ID', '') or '').strip()
        app_key = str(getattr(settings, 'B2_APPLICATION_KEY', '') or '').strip()
        bucket_name = (
            str(getattr(settings, 'B2_IMAGE_BUCKET_NAME', '') or '').strip()
            or str(getattr(settings, 'B2_BUCKET_NAME', '') or '').strip()
        )
        download_url = str(getattr(settings, 'B2_DOWNLOAD_URL', '') or '').strip()
        if not key_id or not app_key or not bucket_name or not download_url:
            raise CommandError('Missing B2 credentials/settings (B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME/B2_IMAGE_BUCKET_NAME, B2_DOWNLOAD_URL)')
        return key_id, app_key, bucket_name, download_url

    def _b2_authorize(self, key_id, app_key):
        import base64

        auth = base64.b64encode(f'{key_id}:{app_key}'.encode('utf-8')).decode('ascii')
        resp = requests.get(
            'https://api.backblazeb2.com/b2api/v2/b2_authorize_account',
            headers={'Authorization': f'Basic {auth}'},
            timeout=20,
        )
        if resp.status_code != 200:
            raise CommandError(f'B2 authorize failed: {resp.status_code} {resp.text[:300]}')
        return resp.json()

    def _b2_get_bucket_id(self, api_url, auth_token, account_id, bucket_name):
        resp = requests.get(
            f'{api_url}/b2api/v2/b2_list_buckets',
            headers={'Authorization': auth_token},
            params={'accountId': account_id},
            timeout=20,
        )
        if resp.status_code != 200:
            raise CommandError(f'B2 list buckets failed: {resp.status_code} {resp.text[:300]}')
        buckets = resp.json().get('buckets', [])
        bucket = next((b for b in buckets if b.get('bucketName') == bucket_name), None)
        if not bucket:
            raise CommandError(f'B2 bucket not found: {bucket_name}')
        return bucket.get('bucketId')

    def _b2_get_upload_url(self, api_url, auth_token, bucket_id):
        resp = requests.post(
            f'{api_url}/b2api/v2/b2_get_upload_url',
            headers={'Authorization': auth_token},
            json={'bucketId': bucket_id},
            timeout=20,
        )
        if resp.status_code != 200:
            raise CommandError(f'B2 get upload URL failed: {resp.status_code} {resp.text[:300]}')
        return resp.json()['uploadUrl'], resp.json()['authorizationToken']

    def _content_sha1(self, content):
        h = hashlib.sha1()
        h.update(content)
        return h.hexdigest()

    def _collect_image_usages(self):
        usages = []

        for item in KPopGroup.objects.exclude(image_url__isnull=True).exclude(image_url='').only('id', 'slug', 'image_url'):
            usages.append((item.image_url, 'KPopGroup', item.id, 'image_url'))

        for item in KPopMember.objects.exclude(image_url__isnull=True).exclude(image_url='').only('id', 'name', 'image_url'):
            usages.append((item.image_url, 'KPopMember', item.id, 'image_url'))

        for item in BlogArticle.objects.only('id', 'slug', 'image', 'image_2', 'image_3'):
            if item.image:
                usages.append((item.image, 'BlogArticle', item.id, 'image'))
            if item.image_2:
                usages.append((item.image_2, 'BlogArticle', item.id, 'image_2'))
            if item.image_3:
                usages.append((item.image_3, 'BlogArticle', item.id, 'image_3'))

        return usages

    def _guess_ext(self, url, content_type):
        ct = str(content_type or '').split(';')[0].strip().lower()
        ct_map = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/webp': '.webp',
            'image/gif': '.gif',
            'image/avif': '.avif',
        }
        if ct in ct_map:
            return ct_map[ct]

        path = urlparse(url).path or ''
        suffix = Path(path).suffix.lower()
        if suffix in ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif'):
            return '.jpg' if suffix == '.jpeg' else suffix

        guessed = mimetypes.guess_extension(ct) if ct else None
        if guessed:
            return '.jpg' if guessed == '.jpe' else guessed
        return '.jpg'

    def _download_image(self, url):
        def _try_get(target_url):
            response = requests.get(target_url, timeout=25, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
            if response.status_code != 200:
                raise RuntimeError(f'download status {response.status_code}')
            ctype_inner = str(response.headers.get('content-type') or '').lower()
            if not ctype_inner.startswith('image/'):
                raise RuntimeError(f'non-image content-type {ctype_inner}')
            return response.content, ctype_inner

        try:
            return _try_get(url)
        except Exception:
            source_url = self._extract_cloudinary_fetch_source_url(url)
            if source_url and source_url != url:
                return _try_get(source_url)
            raise

    def _extract_cloudinary_fetch_source_url(self, url):
        parsed = urlparse(url)
        if 'res.cloudinary.com' not in (parsed.netloc or '').lower():
            return ''
        marker = '/image/fetch/'
        path = parsed.path or ''
        if marker not in path:
            return ''
        after = path.split(marker, 1)[1]
        # Cloudinary fetch format may include transforms before the encoded URL.
        # We detect the URL payload by searching for encoded or literal http(s).
        for token in ('https%3A%2F%2F', 'http%3A%2F%2F', 'https://', 'http://'):
            idx = after.find(token)
            if idx >= 0:
                return unquote(after[idx:])
        return ''

    def _upload_b2_file(self, upload_url, upload_auth, file_name, content, content_type):
        sha1 = self._content_sha1(content)
        headers = {
            'Authorization': upload_auth,
            'X-Bz-File-Name': quote(file_name, safe='/'),
            'Content-Type': content_type,
            'X-Bz-Content-Sha1': sha1,
        }
        resp = requests.post(upload_url, headers=headers, data=content, timeout=60)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f'upload failed {resp.status_code}: {resp.text[:250]}')
        return resp.json()

    def _build_cloudinary_fetch_url(self, source_url):
        cloud_name = str(getattr(settings, 'CLOUDINARY_CLOUD_NAME', '') or '').strip()
        if not cloud_name:
            return ''
        transform = str(getattr(settings, 'IMAGE_STREAM_CLOUDINARY_TRANSFORM', '') or '').strip()
        encoded = quote(source_url, safe='')
        if transform:
            return f'https://res.cloudinary.com/{cloud_name}/image/fetch/{transform}/{encoded}'
        return f'https://res.cloudinary.com/{cloud_name}/image/fetch/{encoded}'

    def _apply_mapping(self, mapping):
        by_old = {k: v for k, v in mapping.items() if k and v}
        total = 0

        def update_model(model, field):
            nonlocal total
            qs = model.objects.exclude(**{f'{field}__isnull': True}).exclude(**{field: ''})
            updated = 0
            for obj in qs.iterator():
                old = str(getattr(obj, field, '') or '').strip()
                new = by_old.get(old)
                if not new:
                    continue
                setattr(obj, field, new)
                obj.save(update_fields=[field])
                updated += 1
            total += updated
            return updated

        summary = {
            'KPopGroup.image_url': update_model(KPopGroup, 'image_url'),
            'KPopMember.image_url': update_model(KPopMember, 'image_url'),
            'BlogArticle.image': update_model(BlogArticle, 'image'),
            'BlogArticle.image_2': update_model(BlogArticle, 'image_2'),
            'BlogArticle.image_3': update_model(BlogArticle, 'image_3'),
            'total': total,
        }
        return summary

    def handle(self, *args, **options):
        output_path = Path(options['output']).resolve()
        apply_updates = bool(options.get('apply'))
        limit = max(0, int(options.get('limit') or 0))
        canary_check = bool(options.get('canary_check'))

        key_id, app_key, bucket_name, download_url = self._get_b2_config()
        auth = self._b2_authorize(key_id, app_key)
        api_url = auth['apiUrl']
        auth_token = auth['authorizationToken']
        account_id = auth['accountId']
        bucket_id = self._b2_get_bucket_id(api_url, auth_token, account_id, bucket_name)
        upload_url, upload_auth = self._b2_get_upload_url(api_url, auth_token, bucket_id)

        usages = self._collect_image_usages()
        unique_urls = []
        seen = set()
        for old_url, _model, _id, _field in usages:
            u = str(old_url or '').strip()
            if not u or u in seen:
                continue
            seen.add(u)
            unique_urls.append(u)

        if limit > 0:
            unique_urls = unique_urls[:limit]

        self.stdout.write(self.style.NOTICE(f'Found {len(unique_urls)} unique image URLs to process.'))

        mapping = {}
        failures = []
        canary_results = []

        for idx, old_url in enumerate(unique_urls, start=1):
            try:
                parsed = urlparse(old_url)
                if 'backblazeb2.com' in (parsed.netloc or '').lower() and f'/file/{bucket_name}/' in (parsed.path or ''):
                    mapping[old_url] = old_url
                    continue

                content, content_type = self._download_image(old_url)
                ext = self._guess_ext(old_url, content_type)
                digest = hashlib.sha1(old_url.encode('utf-8')).hexdigest()
                file_name = f'media/images/{digest}{ext}'
                self._upload_b2_file(upload_url, upload_auth, file_name, content, content_type)
                new_url = f"{download_url.rstrip('/')}/file/{bucket_name}/{quote(file_name, safe='/')}"
                mapping[old_url] = new_url

                if canary_check:
                    cloudinary_url = self._build_cloudinary_fetch_url(new_url)
                    if cloudinary_url:
                        try:
                            resp = requests.get(cloudinary_url, timeout=20, allow_redirects=True)
                            canary_results.append((new_url, resp.status_code))
                        except Exception:
                            canary_results.append((new_url, 0))

            except Exception as exc:
                failures.append((old_url, str(exc)))

            if idx % 25 == 0:
                self.stdout.write(f'Processed {idx}/{len(unique_urls)}...')

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['old_url', 'new_url'])
            for old, new in mapping.items():
                writer.writerow([old, new])

        self.stdout.write(self.style.SUCCESS(f'Mapping written: {output_path} (rows={len(mapping)})'))

        if failures:
            fail_path = output_path.with_name(output_path.stem + '_failures.csv')
            with fail_path.open('w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['old_url', 'error'])
                writer.writerows(failures)
            self.stdout.write(self.style.WARNING(f'Failures: {len(failures)} (saved to {fail_path})'))

        if canary_check and canary_results:
            total = len(canary_results)
            ok = sum(1 for _u, status in canary_results if status == 200)
            self.stdout.write(self.style.NOTICE(f'Cloudinary canary: {ok}/{total} returned HTTP 200'))

        if apply_updates:
            summary = self._apply_mapping(mapping)
            self.stdout.write(self.style.SUCCESS(f'Applied DB updates: {summary}'))
        else:
            self.stdout.write(self.style.NOTICE('Dry-run mode (no DB updates). Use --apply to persist.'))
