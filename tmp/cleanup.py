import os
import re

templates_dir = r'c:\Users\denni\OneDrive\Documents\Vs projects\K-Sync\core\templates\core'
static_dir = r'c:\Users\denni\OneDrive\Documents\Vs projects\K-Sync\core\static\core'

# Find 0-byte html files
zero_byte_files = []
for f in os.listdir(templates_dir):
    p = os.path.join(templates_dir, f)
    if os.path.getsize(p) == 0:
        zero_byte_files.append(p)

print(f'Zero byte files: {zero_byte_files}')

used_static_files = set()
for root, _, files in os.walk(templates_dir):
    for file in files:
        if file.endswith('.html'):
            try:
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    content = f.read()
                    matches = re.findall(r"\'core\/(.*?)\'", content)
                    for m in matches:
                        used_static_files.add(os.path.normpath(os.path.join(static_dir, m)))
            except Exception as e:
                print(e)

print(f"Used static files: {used_static_files}")

all_static_files = []
for root, _, files in os.walk(static_dir):
    for f in files:
        all_static_files.append(os.path.normpath(os.path.join(root, f)))

unused_media_files = []
for f in all_static_files:
    if f not in used_static_files and not f.endswith('.css') and not f.endswith('.js'):
        unused_media_files.append(f)

print(f"Total All Static Files: {len(all_static_files)}")
print(f"Total Unused Media Files ({len(unused_media_files)}):")
for f in unused_media_files:
    print(f)
    if os.path.getsize(f) > 0:
        os.remove(f)

for f in zero_byte_files:
    os.remove(f)
print('Unused pages and images cleaned.')
