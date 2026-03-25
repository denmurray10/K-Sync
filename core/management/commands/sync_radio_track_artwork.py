import re
from difflib import SequenceMatcher

import requests
from django.core.management.base import BaseCommand
from django.db.models import Q

from core.models import RadioTrack


ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
DEEZER_SEARCH_URL = "https://api.deezer.com/search"
USER_AGENT = "KSyncArtworkSync/1.0"


def _clean_text(value):
    text = str(value or "").strip().lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"\b(feat|ft|featuring|with|prod|ver|version|remix)\b.*$", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _token_set(value):
    cleaned = _clean_text(value)
    return {token for token in cleaned.split(" ") if token}


def _ratio(left, right):
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, _clean_text(left), _clean_text(right)).ratio()


def _token_overlap(left, right):
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    shared = len(left_tokens & right_tokens)
    largest = max(len(left_tokens), len(right_tokens))
    return shared / largest if largest else 0.0


def _score_candidate(track, candidate):
    artist_score = max(
        _ratio(track.artist, candidate.get("artist")),
        _token_overlap(track.artist, candidate.get("artist")),
    )
    title_score = max(
        _ratio(track.title, candidate.get("title")),
        _token_overlap(track.title, candidate.get("title")),
    )

    # Favor title quality slightly more because artist names can vary by credits.
    score = (artist_score * 0.42) + (title_score * 0.58)

    if _clean_text(track.artist) and _clean_text(track.artist) == _clean_text(candidate.get("artist")):
        score += 0.08
    if _clean_text(track.title) and _clean_text(track.title) == _clean_text(candidate.get("title")):
        score += 0.1

    return round(min(score, 1.0), 4)


def _build_queries(track):
    raw_title = str(track.title or "").strip()
    raw_artist = str(track.artist or "").strip()
    cleaned_title = _clean_text(raw_title)
    cleaned_artist = _clean_text(raw_artist)

    queries = []
    for query in (
        f"{raw_artist} {raw_title}".strip(),
        f"{cleaned_artist} {cleaned_title}".strip(),
        raw_title,
        cleaned_title,
    ):
        if query and query not in queries:
            queries.append(query)
    return queries


def _itunes_candidates(query, timeout):
    response = requests.get(
        ITUNES_SEARCH_URL,
        params={"term": query, "entity": "song", "limit": 5},
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json() or {}
    rows = payload.get("results") or []
    candidates = []
    for row in rows:
        artwork = str(row.get("artworkUrl100") or "").strip()
        if not artwork:
            continue
        candidates.append(
            {
                "provider": "itunes",
                "artist": str(row.get("artistName") or "").strip(),
                "title": str(row.get("trackName") or "").strip(),
                "artwork_url": artwork.replace("100x100bb", "600x600bb").replace("60x60bb", "600x600bb"),
                "source_url": str(row.get("trackViewUrl") or row.get("collectionViewUrl") or "").strip(),
            }
        )
    return candidates


def _deezer_candidates(query, timeout):
    response = requests.get(
        DEEZER_SEARCH_URL,
        params={"q": query, "limit": 5},
        headers={"User-Agent": USER_AGENT},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json() or {}
    rows = payload.get("data") or []
    candidates = []
    for row in rows:
        album = row.get("album") or {}
        artwork = ""
        for key in ("cover_xl", "cover_big", "cover_medium", "cover"):
            artwork = str(album.get(key) or "").strip()
            if artwork:
                break
        if not artwork:
            continue
        candidates.append(
            {
                "provider": "deezer",
                "artist": str((row.get("artist") or {}).get("name") or "").strip(),
                "title": str(row.get("title") or "").strip(),
                "artwork_url": artwork,
                "source_url": str(row.get("link") or "").strip(),
            }
        )
    return candidates


def _find_best_artwork(track, timeout, min_score):
    seen = set()
    best = None
    errors = []

    for query in _build_queries(track):
        for provider in (_itunes_candidates, _deezer_candidates):
            try:
                candidates = provider(query, timeout)
            except Exception as error:
                errors.append(f"{provider.__name__}:{error}")
                continue

            for candidate in candidates:
                dedupe_key = (
                    candidate.get("provider"),
                    _clean_text(candidate.get("artist")),
                    _clean_text(candidate.get("title")),
                    candidate.get("artwork_url"),
                )
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)

                score = _score_candidate(track, candidate)
                candidate["score"] = score

                if score < min_score:
                    continue
                if best is None or score > best["score"]:
                    best = candidate

    return best, errors


class Command(BaseCommand):
    help = "Search external music providers and backfill RadioTrack album_art matches."

    def add_arguments(self, parser):
        parser.add_argument("--only-missing", action="store_true", help="Only process tracks with blank album_art.")
        parser.add_argument("--limit", type=int, default=0, help="Maximum number of tracks to process.")
        parser.add_argument("--min-score", type=float, default=0.72, help="Minimum match score required to save artwork.")
        parser.add_argument("--timeout", type=float, default=4.0, help="Per-provider request timeout in seconds.")
        parser.add_argument("--dry-run", action="store_true", help="Preview matches without saving them.")
        parser.add_argument("--force-refresh", action="store_true", help="Refresh artwork even when album_art is already set.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        only_missing = options["only_missing"]
        force_refresh = options["force_refresh"]
        timeout = float(options["timeout"])
        min_score = float(options["min_score"])
        limit = int(options["limit"] or 0)

        queryset = RadioTrack.objects.all().order_by("artist", "title")
        if only_missing and not force_refresh:
            queryset = queryset.filter(Q(album_art__isnull=True) | Q(album_art=""))
        elif not force_refresh:
            queryset = queryset.filter(Q(album_art__isnull=True) | Q(album_art=""))

        if limit > 0:
            queryset = queryset[:limit]

        tracks = list(queryset)
        self.stdout.write(f"Artwork sync candidates: {len(tracks)}")

        updated = 0
        matched = 0
        skipped = 0
        failed = 0

        for index, track in enumerate(tracks, start=1):
            prefix = f"[{index}/{len(tracks)}] track#{track.id} {track.artist} - {track.title}"
            best, errors = _find_best_artwork(track, timeout=timeout, min_score=min_score)

            if not best:
                failed += 1
                if errors:
                    self.stdout.write(self.style.WARNING(f"{prefix} -> no match ({'; '.join(errors[:2])})"))
                else:
                    self.stdout.write(self.style.WARNING(f"{prefix} -> no match"))
                continue

            matched += 1
            current_art = str(track.album_art or "").strip()
            next_art = str(best.get("artwork_url") or "").strip()
            if current_art == next_art:
                skipped += 1
                self.stdout.write(f"{prefix} -> unchanged via {best['provider']} score={best['score']}")
                continue

            if not dry_run:
                track.album_art = next_art
                track.save(update_fields=["album_art"])
            updated += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"{prefix} -> {best['provider']} score={best['score']} {('[dry-run] ' if dry_run else '')}{next_art}"
                )
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Matched: {matched}"))
        self.stdout.write(self.style.SUCCESS(f"Updated: {updated}"))
        self.stdout.write(f"Unchanged: {skipped}")
        self.stdout.write(self.style.WARNING(f"No match: {failed}"))
