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
    (1, "BTS", "HYBE Labels", "BOY"),
    (2, "Stray Kids", "JYP Entertainment", "BOY"),
    (3, "BLACKPINK", "YG Entertainment", "GIRL"),
    (4, "TWICE", "JYP Entertainment", "GIRL"),
    (5, "ITZY", "JYP Entertainment", "GIRL"),
    (6, "TXT (Tomorrow X Together)", "HYBE Labels", "BOY"),
    (7, "(G)I-DLE", "Cube Entertainment", "GIRL"),
    (8, "ENHYPEN", "Belift Lab / HYBE Labels", "BOY"),
    (9, "aespa", "SM Entertainment", "GIRL"),
    (10, "LE SSERAFIM", "Source Music / HYBE Labels", "GIRL"),
    (11, "Super Junior", "SM Entertainment", "BOY"),
    (12, "Red Velvet", "SM Entertainment", "GIRL"),
    (13, "IVE", "Starship Entertainment", "GIRL"),
    (14, "SEVENTEEN", "Pledis / HYBE Labels", "BOY"),
    (15, "NewJeans", "ADOR / HYBE Labels", "GIRL"),
    (16, "GOT7", "JYP Entertainment", "BOY"),
    (17, "ILLIT", "Belift Lab / HYBE Labels", "GIRL"),
    (18, "BIGBANG", "YG Entertainment", "BOY"),
    (19, "BabyMonster", "YG Entertainment", "GIRL"),
    (20, "Mamamoo", "RBW Entertainment", "GIRL"),
    (21, "NCT", "SM Entertainment", "BOY"),
    (22, "Katseye", "HYBE / Geffen Records", "GIRL"),
    (23, "EXO", "SM Entertainment", "BOY"),
    (24, "ATEEZ", "KQ Entertainment", "BOY"),
    (25, "NMIXX", "JYP Entertainment", "GIRL"),
]

def populate():
    for rank, name, label, gtype in groups_data:
        slug = slugify(name)
        group, created = KPopGroup.objects.update_or_create(
            slug=slug,
            defaults={
                'name': name,
                'label': label,
                'group_type': gtype,
                'rank': rank,
                'logo_path': f'core/images/group_logos/{slug.replace("-", "_")}.png'
            }
        )
        if created:
            print(f"Created group: {name}")
        else:
            print(f"Updated group: {name}")

if __name__ == "__main__":
    populate()
