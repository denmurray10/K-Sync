import csv
import hashlib
import io
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import BlogArticle, KPopGroup, KPopMember


class Command(BaseCommand):
    help = (
        "Optimize oversized Backblaze image files, upload optimized variants to B2, "
        "and optionally apply URL updates in DB fields."
    )

    def add_arguments(self, parser):
        parser.add_argument('--size-threshold-mb', type=float, default=10.0, help='Target max source size in MB (default: 10).')
        parser.add_argument('--max-dim', type=int, default=2800, help='Maximum width/height for optimized images.')
        parser.add_argument('--limit', type=int, default=0, help='Limit oversized URLs processed (0 = all).')
        parser.add_argument('--apply', action='store_true', help='Apply URL updates to DB fields.')
        parser.add_argument('--no-cloudinary-direct', action='store_true', help='Disable direct Cloudinary upload for oversized images.')
        parser.add_argument('--output', type=str, default='media_url_map_b2_optimized.csv', help='CSV mapping output path.')

    def _require_pillow(self):
        try:
            from PIL import Image  # noqa: F401
        except Exception as exc:
            raise CommandError('Pillow is required. Install with: pip install Pillow==10.4.0') from exc

    def _get_b2_config(self):
        key_id = str(getattr(settings, 'B2_KEY_ID', '') or '').strip()
        app_key = str(getattr(settings, 'B2_APPLICATION_KEY', '') or '').strip()
        bucket_name = (
            str(getattr(settings, 'B2_IMAGE_BUCKET_NAME', '') or '').strip()
            or str(getattr(settings, 'B2_BUCKET_NAME', '') or '').strip()
        )
        download_url = str(getattr(settings, 'B2_DOWNLOAD_URL', '') or '').strip()
        if not key_id or not app_key or not bucket_name or not download_url:
            raise CommandError('Missing B2 credentials/settings (B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME/B2_IMAGE_BUCKET_NAME, B2_DOWNLOAD_URL).')
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
        body = resp.json()
        return body['uploadUrl'], body['authorizationToken']

    def _content_sha1(self, data):
        h = hashlib.sha1()
        h.update(data)
        return h.hexdigest()

    def _upload_b2_file(self, upload_url, upload_auth, file_name, content, content_type):
        headers = {
            'Authorization': upload_auth,
            'X-Bz-File-Name': quote(file_name, safe='/'),
            'Content-Type': content_type,
            'X-Bz-Content-Sha1': self._content_sha1(content),
        }
        resp = requests.post(upload_url, headers=headers, data=content, timeout=90)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f'upload failed {resp.status_code}: {resp.text[:240]}')
        return resp.json()

    def _setup_cloudinary(self):
        cloud_name = str(getattr(settings, 'CLOUDINARY_CLOUD_NAME', '') or '').strip()
        cloud_key = str(getattr(settings, 'CLOUDINARY_API_KEY', '') or '').strip()
        cloud_secret = str(getattr(settings, 'CLOUDINARY_API_SECRET', '') or '').strip()
        if not (cloud_name and cloud_key and cloud_secret):
            return None
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=cloud_name,
            api_key=cloud_key,
            api_secret=cloud_secret,
            secure=True,
        )
        return cloudinary.uploader

    def _upload_cloudinary_image(self, uploader, image_bytes, public_id):
        result = uploader.upload(
            io.BytesIO(image_bytes),
            public_id=public_id,
            resource_type='image',
            overwrite=True,
        )
        secure_url = str(result.get('secure_url') or '').strip()
        if not secure_url:
            raise RuntimeError('Cloudinary upload missing secure_url')
        return secure_url

    def _collect_image_usages(self):
        usages = []

        for item in KPopGroup.objects.exclude(image_url__isnull=True).exclude(image_url='').only('id', 'image_url'):
            usages.append((str(item.image_url).strip(), 'KPopGroup', item.id, 'image_url'))

        for item in KPopMember.objects.exclude(image_url__isnull=True).exclude(image_url='').only('id', 'image_url'):
            usages.append((str(item.image_url).strip(), 'KPopMember', item.id, 'image_url'))

        for item in BlogArticle.objects.only('id', 'image', 'image_2', 'image_3'):
            if item.image:
                usages.append((str(item.image).strip(), 'BlogArticle', item.id, 'image'))
            if item.image_2:
                usages.append((str(item.image_2).strip(), 'BlogArticle', item.id, 'image_2'))
            if item.image_3:
                usages.append((str(item.image_3).strip(), 'BlogArticle', item.id, 'image_3'))

        return usages

    def _is_backblaze_url(self, url, b2_download_url):
        parsed = urlparse(url or '')
        host = (parsed.netloc or '').lower()
        b2_host = urlparse(b2_download_url or '').netloc.lower()
        return bool(host and (('backblazeb2.com' in host) or (b2_host and host == b2_host)))

    def _head_size(self, url):
        try:
            response = requests.head(url, timeout=20, allow_redirects=True)
            if response.status_code != 200:
                return 0
            return int(response.headers.get('content-length') or 0)
        except Exception:
            return 0

    def _download_image(self, url):
        response = requests.get(url, timeout=45, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200:
            raise RuntimeError(f'download status {response.status_code}')
        content_type = str(response.headers.get('content-type') or '').lower()
        if not content_type.startswith('image/'):
            raise RuntimeError(f'non-image content-type {content_type}')
        return response.content, content_type

    def _optimize_to_target(self, image_bytes, target_max_bytes, max_dim):
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))
        if getattr(image, 'is_animated', False):
            image.seek(0)

        if image.mode not in ('RGB', 'RGBA'):
            image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')

        width, height = image.size
        if max(width, height) > max_dim:
            ratio = max_dim / float(max(width, height))
            new_size = (max(1, int(width * ratio)), max(1, int(height * ratio)))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        best_bytes = None
        best_size = 0

        def encode_with(quality):
            buf = io.BytesIO()
            image.save(buf, format='WEBP', quality=quality, method=6)
            return buf.getvalue()

        for quality in (85, 80, 75, 70, 65, 60):
            candidate = encode_with(quality)
            candidate_size = len(candidate)
            if (best_bytes is None) or (candidate_size < best_size):
                best_bytes, best_size = candidate, candidate_size
            if candidate_size <= target_max_bytes:
                return candidate, candidate_size

        work_img = image
        while max(work_img.size) > 900:
            new_w = max(1, int(work_img.size[0] * 0.85))
            new_h = max(1, int(work_img.size[1] * 0.85))
            work_img = work_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            for quality in (70, 65, 60, 55):
                buf = io.BytesIO()
                work_img.save(buf, format='WEBP', quality=quality, method=6)
                candidate = buf.getvalue()
                candidate_size = len(candidate)
                if candidate_size < best_size:
                    best_bytes, best_size = candidate, candidate_size
                if candidate_size <= target_max_bytes:
                    return candidate, candidate_size

        return best_bytes, best_size

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

        return {
            'KPopGroup.image_url': update_model(KPopGroup, 'image_url'),
            'KPopMember.image_url': update_model(KPopMember, 'image_url'),
            'BlogArticle.image': update_model(BlogArticle, 'image'),
            'BlogArticle.image_2': update_model(BlogArticle, 'image_2'),
            'BlogArticle.image_3': update_model(BlogArticle, 'image_3'),
            'total': total,
        }

    def handle(self, *args, **options):
        self._require_pillow()

        threshold_mb = float(options.get('size_threshold_mb') or 10.0)
        target_max_bytes = int(threshold_mb * 1024 * 1024)
        max_dim = max(600, int(options.get('max_dim') or 2800))
        limit = max(0, int(options.get('limit') or 0))
        apply_updates = bool(options.get('apply'))
        no_cloudinary_direct = bool(options.get('no_cloudinary_direct'))
        output_path = Path(options.get('output') or 'media_url_map_b2_optimized.csv').resolve()

        key_id, app_key, bucket_name, b2_download_url = self._get_b2_config()
        auth = self._b2_authorize(key_id, app_key)
        bucket_id = self._b2_get_bucket_id(auth['apiUrl'], auth['authorizationToken'], auth['accountId'], bucket_name)
        upload_url, upload_auth = self._b2_get_upload_url(auth['apiUrl'], auth['authorizationToken'], bucket_id)

        cloudinary_uploader = None
        use_cloudinary_direct = not no_cloudinary_direct
        if use_cloudinary_direct:
            cloudinary_uploader = self._setup_cloudinary()
            if cloudinary_uploader is None:
                self.stdout.write(self.style.WARNING('Cloudinary credentials missing; falling back to B2 optimization only.'))
                use_cloudinary_direct = False

        usages = self._collect_image_usages()
        unique_urls = []
        seen = set()
        for url, _model, _id, _field in usages:
            if not url or url in seen:
                continue
            if not self._is_backblaze_url(url, b2_download_url):
                continue
            seen.add(url)
            unique_urls.append(url)

        oversized = []
        for idx, url in enumerate(unique_urls, start=1):
            size = self._head_size(url)
            if size > target_max_bytes:
                oversized.append((url, size))
            if idx % 100 == 0:
                self.stdout.write(f'Scanned {idx}/{len(unique_urls)} for size...')

        if limit > 0:
            oversized = oversized[:limit]

        self.stdout.write(self.style.NOTICE(f'Oversized B2 images found: {len(oversized)} (threshold={threshold_mb:.2f}MB)'))

        mapping = {}
        report_rows = []
        failures = 0

        for index, (old_url, old_size) in enumerate(oversized, start=1):
            row = {
                'old_url': old_url,
                'new_url': '',
                'old_size_bytes': old_size,
                'new_size_bytes': 0,
                'status': 'skipped',
                'delivery': '',
                'error': '',
            }
            try:
                original_bytes, _content_type = self._download_image(old_url)
                digest = hashlib.sha1(old_url.encode('utf-8')).hexdigest()

                if use_cloudinary_direct and cloudinary_uploader is not None:
                    public_id = f'ksync/images/oversized/{digest}'
                    try:
                        cloud_url = self._upload_cloudinary_image(cloudinary_uploader, original_bytes, public_id)
                        mapping[old_url] = cloud_url
                        row.update({
                            'new_url': cloud_url,
                            'new_size_bytes': len(original_bytes),
                            'status': 'migrated',
                            'delivery': 'cloudinary_direct',
                        })
                    except Exception:
                        optimized_bytes, optimized_size = self._optimize_to_target(original_bytes, target_max_bytes, max_dim)
                        if not optimized_bytes or optimized_size <= 0:
                            raise RuntimeError('optimizer produced empty output for cloudinary fallback')
                        if optimized_size > target_max_bytes:
                            raise RuntimeError(f'could_not_reduce_below_threshold_for_cloudinary size={optimized_size}')

                        cloud_url = self._upload_cloudinary_image(cloudinary_uploader, optimized_bytes, public_id)
                        mapping[old_url] = cloud_url
                        row.update({
                            'new_url': cloud_url,
                            'new_size_bytes': optimized_size,
                            'status': 'optimized',
                            'delivery': 'cloudinary_optimized',
                        })
                else:
                    optimized_bytes, optimized_size = self._optimize_to_target(original_bytes, target_max_bytes, max_dim)
                    if not optimized_bytes or optimized_size <= 0:
                        raise RuntimeError('optimizer produced empty output')
                    if optimized_size > target_max_bytes:
                        raise RuntimeError(f'could_not_reduce_below_threshold size={optimized_size}')

                    file_name = f'media/images/optimized/{digest}.webp'
                    self._upload_b2_file(upload_url, upload_auth, file_name, optimized_bytes, 'image/webp')
                    new_url = f"{b2_download_url.rstrip('/')}/file/{bucket_name}/{quote(file_name, safe='/')}"

                    mapping[old_url] = new_url
                    row.update({
                        'new_url': new_url,
                        'new_size_bytes': optimized_size,
                        'status': 'optimized',
                        'delivery': 'b2_optimized',
                    })
            except Exception as exc:
                failures += 1
                row['status'] = 'failed'
                row['error'] = str(exc)

            report_rows.append(row)

            if index % 10 == 0:
                self.stdout.write(f'Processed {index}/{len(oversized)} oversized images...')

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=['old_url', 'new_url', 'old_size_bytes', 'new_size_bytes', 'status', 'delivery', 'error'],
            )
            writer.writeheader()
            writer.writerows(report_rows)

        self.stdout.write(self.style.SUCCESS(f'Optimization mapping written: {output_path}'))
        self.stdout.write(self.style.NOTICE(f'Optimized mappings ready: {len(mapping)}, failures: {failures}'))

        if apply_updates and mapping:
            summary = self._apply_mapping(mapping)
            self.stdout.write(self.style.SUCCESS(f'Applied DB updates: {summary}'))
        elif apply_updates and not mapping:
            self.stdout.write(self.style.WARNING('No optimized mappings to apply.'))
        else:
            self.stdout.write(self.style.NOTICE('Dry-run mode (no DB updates). Use --apply to persist.'))
