
import urllib.request
import re
import json

def test_scrape():
    url = "https://www.ichart.kr/rank"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            
            # Look for JSON-like blocks in scripts
            # Next.js 13+ often uses self-bootstraping data in multiple script tags
            # or a single large one.
            
            # Let's try to find all JSON-looking strings in the HTML
            # or specifically the ones that look like ranking data.
            
            # Search for track names specifically to see what context they are in
            # We know "Baddie" or "Love Dive" etc are likely there.
            
            # Find all script tags
            scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
            print(f"Scripts found: {len(scripts)}")
            
            for i, s in enumerate(scripts):
                if '"rank":' in s and '"title":' in s:
                    print(f"Found potential ranking JSON in script {i}")
                    # Try to parse it or print a snippet
                    start = s.find('{')
                    end = s.rfind('}') + 1
                    try:
                        # Sometimes it's just a fragment
                        pass
                    except:
                        pass
            
            # Let's also look for the HTML structure again
            # <h3 class="...">Title</h3>
            # <p class="...">Artist</p>
            
            pattern = re.compile(r'<h3[^>]*>(.*?)</h3>.*?<p[^>]*>(.*?)</p>', re.DOTALL)
            matches = pattern.findall(html)
            print(f"Matches found: {len(matches)}")
            for m in matches[:10]:
                print(f"Track: {m[0].strip()} | Artist: {m[1].strip()}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_scrape()
