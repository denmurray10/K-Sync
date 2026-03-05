import os
import json
import shutil
import urllib.parse
from datetime import datetime

history_dir = os.path.join(os.environ.get('APPDATA', r'C:\Users\denni\AppData\Roaming'), 'Code', 'User', 'History')
templates_dir = r'c:\Users\denni\OneDrive\Documents\Vs projects\K-Sync\core\templates\core'

recovered = 0
for file in os.listdir(templates_dir):
    if not file.endswith('.html'):
        continue
    path = os.path.join(templates_dir, file)
    if os.path.getsize(path) != 0:
        continue
    
    restored = False
    for hdir in os.listdir(history_dir):
        hpath = os.path.join(history_dir, hdir)
        entries_file = os.path.join(hpath, 'entries.json')
        if not os.path.exists(entries_file):
            continue
        try:
            with open(entries_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                resource = data.get('resource', '')
                decoded = urllib.parse.unquote(resource).replace('\\', '/')
                if 'K-Sync' in decoded and 'templates/core' in decoded and decoded.endswith(file):
                    entries = data.get('entries', [])
                    entries.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
                    for entry in entries:
                        entry_path = os.path.join(hpath, entry.get('id', ''))
                        if os.path.exists(entry_path) and os.path.getsize(entry_path) > 0:
                            shutil.copy2(entry_path, path)
                            print(f'Recovered {file}')
                            recovered += 1
                            restored = True
                            break
        except Exception as e:
            pass
        if restored:
            break
            
print('Total recovered:', recovered)
