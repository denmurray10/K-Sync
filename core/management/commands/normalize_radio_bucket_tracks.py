from django.core.management.base import BaseCommand

from core.models import RadioTrack
from core.views import (
    _canonicalize_radio_bucket_audio_url,
    _is_supported_live_audio_url,
    _normalize_live_audio_path,
)


class Command(BaseCommand):
    help = (
        "Audit radio tracks so the live player only uses direct Backblaze "
        "StrayKids/Music files with browser-safe extensions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Clear audio_url on unsupported radio tracks so they cannot be selected by legacy state.",
        )

    def handle(self, *args, **options):
        apply_changes = bool(options["apply"])
        supported = 0
        unsupported = []

        for track in RadioTrack.objects.exclude(audio_url__isnull=True).exclude(audio_url="").order_by("artist", "title", "id"):
            path = _normalize_live_audio_path(track.audio_url)
            if _is_supported_live_audio_url(track.audio_url):
                supported += 1
                continue
            unsupported.append((track, path))

        self.stdout.write(self.style.SUCCESS(f"Supported live tracks: {supported}"))
        self.stdout.write(self.style.WARNING(f"Unsupported live tracks: {len(unsupported)}"))

        for track, path in unsupported[:50]:
            self.stdout.write(f"- #{track.id} {track.artist} - {track.title} -> {path or track.audio_url}")

        if apply_changes and unsupported:
            updated = 0
            cleared = 0
            for track, _path in unsupported:
                canonical = _canonicalize_radio_bucket_audio_url(track.audio_url)
                if canonical:
                    track.audio_url = canonical
                    track.save(update_fields=["audio_url"])
                    updated += 1
                    continue
                if track.audio_url:
                    track.audio_url = ""
                    track.save(update_fields=["audio_url"])
                    cleared += 1
            self.stdout.write(self.style.SUCCESS(f"Rewrote {updated} track URL(s) to StrayKids/Music."))
            if cleared:
                self.stdout.write(self.style.WARNING(f"Cleared audio_url on {cleared} unsupported track(s) with no safe Music-path rewrite."))
        elif unsupported and not apply_changes:
            self.stdout.write("Run with --apply to rewrite legacy URLs into StrayKids/Music and clear anything still unsupported.")
