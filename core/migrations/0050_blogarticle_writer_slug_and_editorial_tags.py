from django.db import migrations, models


def _infer_writer_slug(title, category, source_name):
    haystack = f"{title} {category} {source_name}".lower()
    james_signals = (
        "what is", "why ", "guide", "explained", "global", "western",
        "dominating", "beginner", "introduction", "opinion", "editorial", "analysis",
    )
    sunny_signals = (
        "fandom", "fan theory", "theory", "lore", "hidden meaning",
        "discography", "ranking", "ranked", "best ", "universe", "symbol", "era",
    )
    if any(signal in haystack for signal in james_signals):
        return "james-elliott"
    if any(signal in haystack for signal in sunny_signals):
        return "sunny-park"
    return "mia-kang"


def _infer_editorial_tags(title, category, source_name, source_url):
    haystack = f"{title} {category} {source_name}".lower()
    tags = []
    if category in {"News", "Comeback", "Awards", "Industry"}:
        tags.append("Breaking News")
    if category == "Charts":
        tags.append("Chart Watch")
    if any(keyword in haystack for keyword in ("guide", "what is", "explained", "beginner")):
        tags.append("Beginner Guide")
    if any(keyword in haystack for keyword in ("analysis", "why ", "global", "western", "opinion")):
        tags.append("Opinion")
    if any(keyword in haystack for keyword in ("lore", "fan theory", "theory", "discography", "ranking", "ranked")):
        tags.append("Deep Dive")
    if any(keyword in haystack for keyword in ("fandom", "lore", "theory", "hidden meaning")):
        tags.append("Fan Theory")
    if not source_url or source_name.lower() in {"k-beats", "k-beats editorial", "k-sync"}:
        tags.append("Exclusive")
    if not tags:
        tags.append("Editor Pick")

    deduped = []
    seen = set()
    for tag in tags:
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(tag)
    return ", ".join(deduped[:3])


def backfill_blogarticle_editorial_fields(apps, schema_editor):
    BlogArticle = apps.get_model("core", "BlogArticle")
    for article in BlogArticle.objects.all().iterator():
        article.writer_slug = _infer_writer_slug(
            article.title or "",
            article.category or "",
            article.source_name or "",
        )
        article.editorial_tags = _infer_editorial_tags(
            article.title or "",
            article.category or "",
            article.source_name or "",
            article.source_url or "",
        )
        article.save(update_fields=["writer_slug", "editorial_tags"])


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0049_kpopmember_profile_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="blogarticle",
            name="editorial_tags",
            field=models.CharField(
                blank=True,
                help_text="Comma-separated editorial tags, for example: Breaking News, Exclusive",
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name="blogarticle",
            name="writer_slug",
            field=models.CharField(
                choices=[
                    ("mia-kang", "Mia Kang"),
                    ("sunny-park", "Sunny Park"),
                    ("james-elliott", "James Elliott"),
                ],
                default="mia-kang",
                max_length=40,
            ),
        ),
        migrations.RunPython(backfill_blogarticle_editorial_fields, migrations.RunPython.noop),
    ]
