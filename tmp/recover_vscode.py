import os
import json
import shutil
import urllib.parse

history_dir = os.path.join(os.environ.get('APPDATA', 'C:\\Users\\denni\\AppData\\Roaming'), 'Code', 'User', 'History')
templates_dir = r'c:\Users\denni\OneDrive\Documents\Vs projects\K-Sync\core\templates\core'

print('History dir:', history_dir)

recovered = 0
for file in os.listdir(templates_dir):
    if file.endswith('.html'):
        path = os.path.join(templates_dir, file)
        if os.path.getsize(path) == 0:
            restored = False
            for hdir in os.listdir(history_dir):
                hpath = os.path.join(history_dir, hdir)
                entries_file = os.path.join(hpath, 'entries.json')
                if os.path.exists(entries_file):
                    try:
                        with open(entries_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            resource = data.get('resource', '')
                            decoded_resource = urllib.parse.unquote(resource).replace('\\', '/')
                            if file in decoded_resource and 'core/templates/core' in decoded_resource:
                                entries = data.get('entries', [])
                                entries.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
                                for entry in entries:
                                    entry_id = entry.get('id')
                                    entry_path = os.path.join(hpath, entry_id)
                                    if os.path.exists(entry_path) and os.path.getsize(entry_path) > 0:
                                        shutil.copy2(entry_path, path)
                                        print(f'Recovered {file}')
                                        recovered += 1
                                        restored = True
                                        break
                    except Exception:
                        pass
                if restored:
                    break
print(f'Recovered {recovered} files')
