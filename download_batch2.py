import os
import urllib.request
import certifi
import ssl
import time

ssl_context = ssl.create_default_context(cafile=certifi.where())

urls = [
    {
        "id": "bb341657a02c469799766bf410449cbb",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidWME-i_YxcCzF7lSzCS0DWQLZaBEF7NB_qt6UykFcXHIvX5kZRo1G1WAD-jUnw4uSEki3L2BQoHYLCt-o0R4e5D1GE1o_uakd0XgEEpUauZlTWOR1j9ZW3QeKrx9nov0TlDxoJQewRldp1IvmSq2Cw0VYzLREAvJrYHGEFKJ3Mj9LTuf5rC1I6DD-jgkf4nQGkBpQfEH2jnql75pbZVs3KJSDB9FtF60LAalncafNs2A8wMrn6vrZq5LjuU",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sXzJjZDcwNzI1MmY4YzQzMzFiMjE5ZjE1NGJiZGQzN2VjEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "c8eb3dd036f34322936b07a84608b2f8",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidULYUK1cD_8by_KstATHsoFkZjw0LhN51lyGyqKv_l_hWeplh-4Tj98hx0jkK8bZ1buo9Pg_pUTmj0lEzV5cj1Tps_ImwW2mgrZQ5Xy4JFWNeERUPISJWzVOlI98iiHPREarojBl7ubCV7OmK1rgyYXXWMgFSVFhFBfk2hzmjy34yK8xDxTo1Ux-qPUSwdiqCZYKvDo0u1L3Oldvm1RY7Gv4DKPwcQ5TeaNGkbUTlPWid49ocHykhm9CG5l",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2E0MWE2OTQ1NTU0YjRhMTY5Y2JjMWZjNGY2Njc1Yzg4EgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
    },
    {
        "id": "cb0d103957fb42edad4f0c78259fbe2f",
        "screenshot": "https://lh3.googleusercontent.com/aida/AOfcidXVN-CGYqO5jBTQ6J9f6X2N041nodheiYAHQmhiTgld6fUDU1J3nbm_ByUfcOUNdUXFtA1DU5WKucv8eU1dKPGoNrrin-xn4DVxYF-akdABAhk2_kLAcqwATpO4xfuLPWuW_Wo3TnZQPgjF2sstIOoO6UejQi79lKNO8K05NiRFSN2FWo8yCJbphIsk3SUp3rf0ehkH2I-kd19V2EklrzCikmi-ir2vP9XB4I1c5O9VuZlLdXS7OsbjKzJG",
        "html": "https://contribution.usercontent.google.com/download?c=CgthaWRhX2NvZGVmeBJ8Eh1hcHBfY29tcGFuaW9uX2dlbmVyYXRlZF9maWxlcxpbCiVodG1sX2ZiNTkyNTM0OGM5YzQwNWQ5OGVhZTUxOWU4OTYxNmQxEgsSBxCXhpyfmhQYAZIBJAoKcHJvamVjdF9pZBIWQhQxNzQ2NjA3OTc3Mjg5ODUwMjMzMA&filename=&opi=89354086"
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

print("Batch 2 Done")
