"""
fetch_kpopping_images.py

Downloads group and member profile images from kpopping.com CDN.
Images are saved locally to core/static/core/images/ and the DB
image_url fields are updated to point to the local static paths.

Usage:
    python fetch_kpopping_images.py            # skip already-downloaded
    python fetch_kpopping_images.py --force    # re-download everything
"""

import os
import sys
import time
import django
import requests
from pathlib import Path

# ── Django setup ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ksync_project.settings")
django.setup()

from core.models import KPopGroup, KPopMember  # noqa: E402 (must come after setup)

# ── Paths ─────────────────────────────────────────────────────────────────────
IMAGES_DIR = BASE_DIR / "core" / "static" / "core" / "images"
GROUPS_DIR = IMAGES_DIR / "groups"
MEMBERS_DIR = IMAGES_DIR / "members"
GROUPS_DIR.mkdir(parents=True, exist_ok=True)
MEMBERS_DIR.mkdir(parents=True, exist_ok=True)

FORCE = "--force" in sys.argv

# ── Known kpopping.com group name overrides ──────────────────────────────────
# Maps our DB group name → exact folder name on cdn.kpopping.com/groups/
GROUP_NAME_MAP = {
    "(G)I-DLE":     "i-dle",
    "BLACKPINK":    "BLACKPINK",
    "BTS":          "BTS",
    "ENHYPEN":      "ENHYPEN",
    "EXO":          "EXO",
    "GOT7":         "GOT7",
    "ITZY":         "ITZY",
    "IU":           "IU",
    "IVE":          "IVE",
    "Jungkook":     "Jungkook",
    "LE SSERAFIM":  "LE-SSERAFIM",
    "Lisa":         "Lisa",
    "NCT 127":      "NCT-127",
    "NewJeans":     "NewJeans",
    "SEVENTEEN":    "SEVENTEEN",
    "Stray Kids":   "Stray-Kids",
    "TWICE":        "TWICE",
    "TXT":          "TXT",
    "Taeyang":      "Taeyang",
    "aespa":        "aespa",
}

# Solo artists stored as KPopGroup in our DB — CDN images live under /idols/ not /groups/
GROUP_CDN_FOLDER = {
    "IU":       "idols",
    "Jungkook": "idols",
    "Lisa":     "idols",
    "Taeyang":  "idols",
}

# Maps our stage name → exact folder name on cdn.kpopping.com/idols/
# Numbers (e.g. Karina2) resolve disambiguation when multiple idols share a name
MEMBER_NAME_MAP = {
    "Rosé":         "Rose",
    "j-hope":       "j-hope",
    "SUGA":         "Suga",
    "RM":           "RM",
    # BTS Jimin disambiguated from Wanna One Jimin
    "Jimin":        "Jimin2",
    "Bang Chan":    "Bang-Chan",
    "Lee Know":     "Lee-Know",
    # Stray Kids Hyunjin / Seungmin disambiguated
    "Hyunjin":      "Hyunjin2",
    "Seungmin":     "Seungmin2",
    "I.N":          "I-N",
    "D.O.":         "D-O",
    "S.Coups":      "S-Coups",
    "The8":         "The8",
    "Huening Kai":  "Huening-Kai",
    "Ni-ki":        "Ni-ki",
    "BamBam":       "BamBam",
    "JB":           "Jay-B",
    "Yunjin":       "Huh-Yunjin",
    "Leeseo":       "Leeseo",
    "Haechan":      "Haechan",
    # aespa Karina disambiguated from SKYGIRLS Karina
    "Karina":       "Karina2",
    # aespa — CDN uses lowercase folder names
    "Giselle":      "giselle",
    "Winter":       "winter",
    "Ningning":     "ningning",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://kpopping.com/",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def to_kpopping_slug(name):
    """Default conversion: replace spaces with hyphens."""
    return name.replace(" ", "-")


def download_image(url, dest_path):
    """Download url → dest_path.  Returns True on success."""
    try:
        resp = SESSION.get(url, timeout=15)
        ct = resp.headers.get("Content-Type", "")
        if resp.status_code == 200 and "image" in ct:
            dest_path.write_bytes(resp.content)
            return True
        return False
    except requests.RequestException:
        return False


def fetch_best(cdn_name, cdn_folder, dest_dir, slug, static_folder=None):
    """Try .webp then .jpg for a CDN resource, return (local_path, static_url).

    cdn_name    : folder name used on the CDN (e.g. 'BTS', 'Karina2')
    cdn_folder  : CDN subfolder — 'groups' or 'idols'
    dest_dir    : local Path to save into
    slug        : safe filename stem (no extension)
    static_folder: folder name used in the static URL (defaults to cdn_folder)
    Returns (local_path, static_url) on success, (None, None) on failure.
    """
    if static_folder is None:
        static_folder = cdn_folder
    base = f"https://cdn.kpopping.com/{cdn_folder}/{cdn_name}/profile"
    for ext in (".webp", ".jpg"):
        url = base + ext
        dest = dest_dir / f"{slug}{ext}"
        if download_image(url, dest):
            static = f"/static/core/images/{static_folder}/{slug}{ext}"
            return dest, static
    return None, None


# Group images
print("=" * 60)
print("GROUP PROFILE IMAGES")
print("=" * 60)

group_ok = 0
group_fail = []

for group in KPopGroup.objects.all().order_by("name"):
    kpopping_name = GROUP_NAME_MAP.get(
        group.name, to_kpopping_slug(group.name)
    )

    # Skip if any variant already downloaded and not forcing
    existing = list(GROUPS_DIR.glob(f"{group.slug}.*"))
    if existing and not FORCE:
        saved_url = (
            f"/static/core/images/groups/"
            f"{existing[0].name}"
        )
        print(f"  [SKIP] {group.name}")
        if group.image_url != saved_url:
            group.image_url = saved_url
            group.save()
        continue

    cdn_folder = GROUP_CDN_FOLDER.get(group.name, "groups")
    local_path, static_url = fetch_best(
        kpopping_name, cdn_folder, GROUPS_DIR, group.slug,
        static_folder="groups"
    )

    if local_path:
        group.image_url = static_url
        group.save()
        print(f"  [OK]   {group.name}  →  {local_path.name}")
        group_ok += 1
    else:
        print(f"  [FAIL] {group.name}  (cdn: {kpopping_name})")
        group_fail.append(group.name)

    time.sleep(0.4)

print()
print(f"Groups: {group_ok} ok, {len(group_fail)} failed")
if group_fail:
    print(f"  Failed: {group_fail}")

# Member images
print()
print("=" * 60)
print("MEMBER PROFILE IMAGES")
print("=" * 60)

member_ok = 0
member_fail = []

members = (
    KPopMember.objects.select_related("group")
    .all()
    .order_by("group__name", "order", "name")
)

for member in members:
    stage = member.stage_name or member.name

    # Use override map first, then default slug conversion
    kpopping_member = MEMBER_NAME_MAP.get(
        stage, to_kpopping_slug(stage)
    )

    # Safe filesystem stem (strip dots/slashes/spaces)
    safe_stem = (
        stage.replace("/", "_")
             .replace(".", "")
             .replace(" ", "-")
    )

    existing = list(MEMBERS_DIR.glob(f"{safe_stem}.*"))
    if existing and not FORCE:
        saved_url = (
            f"/static/core/images/members/"
            f"{existing[0].name}"
        )
        print(f"  [SKIP] [{member.group.name}] {stage}")
        if member.image_url != saved_url:
            member.image_url = saved_url
            member.save()
        continue

    local_path, static_url = fetch_best(
        kpopping_member, "idols", MEMBERS_DIR, safe_stem,
        static_folder="members"
    )

    if local_path:
        member.image_url = static_url
        member.save()
        print(
            f"  [OK]   [{member.group.name}] {stage}"
            f"  →  {kpopping_member}"
        )
        member_ok += 1
    else:
        print(
            f"  [FAIL] [{member.group.name}] {stage}"
            f"  (cdn: {kpopping_member})"
        )
        member_fail.append(f"{member.group.name}/{stage}")

    time.sleep(0.4)

print()
print(f"Members: {member_ok} ok, {len(member_fail)} failed")
if member_fail:
    print("  Failed:", member_fail)

print()
print("Done!")
