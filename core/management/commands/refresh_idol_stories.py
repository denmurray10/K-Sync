import re

from django.core.management.base import BaseCommand

from core.models import KPopGroup
from core.views import _chat_reasoner


def _clean_story(text: str) -> str:
    raw = str(text or "").strip()
    raw = re.sub(r"\r\n?", "\n", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    raw = re.sub(r"^\s*(The Story|About)\s*:?\s*", "", raw, flags=re.IGNORECASE)
    return raw.strip()


class Command(BaseCommand):
    help = "Refresh idol profile stories with richer two-paragraph DeepSeek copy."

    def add_arguments(self, parser):
        parser.add_argument("--slug", help="Refresh only one group by slug.")
        parser.add_argument("--limit", type=int, default=0, help="Maximum number of groups to refresh.")
        parser.add_argument("--force", action="store_true", help="Refresh all matched groups, even if already long.")
        parser.add_argument("--dry-run", action="store_true", help="Generate without saving.")

    def handle(self, *args, **options):
        slug = str(options.get("slug") or "").strip()
        limit = int(options.get("limit") or 0)
        force = bool(options.get("force"))
        dry_run = bool(options.get("dry_run"))

        qs = KPopGroup.objects.prefetch_related("members").all().order_by("rank", "name")
        if slug:
            qs = qs.filter(slug=slug)

        groups = list(qs)
        if not force:
            groups = [group for group in groups if len(str(group.description or "").strip()) < 420]
        if limit > 0:
            groups = groups[:limit]

        if not groups:
            self.stdout.write(self.style.WARNING("No groups matched the refresh filters."))
            return

        self.stdout.write(f"Refreshing stories for {len(groups)} group(s)...")
        updated = 0
        failed = 0

        for group in groups:
            member_names = ", ".join(
                [
                    (member.stage_name or member.name or "").strip()
                    for member in group.members.all()[:12]
                    if (member.stage_name or member.name or "").strip()
                ]
            ) or "line-up varies by era"

            prompt = (
                f"Write a polished artist profile for the K-pop act {group.name}. "
                f"Use exactly 2 paragraphs, each 4 to 6 sentences long. "
                f"Cover their formation or rise, musical identity, key eras or releases, performance style, fandom impact, and why they matter in K-pop. "
                f"Keep it factual, vivid, and readable for fans on an idol profile page. "
                f"Avoid bullet points, headings, markdown, and empty hype. "
                f"Act type: {group.get_group_type_display()}. "
                f"Label: {group.label or 'Unknown label'}. "
                f"Known members: {member_names}."
            )

            try:
                story = _clean_story(
                    _chat_reasoner(
                        prompt,
                        system="You are an expert K-pop editor writing premium artist profile copy for a fan platform.",
                    )
                )
            except Exception as exc:
                failed += 1
                self.stdout.write(self.style.WARNING(f"FAIL  {group.name}: {exc}"))
                continue

            if len(story) < 250:
                failed += 1
                self.stdout.write(self.style.WARNING(f"FAIL  {group.name}: generated story too short"))
                continue

            if not dry_run:
                group.description = story
                group.save(update_fields=["description"])

            updated += 1
            self.stdout.write(self.style.SUCCESS(f"OK    {group.name}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Updated: {updated}"))
        self.stdout.write(self.style.WARNING(f"Failed: {failed}"))
