import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import KPopGroup, KPopMember, BlogArticle


class Command(BaseCommand):
    help = (
        "Safely remap media URLs for idol/blog image fields using a CSV map. "
        "Default is dry-run; pass --apply to persist changes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--map-file',
            type=str,
            required=True,
            help='CSV file with columns: old_url,new_url',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Persist updates. If omitted, command runs in dry-run mode.',
        )

    def _load_map(self, map_file_path):
        mapping = {}
        path = Path(map_file_path)
        if not path.exists():
            raise CommandError(f'Map file not found: {path}')

        with path.open('r', encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            missing_cols = {'old_url', 'new_url'} - set(reader.fieldnames or [])
            if missing_cols:
                raise CommandError(
                    f'Map file must contain columns old_url,new_url. Missing: {", ".join(sorted(missing_cols))}'
                )

            for row in reader:
                old_url = str(row.get('old_url') or '').strip()
                new_url = str(row.get('new_url') or '').strip()
                if not old_url or not new_url:
                    continue
                mapping[old_url] = new_url

        if not mapping:
            raise CommandError('No valid mapping rows found in CSV.')
        return mapping

    def _update_model_field(self, model, field_name, mapping, apply):
        matched = 0
        updated = 0

        queryset = model.objects.exclude(**{f'{field_name}__isnull': True}).exclude(**{field_name: ''})
        for obj in queryset.iterator():
            old_val = str(getattr(obj, field_name, '') or '').strip()
            new_val = mapping.get(old_val)
            if not new_val:
                continue

            matched += 1
            if apply:
                setattr(obj, field_name, new_val)
                obj.save(update_fields=[field_name])
                updated += 1

        return matched, updated

    def handle(self, *args, **options):
        mapping = self._load_map(options['map_file'])
        apply_updates = bool(options.get('apply'))

        targets = [
            (KPopGroup, 'image_url'),
            (KPopMember, 'image_url'),
            (BlogArticle, 'image'),
            (BlogArticle, 'image_2'),
            (BlogArticle, 'image_3'),
        ]

        total_matched = 0
        total_updated = 0

        self.stdout.write(self.style.NOTICE(f'Loaded {len(mapping)} URL mappings.'))
        self.stdout.write(self.style.NOTICE('Mode: APPLY' if apply_updates else 'Mode: DRY-RUN'))

        for model, field_name in targets:
            matched, updated = self._update_model_field(model, field_name, mapping, apply_updates)
            total_matched += matched
            total_updated += updated
            self.stdout.write(f'- {model.__name__}.{field_name}: matched={matched}, updated={updated}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Completed. total_matched={total_matched}, total_updated={total_updated}, apply={apply_updates}'
            )
        )
