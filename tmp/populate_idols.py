import os
import sys
import django

# Set up Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ksync_project.settings')
django.setup()

from core.models import KPopGroup
from django.utils.text import slugify

groups_data = [
    (1, "BTS", "HYBE Labels", "BOY", "Global dominance with multiple #1 Billboard albums."),
    (2, "BLACKPINK", "YG Entertainment", "GIRL", "First K-pop girl group to headline Coachella."),
    (3, "SEVENTEEN", "PLEDIS Entertainment", "BOY", "Recognized as 2025 Billboard K-Pop Artist #1."),
    (4, "Stray Kids", "JYP Entertainment", "BOY", "Consistent Billboard 200 chart-toppers."),
    (5, "EXO", "SM Entertainment", "BOY", "Pioneered K-pop’s global expansion in the 2010s."),
    (6, "TWICE", "JYP Entertainment", "GIRL", "One of the best-selling K-pop girl groups ever."),
    (7, "SHINee", "SM Entertainment", "BOY", "Legendary discography and performance legacy."),
    (8, "NCT 127", "SM Entertainment", "BOY", "Known for an experimental sound and global fanbase."),
    (9, "NCT Dream", "SM Entertainment", "BOY", "Powerful streaming and strong youth appeal."),
    (10, "Super Junior", "SM Entertainment", "BOY", "One of K-pop’s original global superstar groups."),
    (11, "ATEEZ", "KQ Entertainment", "BOY", "4th-gen performance powerhouse with international touring strength."),
    (12, "ENHYPEN", "BELIFT LAB", "BOY", "Rapid global rise with strong album and tour momentum."),
    (13, "TXT (Tomorrow X Together)", "BIGHIT MUSIC", "BOY", "Signature storytelling concept and worldwide fandom growth."),
    (14, "aespa", "SM Entertainment", "GIRL", "Genre-blending concept leaders of the current era."),
    (15, "(G)I-DLE", "Cube Entertainment", "GIRL", "Self-driven identity and chart-winning releases."),
    (16, "IVE", "Starship Entertainment", "GIRL", "Hitmaking consistency and premium concept execution."),
    (17, "LE SSERAFIM", "SOURCE MUSIC", "GIRL", "Performance-forward identity with global pop crossover."),
    (18, "NewJeans", "ADOR", "GIRL", "Cultural trendsetters with standout streaming impact."),
    (19, "ITZY", "JYP Entertainment", "GIRL", "High-energy choreography and strong fan support."),
    (20, "TREASURE", "YG Entertainment", "BOY", "Strong global fanbase and stage-focused brand."),
    (21, "ZEROBASEONE", "WAKEONE", "BOY", "Fast-rising project group with major rookie momentum."),
    (22, "RIIZE", "SM Entertainment", "BOY", "New-generation growth with strong digital response."),
    (23, "TWS", "PLEDIS Entertainment", "BOY", "Emerging act with breakout public attention."),
    (24, "GOT7", "Warner Music Korea", "BOY", "Beloved 3rd-gen group with proven global reach."),
    (25, "MONSTA X", "Starship Entertainment", "BOY", "Internationally recognized for performance and touring."),
    (26, "Red Velvet", "SM Entertainment", "GIRL", "Versatile concept queens with a respected catalog."),
    (27, "NCT U", "SM Entertainment", "BOY", "Flexible unit format showcasing NCT’s core range."),
    (28, "BIGBANG", "YG Entertainment", "BOY", "Iconic trendsetting legacy in modern K-pop history."),
    (29, "Girls' Generation (SNSD)", "SM Entertainment", "GIRL", "Foundational girl-group icons of the Hallyu era."),
    (30, "MAMAMOO", "RBW", "GIRL", "Renowned vocal group with enduring fan loyalty."),
    (31, "BABYMONSTER", "YG Entertainment", "GIRL", "5th-gen YG girl group with major spotlight."),
    (32, "ILLIT", "BELIFT LAB", "GIRL", "Breakout 5th-gen act with rapid audience growth."),
    (33, "ASTRO", "Fantagio", "BOY", "Beloved 3rd-gen team with dedicated fandom."),
    (34, "IZ*ONE", "Off The Record / Swing Entertainment", "GIRL", "Iconic project group with lasting influence."),
    (35, "EXID", "Banana Culture", "GIRL", "2nd-gen legends known for viral-era impact."),
    (36, "Wanna One", "Swing Entertainment", "BOY", "Project group that produced many top stars."),
    (37, "CIX", "C9 Entertainment", "BOY", "Vocal-focused group with strong concept identity."),
    (38, "DAY6", "JYP Entertainment", "BOY", "K-pop band respected for live-musicianship."),
    (39, "HIGHLIGHT", "Around US Entertainment", "BOY", "Veteran group with stable long-term support."),
    (40, "VICTON", "IST Entertainment", "BOY", "Fan-favorite team with a loyal core audience."),
    (41, "KISS OF LIFE", "S2 Entertainment", "GIRL", "Retro-inspired identity with strong buzz."),
    (42, "fromis_9", "PLEDIS Entertainment", "GIRL", "Consistent releases and steady fan growth."),
    (43, "VERIVERY", "Jellyfish Entertainment", "BOY", "4th-gen boy group with performance strengths."),
    (44, "PENTAGON", "Cube Entertainment", "BOY", "Creative, self-producing team with dedicated fandom."),
    (45, "THE BOYZ", "IST Entertainment", "BOY", "Performance-focused act with global support."),
    (46, "EVNNE", "Jellyfish Entertainment", "BOY", "Rising 5th-gen group gaining momentum."),
    (47, "FIFTY FIFTY", "ATTRAKT", "GIRL", "Global viral breakout via ‘Cupid’."),
    (48, "STAYC", "High Up Entertainment", "GIRL", "4th-gen girl group with consistent chart presence."),
    (49, "Kep1er", "WAKEONE / Swing Entertainment", "GIRL", "Project girl group with international fanbase."),
    (50, "XODIAC", "One Cool Jacso Entertainment", "BOY", "Emerging 5th-gen act with rising attention."),
]


def _slug_for(name: str) -> str:
    overrides = {
        "TXT (Tomorrow X Together)": "txt",
        "(G)I-DLE": "g-i-dle",
        "Girls' Generation (SNSD)": "girls-generation-snsd",
        "IZ*ONE": "izone",
        "fromis_9": "fromis-9",
    }
    return overrides.get(name, slugify(name))


def _story_for(name: str, label: str, gtype: str, trait: str) -> str:
    group_label = 'boy group' if gtype == 'BOY' else ('girl group' if gtype == 'GIRL' else 'solo artist')
    return (
        f"{name} is a leading K-pop {group_label} under {label}. "
        f"{trait} "
        f"On K-Beats, fans can follow {name}'s story through releases, milestones, and community highlights."
    )


def populate():
    target_slugs = set()

    for rank, name, label, gtype, trait in groups_data:
        slug = _slug_for(name)
        target_slugs.add(slug)
        group, created = KPopGroup.objects.update_or_create(
            slug=slug,
            defaults={
                'name': name,
                'label': label,
                'group_type': gtype,
                'rank': rank,
                'logo_path': f'core/images/group_logos/{slug.replace("-", "_")}.png',
                'description': _story_for(name, label, gtype, trait),
            }
        )

        if created:
            print(f"Created group: {name}")
        else:
            print(f"Updated group: {name}")

    demoted = KPopGroup.objects.exclude(slug__in=target_slugs).exclude(rank__isnull=True).update(rank=None)
    if demoted:
        print(f"Demoted {demoted} non-top-50 ranked entries (set rank=None)")

if __name__ == "__main__":
    populate()
