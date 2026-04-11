import json
import re

from django.core.management.base import BaseCommand

from core.models import BirthdayFeature, KPopMember
from core.views import _chat_reasoner


def _clean_text(text):
    raw = str(text or "").strip()
    raw = re.sub(r"\r\n?", "\n", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def _safe_json_payload(text):
    raw = str(text or "").strip()
    match = re.search(r"\{.*\}\s*$", raw, flags=re.DOTALL)
    candidate = match.group(0) if match else raw
    return json.loads(candidate)


def _member_fact_payload(member):
    group = member.group
    payload = {
        "group": group.name,
        "group_type": group.get_group_type_display(),
        "agency": group.agency or group.label or "",
        "fandom_name": group.fandom_name or "",
        "stage_name": member.display_name,
        "full_name": member.resolved_full_name,
        "korean_name": member.korean_name or "",
        "positions": member.resolved_positions or "",
        "date_of_birth": member.date_of_birth.isoformat() if member.date_of_birth else "",
        "birthplace": member.birthplace or "",
        "nationality": member.nationality or "",
        "mbti": member.mbti or "",
        "blood_type": member.blood_type or "",
        "height_cm": str(member.height_cm or ""),
        "instagram_url": member.instagram_url or "",
        "debut_date": member.debut_date.isoformat() if member.debut_date else (group.debut_date.isoformat() if group.debut_date else ""),
        "existing_profile_bio": member.profile_bio or "",
        "existing_fan_facts": member.fan_facts or "",
        "profile_metadata": member.profile_metadata or {},
    }
    cleaned = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            if value:
                cleaned[key] = value
        elif str(value).strip():
            cleaned[key] = value
    return cleaned


def _build_prompt(member):
    facts = json.dumps(_member_fact_payload(member), ensure_ascii=True, indent=2)
    return (
        "Using only the verified facts below, generate JSON with exactly these keys: "
        '"profile_bio", "fan_facts", "seo_description_override", "birthday_spotlight". '
        '"profile_bio" must be 2 short paragraphs, polished and professional, with no invented facts. '
        '"fan_facts" must be 4 to 6 short bullet-style lines separated by \\n, each grounded in the facts provided. '
        '"seo_description_override" must be one sentence under 160 characters. '
        '"birthday_spotlight" must be 2 to 3 sentences explaining why this member\'s birthday page matters, again using only provided facts. '
        "Do not mention missing data. Do not invent family details, achievements, nicknames, training history, or preferences unless explicitly present in the facts. "
        "Return JSON only.\n\n"
        f"Verified facts:\n{facts}"
    )


class Command(BaseCommand):
    help = "Generate member dossier copy from verified K-Sync facts using DeepSeek."

    def add_arguments(self, parser):
        parser.add_argument("--group", help="Limit generation to one group slug.")
        parser.add_argument("--member", help="Limit generation to one member slug.")
        parser.add_argument("--limit", type=int, default=0, help="Maximum number of members to process.")
        parser.add_argument("--force", action="store_true", help="Regenerate even when copy already exists.")
        parser.add_argument("--include-birthday", action="store_true", help="Write a birthday spotlight into BirthdayFeature.")
        parser.add_argument("--dry-run", action="store_true", help="Generate output without saving.")

    def handle(self, *args, **options):
        group_slug = str(options.get("group") or "").strip()
        member_slug = str(options.get("member") or "").strip()
        limit = int(options.get("limit") or 0)
        force = bool(options.get("force"))
        include_birthday = bool(options.get("include_birthday"))
        dry_run = bool(options.get("dry_run"))

        queryset = KPopMember.objects.select_related("group").all().order_by("group__name", "order", "name")
        if group_slug:
            queryset = queryset.filter(group__slug=group_slug)
        if member_slug:
            queryset = queryset.filter(slug=member_slug)

        members = list(queryset)
        if not force:
            members = [
                member for member in members
                if not (
                    str(member.profile_bio or "").strip()
                    and str(member.fan_facts or "").strip()
                    and str(member.seo_description_override or "").strip()
                )
            ]
        if limit > 0:
            members = members[:limit]

        if not members:
            self.stdout.write(self.style.WARNING("No members matched the generation filters."))
            return

        updated = 0
        failed = 0
        skipped = 0

        for member in members:
            fact_payload = _member_fact_payload(member)
            if len(fact_payload) < 4:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"SKIP  {member.display_name}: not enough verified data"))
                continue

            try:
                response = _chat_reasoner(
                    _build_prompt(member),
                    system="You are a K-pop editor writing premium dossier copy from a fixed verified fact sheet. Never invent facts.",
                )
                parsed = _safe_json_payload(response)
            except Exception as exc:
                failed += 1
                self.stdout.write(self.style.WARNING(f"FAIL  {member.display_name}: {exc}"))
                continue

            profile_bio = _clean_text(parsed.get("profile_bio"))
            fan_facts = _clean_text(parsed.get("fan_facts"))
            seo_description = _clean_text(parsed.get("seo_description_override"))[:160]
            birthday_spotlight = _clean_text(parsed.get("birthday_spotlight"))

            if len(profile_bio) < 120 or len(fan_facts) < 40:
                failed += 1
                self.stdout.write(self.style.WARNING(f"FAIL  {member.display_name}: generated copy was too thin"))
                continue

            if not dry_run:
                update_fields = []
                if profile_bio:
                    member.profile_bio = profile_bio
                    update_fields.append("profile_bio")
                if fan_facts:
                    member.fan_facts = fan_facts
                    update_fields.append("fan_facts")
                if seo_description:
                    member.seo_description_override = seo_description
                    update_fields.append("seo_description_override")
                if update_fields:
                    member.save(update_fields=update_fields)

                if include_birthday and birthday_spotlight:
                    BirthdayFeature.objects.update_or_create(
                        member=member,
                        title="Birthday editorial spotlight",
                        defaults={
                            "description": birthday_spotlight,
                            "sort_order": -10,
                        },
                    )

            updated += 1
            self.stdout.write(self.style.SUCCESS(f"OK    {member.display_name}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Updated: {updated}"))
        self.stdout.write(self.style.WARNING(f"Skipped: {skipped}"))
        self.stdout.write(self.style.WARNING(f"Failed: {failed}"))
