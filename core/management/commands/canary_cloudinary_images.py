import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import BlogArticle, KPopGroup, KPopMember


class Command(BaseCommand):
    help = (
        "Run Cloudinary fetch canary checks against B2 image URLs and optionally "
        "enable IMAGE_STREAM_USE_CLOUDINARY_FETCH in an env file on full success."
    )

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=10, help='Number of unique B2 URLs to test (0 = all).')
        parser.add_argument('--timeout', type=float, default=20.0, help='HTTP timeout for each URL check.')
        parser.add_argument('--auto-enable', action='store_true', help='Enable IMAGE_STREAM_USE_CLOUDINARY_FETCH=true only if canary fully passes.')
        parser.add_argument('--env-file', type=str, default='.env', help='Env file to update when using --auto-enable.')
        parser.add_argument('--output', type=str, default='', help='Optional output CSV file path.')

    def _default_output_path(self):
        stamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        reports_dir = Path('tmp') / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir / f'cloudinary_image_canary_{stamp}.csv'

    def _iter_source_urls(self):
        for item in KPopGroup.objects.exclude(image_url__isnull=True).exclude(image_url='').only('image_url'):
            yield str(item.image_url).strip()
        for item in KPopMember.objects.exclude(image_url__isnull=True).exclude(image_url='').only('image_url'):
            yield str(item.image_url).strip()
        for item in BlogArticle.objects.only('image', 'image_2', 'image_3'):
            if item.image:
                yield str(item.image).strip()
            if item.image_2:
                yield str(item.image_2).strip()
            if item.image_3:
                yield str(item.image_3).strip()

    def _is_backblaze_url(self, url):
        parsed = urlparse(url or '')
        host = (parsed.netloc or '').lower()
        if not host:
            return False
        b2_host = urlparse(str(getattr(settings, 'B2_DOWNLOAD_URL', '') or '')).netloc.lower()
        return ('backblazeb2.com' in host) or (b2_host and host == b2_host)

    def _build_cloudinary_fetch_url(self, source_url):
        cloud_name = str(getattr(settings, 'CLOUDINARY_CLOUD_NAME', '') or '').strip()
        if not cloud_name:
            raise CommandError('Missing CLOUDINARY_CLOUD_NAME setting.')
        transform = str(getattr(settings, 'IMAGE_STREAM_CLOUDINARY_TRANSFORM', 'f_auto,q_auto') or '').strip()
        encoded = quote(source_url, safe='')
        if transform:
            return f'https://res.cloudinary.com/{cloud_name}/image/fetch/{transform}/{encoded}'
        return f'https://res.cloudinary.com/{cloud_name}/image/fetch/{encoded}'

    def _upsert_env_var(self, env_path, key, value):
        env_file = Path(env_path)
        if env_file.exists():
            lines = env_file.read_text(encoding='utf-8').splitlines()
        else:
            lines = []

        updated = False
        new_lines = []
        prefix = f'{key}='
        for line in lines:
            if line.strip().startswith(prefix):
                new_lines.append(f'{key}={value}')
                updated = True
            else:
                new_lines.append(line)

        if not updated:
            if new_lines and new_lines[-1].strip() != '':
                new_lines.append('')
            new_lines.append(f'{key}={value}')

        env_file.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')

    def handle(self, *args, **options):
        limit = max(0, int(options.get('limit') or 0))
        timeout = max(2.0, float(options.get('timeout') or 20.0))
        auto_enable = bool(options.get('auto_enable'))
        env_file = str(options.get('env_file') or '.env').strip()

        all_urls = []
        seen = set()
        for url in self._iter_source_urls():
            if not url or url in seen:
                continue
            seen.add(url)
            all_urls.append(url)

        b2_urls = [url for url in all_urls if self._is_backblaze_url(url)]
        if limit > 0:
            b2_urls = b2_urls[:limit]

        if not b2_urls:
            raise CommandError('No Backblaze image URLs found for canary checks.')

        self.stdout.write(self.style.NOTICE(f'Checking Cloudinary fetch for {len(b2_urls)} B2 image URL(s)...'))

        results = []
        for idx, source_url in enumerate(b2_urls, start=1):
            cloudinary_url = self._build_cloudinary_fetch_url(source_url)
            status = 0
            content_type = ''
            error = ''
            ok = False
            try:
                response = requests.get(cloudinary_url, timeout=timeout, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
                status = int(response.status_code)
                content_type = str(response.headers.get('content-type') or '')
                ok = (status == 200) and content_type.lower().startswith('image/')
                if not ok:
                    error = f'status={status}, content_type={content_type}'
            except Exception as exc:
                error = str(exc)

            results.append({
                'source_url': source_url,
                'cloudinary_url': cloudinary_url,
                'status': status,
                'content_type': content_type,
                'ok': int(ok),
                'error': error,
            })

            if idx % 25 == 0:
                self.stdout.write(f'Checked {idx}/{len(b2_urls)}...')

        output_path = Path(options.get('output') or '') if options.get('output') else self._default_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['source_url', 'cloudinary_url', 'status', 'content_type', 'ok', 'error'])
            writer.writeheader()
            writer.writerows(results)

        total = len(results)
        passed = sum(1 for item in results if item['ok'] == 1)
        failed = total - passed

        host_counts = Counter(urlparse(item['source_url']).netloc.lower() for item in results)
        top_hosts = ', '.join(f'{h}:{c}' for h, c in host_counts.most_common(5))

        self.stdout.write(self.style.SUCCESS(f'Canary report written: {output_path}'))
        self.stdout.write(self.style.NOTICE(f'Canary results: pass={passed}, fail={failed}, total={total}'))
        self.stdout.write(self.style.NOTICE(f'Source hosts: {top_hosts or "n/a"}'))

        if failed > 0:
            self.stdout.write(self.style.WARNING('Canary failed; IMAGE_STREAM_USE_CLOUDINARY_FETCH was not changed.'))
            return

        self.stdout.write(self.style.SUCCESS('Canary passed 100%.'))
        if auto_enable:
            self._upsert_env_var(env_file, 'IMAGE_STREAM_USE_CLOUDINARY_FETCH', 'true')
            self.stdout.write(self.style.SUCCESS(f'Updated {env_file}: IMAGE_STREAM_USE_CLOUDINARY_FETCH=true'))
            self.stdout.write(self.style.NOTICE('Restart application processes to apply new settings.'))
