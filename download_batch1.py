import os
import urllib.request
import certifi
import ssl
import time

ssl_context = ssl.create_default_context(cafile=certifi.where())

urls = [
    {
        "id": "0b013e3a4f56427e8fbc6cb10858c5c3",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidUBq-GRRH9k15jPTr9VGorVSOSo34ajcHZFqHy59vjGXkJoUZB0DWfamf8wIZuh77MDrkwJDEGEgMSbqVriyNFIWDX-idOomRih7jcFfCqMwMQCRH4ljkuCLRovdffY4fUCq2F0VAzo_-IhFtGL--CD04JLStJvUhJjnPiW0EDYRnGLcoi8abzzQIyte2gTXthk_9_ZV9YZPEErKzFb9A7ROlsDh4pa39AeggQNbcm2TcvY5Mx3wgQ0dSLH",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzVmOGJmMWMxNDY2ZTRkMDhhN2ExZDRhMWVhMjZlOGJjEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "34a25375164045209c9f58d893eae0ae",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidWiHWozdCRzH8ZOwCGIbNC6sANZ3gW-i2PsOnT7HvOyM0ca2F9io6qdOii2sE6Rbpt3dnJ74ryTTaX_7AZiRtiueqZlUB5c_cB7oT5menXI6wD7jVinUkeqAloEoPmRfVsaujXcenUsse8nBOwoTeOTDjOiNI3S2lmHWZlmeKEXMKQ3xijZ1LwTpI9m2gY5gib8yasFeDhHrj_h4vGAWY1tL68Fcij3DEbFcMy7xyR3OhpWid4KjXDUzezO",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2I4M2I4YTc3ZDFlYTQxZjJiYzAzYmRmYjI2NmM2ZGI2EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "74c756010762411b9552864bda9da161",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidW-SpOLUePnENGuyXpLqEZ2b_k0VtGGz8j8lMlcYUAcDIL_yNzAdTctSbneNdIbKCNS1TH3CP3ZjKEucoPyR3zYEcR0G9o1pipXUm4vIXQZTQcjUb4vrCZUZo2gLTIBrrVip5yaK3uenXJgELRKWVL7vv0FNB3ke0mIS5I8PUCPmRCkohjx2D9N95oPhuGU55kl8eL1PJkJf5uHtiotZfHCFGo8rsu_O6QUYobuRD7lSvJcMVynxmW5-cw",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzQ0NzhmNjA1NzhlYTQwOTQ5NDFkZTFjZDZjYjJhYWJmEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "7a36d6443dcb4ece96b98aa75ab533ad",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidXBOgv3LhzQ0rXph9KU_EDGFHYXpLEs40DdeGnpDQFW4NXbeurn8xgaM3r7sXEDlpB4VSIAqZPjvZHKHbbDXybG8FXOxJ4qMqudlLQyXuR5fAB0YdQTMho5dVqdtCzMZTeJG9Hyj607wqQgyf4s7PAZmbmw2KhTY5tatkCbOvIw2XyocUqCMNQFDGVOzarJxXegx7vu3IheXSnk6lfO0ACcXBRJvaEnkEzmNxcX3FVQd2Pa4QdgiN8Kl1LE",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2E1YjMwNzY3Y2M5NDQ5Y2ZhMjFiMmI5N2JkYWU4ZjI0EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "a1a4a5cd3dcf4adc8d5deb51ec4c3d23",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidVIBYJo6v1NDKb6KEQFsHpFb33QRYHoGejP83jOGdDI1SSy7sgwyTvDNeFTqEQeWJZL-CZkSkaV0-O6Aqeg0Wuuj9r6jxvYEtIQ-iXC7E0FpTnmh9aaOL0AVoY5oH-jW6oGbSn1fkQROY3lH3HgbnXKRjMVuD4naHJr2sq8SHMmjPPuvPp-QzNJFzmqA1Vp584KcEB1BRob6AnRuXYayTYGlpRrGl7Xj73UHMRNub591TboUnSsnzZLd3Y",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzdjZmYxZGQ3NTRjZDQxMGRhMmNiM2U4OGYzMzZmZGY0EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    }
]

download_dir = "stitch_downloads"
os.makedirs(download_dir, exist_ok=True)

for item in urls:
    screen_id = item["id"]
    print(f"Downloading {screen_id}...")
    
    # Download HTML
    html_path = os.path.join(download_dir, f"{screen_id}.html")
    if not os.path.exists(html_path):
        req = urllib.request.Request(item["html"], headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, context=ssl_context) as response, open(html_path, 'wb') as out_file:
                out_file.write(response.read())
        except Exception as e:
            print(f"Failed HTML {screen_id}: {e}")
        time.sleep(2)

    # Download Screenshot
    screenshot_path = os.path.join(download_dir, f"{screen_id}.png")
    if not os.path.exists(screenshot_path):
        req = urllib.request.Request(item["screenshot"], headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, context=ssl_context) as response, open(screenshot_path, 'wb') as out_file:
                out_file.write(response.read())
        except Exception as e:
            print(f"Failed Screenshot {screen_id}: {e}")
        time.sleep(2)

print("Batch 1 Done")
