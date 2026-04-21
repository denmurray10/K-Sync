from dataclasses import dataclass


@dataclass(frozen=True)
class WriterProfile:
    slug: str
    name: str
    role: str
    bio: str
    tone: str
    avatar_path: str


WRITER_PROFILES = {
    "mia-kang": WriterProfile(
        slug="mia-kang",
        name="Mia Kang",
        role="K-pop News Reporter & Trend Analyst",
        bio=(
            "Mia is a sharp, fast-moving journalist obsessed with everything K-pop. "
            "She breaks comeback news, tracks chart swings, and keeps every update crisp."
        ),
        tone="Concise, informative, professional, and punchy.",
        avatar_path="core/img/avatars/mia-kang.jpeg",
    ),
    "sunny-park": WriterProfile(
        slug="sunny-park",
        name="Sunny Elliot",
        role="Fan Culture Writer & Deep Dive Columnist",
        bio=(
            "Sunny writes from the fandom front row, mixing humour, warmth, and lore-heavy context "
            "for readers who love the deeper story behind every era."
        ),
        tone="Conversational, enthusiastic, and fan-first.",
        avatar_path="core/img/avatars/sunny-elliot.jpeg",
    ),
    "james-elliott": WriterProfile(
        slug="james-elliott",
        name="James Park",
        role="Music Critic & Global K-pop Commentator",
        bio=(
            "James bridges Western pop readers into K-pop with thoughtful analysis, wider cultural framing, "
            "and a critic's eye for momentum and meaning."
        ),
        tone="Thoughtful, analytical, and slightly opinionated.",
        avatar_path="core/img/avatars/james-park.jpeg",
    ),
}

WRITER_CHOICES = tuple((slug, profile.name) for slug, profile in WRITER_PROFILES.items())

PRIMARY_TAG_ORDER = (
    "Breaking News",
    "Exclusive",
    "Chart Watch",
    "Fan Theory",
    "Deep Dive",
    "Opinion",
    "Beginner Guide",
    "Editor Pick",
)


def get_writer_profile(writer_slug: str | None) -> WriterProfile:
    return WRITER_PROFILES.get(writer_slug or "", WRITER_PROFILES["mia-kang"])


def parse_editorial_tags(value: str | None) -> list[str]:
    if not value:
        return []

    seen: set[str] = set()
    tags: list[str] = []
    for raw_tag in str(value).split(","):
        tag = raw_tag.strip()
        if not tag:
            continue
        normalized = tag.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        tags.append(tag)
    return tags


def serialize_editorial_tags(tags: list[str] | tuple[str, ...] | None) -> str:
    return ", ".join(parse_editorial_tags(", ".join(tags or [])))


def infer_writer_slug(*, title: str = "", category: str = "", source_name: str = "") -> str:
    haystack = f"{title} {category} {source_name}".lower()

    james_signals = (
        "what is",
        "why ",
        "guide",
        "explained",
        "global",
        "western",
        "dominating",
        "beginner",
        "introduction",
        "opinion",
        "editorial",
        "analysis",
    )
    sunny_signals = (
        "fandom",
        "fan theory",
        "theory",
        "lore",
        "hidden meaning",
        "discography",
        "ranking",
        "ranked",
        "best ",
        "universe",
        "symbol",
        "era",
    )

    if any(signal in haystack for signal in james_signals):
        return "james-elliott"
    if any(signal in haystack for signal in sunny_signals):
        return "sunny-park"
    return "mia-kang"


def infer_editorial_tags(
    *,
    title: str = "",
    category: str = "",
    source_name: str = "",
    source_url: str = "",
) -> list[str]:
    haystack = f"{title} {category} {source_name}".lower()
    tags: list[str] = []

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

    ordered_tags: list[str] = []
    for preferred in PRIMARY_TAG_ORDER:
        if preferred in tags and preferred not in ordered_tags:
            ordered_tags.append(preferred)
    for tag in tags:
        if tag not in ordered_tags:
            ordered_tags.append(tag)
    return ordered_tags[:3]
