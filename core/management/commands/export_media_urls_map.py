import csv
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import KPopGroup, KPopMember, BlogArticle


class Command(BaseCommand):
    help = (
        "Export current idol/blog media URLs to a CSV mapping template "
        "with columns old_url,new_url for migrate_media_urls."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='media_url_map_template.csv',
            help='Output CSV path (default: media_url_map_template.csv)',
        )

    def _collect_url_usage(self):
        usage = defaultdict(lambda: {'count': 0, 'examples': []})

        def add(url, label):
            value = str(url or '').strip()
            if not value:
                return
            entry = usage[value]
            entry['count'] += 1
            if len(entry['examples']) < 5:
                entry['examples'].append(label)

        for item in KPopGroup.objects.exclude(image_url__isnull=True).exclude(image_url='').only('id', 'slug', 'image_url'):
            add(item.image_url, f'KPopGroup:{item.id}:{item.slug}:image_url')

        for item in KPopMember.objects.exclude(image_url__isnull=True).exclude(image_url='').only('id', 'name', 'image_url'):
            add(item.image_url, f'KPopMember:{item.id}:{item.name}:image_url')

        for item in BlogArticle.objects.only('id', 'slug', 'image', 'image_2', 'image_3'):
            if item.image:
                add(item.image, f'BlogArticle:{item.id}:{item.slug}:image')
            if item.image_2:
                add(item.image_2, f'BlogArticle:{item.id}:{item.slug}:image_2')
            if item.image_3:
                add(item.image_3, f'BlogArticle:{item.id}:{item.slug}:image_3')

        return usage

    def handle(self, *args, **options):
        output_path = Path(options['output']).resolve()
        usage = self._collect_url_usage()

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['old_url', 'new_url', 'usage_count', 'example_refs'])

            for old_url in sorted(usage.keys()):
                meta = usage[old_url]
                writer.writerow([
                    old_url,
                    '',
                    meta['count'],
                    ' | '.join(meta['examples']),
                ])

        self.stdout.write(self.style.SUCCESS(
            f'Exported {len(usage)} unique media URLs to: {output_path}'
        ))
        self.stdout.write(self.style.NOTICE(
            'Fill the new_url column, then run: '
            f'python manage.py migrate_media_urls --map-file "{output_path}" --apply'
        ))
