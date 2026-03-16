import io
import os
import urllib.parse

from django.conf import settings
from django.core.management.base import BaseCommand

from core.models import RadioTrack


DEFAULT_ALBUM_ART_URL = "https://res.cloudinary.com/diuanqnce/image/upload/v1710546648/ksync/skz_group_default.jpg"


def _is_vo_track(track: RadioTrack) -> bool:
    return str(track.title or "").strip().startswith("VO:")


def _looks_local_voiceover_url(url: str) -> bool:
    value = str(url or "").strip().lower()
    if not value:
        return False
    if "/media/radio/voiceovers/" in value:
        return True
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme in ("http", "https") and parsed.netloc.lower().startswith("localhost"):
        return "/media/radio/voiceovers/" in parsed.path.lower()
    return False


def _filename_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(str(url or "").strip())
    path = urllib.parse.unquote(parsed.path or "")
    return os.path.basename(path)


class Command(BaseCommand):
    help = "Upload local voiceover files to Cloudinary and rewrite RadioTrack audio_url to online URLs."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Show planned updates without writing DB changes.')
        parser.add_argument('--delete-local', action='store_true', help='Delete local voiceover files after successful upload.')
        parser.add_argument('--fill-missing-album-art', action='store_true', help='Fill missing album_art with default online Cloudinary URL.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        delete_local = options['delete_local']
        fill_missing_album_art = options['fill_missing_album_art']

        cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', '')
        cloud_key = getattr(settings, 'CLOUDINARY_API_KEY', '')
        cloud_secret = getattr(settings, 'CLOUDINARY_API_SECRET', '')
        can_upload_to_cloudinary = bool(cloud_name and cloud_key and cloud_secret)

        if not can_upload_to_cloudinary:
            self.stdout.write(self.style.WARNING('Cloudinary credentials are incomplete; audio migration will be skipped.'))

        if can_upload_to_cloudinary:
            import cloudinary
            import cloudinary.uploader

            cloudinary.config(
                cloud_name=cloud_name,
                api_key=cloud_key,
                api_secret=cloud_secret,
                secure=True,
            )

        tracks = list(RadioTrack.objects.all())
        vo_candidates = [
            track for track in tracks
            if _is_vo_track(track) and _looks_local_voiceover_url(track.audio_url)
        ]

        self.stdout.write(f'Voiceover migration candidates: {len(vo_candidates)}')

        uploaded = 0
        skipped = 0
        failed = 0

        for track in vo_candidates:
            if not can_upload_to_cloudinary:
                skipped += 1
                continue

            source_url = str(track.audio_url or '').strip()
            filename = _filename_from_url(source_url)
            stem, ext = os.path.splitext(filename)
            ext = (ext or '.mp3').lower()
            if not stem:
                stem = f'vo-track-{track.id}'

            absolute_path = os.path.join(getattr(settings, 'MEDIA_ROOT', ''), 'radio', 'voiceovers', filename)

            audio_bytes = b''
            if os.path.isfile(absolute_path):
                try:
                    with open(absolute_path, 'rb') as file_handle:
                        audio_bytes = file_handle.read()
                except Exception:
                    audio_bytes = b''

            if not audio_bytes:
                failed += 1
                self.stdout.write(self.style.WARNING(f'FAIL  [VO] track#{track.id} {track.title} (file not found: {filename})'))
                continue

            try:
                if not dry_run:
                    result = cloudinary.uploader.upload(
                        io.BytesIO(audio_bytes),
                        public_id=f'ksync/radio/voiceovers/{stem}',
                        resource_type='video',
                        format=ext.lstrip('.'),
                        overwrite=True,
                    )
                    secure_url = (result.get('secure_url') or '').strip()
                    if not secure_url:
                        raise ValueError('Missing secure_url from Cloudinary upload response')
                    track.audio_url = secure_url
                    track.save(update_fields=['audio_url'])

                    if delete_local and os.path.isfile(absolute_path):
                        try:
                            os.remove(absolute_path)
                        except Exception:
                            pass

                uploaded += 1
                self.stdout.write(self.style.SUCCESS(f'OK    [VO] track#{track.id} {track.title}'))
            except Exception as error:
                failed += 1
                self.stdout.write(self.style.WARNING(f'FAIL  [VO] track#{track.id} {track.title}: {error}'))

        album_art_filled = 0
        if fill_missing_album_art:
            art_qs = RadioTrack.objects.filter(album_art__isnull=True) | RadioTrack.objects.filter(album_art='')
            for track in art_qs:
                if not dry_run:
                    track.album_art = DEFAULT_ALBUM_ART_URL
                    track.save(update_fields=['album_art'])
                album_art_filled += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Voiceovers migrated: {uploaded}'))
        self.stdout.write(f'Voiceovers skipped: {skipped}')
        self.stdout.write(self.style.WARNING(f'Voiceovers failed: {failed}'))
        if fill_missing_album_art:
            self.stdout.write(self.style.SUCCESS(f'Album art filled: {album_art_filled}'))
