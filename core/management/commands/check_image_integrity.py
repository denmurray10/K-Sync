import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.core.management.base import BaseCommand

from core.models import BlogArticle, KPopGroup, KPopMember


class Command(BaseCommand):
    help = "HTTP-check image URLs used by idols/blog fields and write a CSV report."

    def add_arguments(self, parser):
        parser.add_argument('--output', type=str, default='', help='Optional output CSV path')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of URLs to check (0 = all)')
        parser.add_argument('--timeout', type=float, default=15.0, help='Request timeout in seconds')

    def _iter_url_rows(self):
        for item in KPopGroup.objects.exclude(image_url__isnull=True).exclude(image_url='').only('id', 'image_url'):
            yield ('KPopGroup', item.id, 'image_url', str(item.image_url).strip())

        for item in KPopMember.objects.exclude(image_url__isnull=True).exclude(image_url='').only('id', 'image_url'):
            yield ('KPopMember', item.id, 'image_url', str(item.image_url).strip())

        for item in BlogArticle.objects.only('id', 'image', 'image_2', 'image_3'):
            if item.image:
                yield ('BlogArticle', item.id, 'image', str(item.image).strip())
            if item.image_2:
                yield ('BlogArticle', item.id, 'image_2', str(item.image_2).strip())
            if item.image_3:
                yield ('BlogArticle', item.id, 'image_3', str(item.image_3).strip())

    def _default_output_path(self):
        stamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        reports_dir = Path('tmp') / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir / f'image_integrity_{stamp}.csv'

    def handle(self, *args, **options):
        limit = max(0, int(options.get('limit') or 0))
        timeout = max(2.0, float(options.get('timeout') or 15.0))

        rows = list(self._iter_url_rows())
        unique_urls = []
        seen = set()
        for _model, _id, _field, url in rows:
            if not url or url in seen:
                continue
            seen.add(url)
            unique_urls.append(url)

        if limit > 0:
            unique_urls = unique_urls[:limit]

        usage_count = Counter(url for _m, _i, _f, url in rows if url)
        status_map = {}

        self.stdout.write(self.style.NOTICE(f'Checking {len(unique_urls)} unique image URL(s)...'))

        for index, url in enumerate(unique_urls, start=1):
            status = 0
            error = ''
            content_type = ''
            try:
                response = requests.get(url, timeout=timeout, allow_redirects=True, headers={'User-Agent': 'Mozilla/5.0'})
                status = int(response.status_code)
                content_type = str(response.headers.get('content-type') or '')
                if (status == 200) and (not content_type.lower().startswith('image/')):
                    error = f'non-image content-type: {content_type}'
            except Exception as exc:
                error = str(exc)

            status_map[url] = {
                'status': status,
                'ok': status == 200 and (not error),
                'error': error,
                'content_type': content_type,
            }

            if index % 50 == 0:
                self.stdout.write(f'Checked {index}/{len(unique_urls)}...')

        output = Path(options.get('output') or '') if options.get('output') else self._default_output_path()
        output.parent.mkdir(parents=True, exist_ok=True)

        with output.open('w', encoding='utf-8', newline='') as file_handle:
            writer = csv.writer(file_handle)
            writer.writerow(['model', 'object_id', 'field', 'url', 'host', 'status', 'ok', 'usage_count', 'content_type', 'error'])
            for model, object_id, field, url in rows:
                result = status_map.get(url, {'status': 0, 'ok': False, 'error': 'not_checked', 'content_type': ''})
                writer.writerow([
                    model,
                    object_id,
                    field,
                    url,
                    urlparse(url).netloc.lower() if url else '',
                    result['status'],
                    int(bool(result['ok'])),
                    usage_count.get(url, 0),
                    result.get('content_type', ''),
                    result.get('error', ''),
                ])

        total_unique = len(unique_urls)
        unique_ok = sum(1 for value in status_map.values() if value['ok'])
        unique_fail = total_unique - unique_ok

        checked_urls = set(status_map.keys())
        total_rows = len(rows)
        row_checked = sum(1 for _m, _i, _f, u in rows if u in checked_urls)
        row_fail = sum(1 for _m, _i, _f, u in rows if (u in checked_urls) and (not status_map.get(u, {}).get('ok')))
        row_unchecked = total_rows - row_checked

        host_counter = Counter((urlparse(url).netloc.lower() if url else '') for url in unique_urls)
        top_hosts = ', '.join(f'{host}:{count}' for host, count in host_counter.most_common(5))

        self.stdout.write(self.style.SUCCESS(f'Image integrity report written: {output}'))
        self.stdout.write(self.style.NOTICE(f'Unique URLs: ok={unique_ok}, fail={unique_fail}, total={total_unique}'))
        self.stdout.write(self.style.NOTICE(f'Field rows checked: {row_checked}/{total_rows} (unchecked={row_unchecked})'))
        self.stdout.write(self.style.NOTICE(f'Field rows failing among checked: {row_fail}'))
        self.stdout.write(self.style.NOTICE(f'Top hosts: {top_hosts or "n/a"}'))

        if unique_fail > 0:
            self.stdout.write(self.style.WARNING('Some image URLs failed checks. Review report for details.'))
