import urllib.request
import json

def get_album_art(artist, track):
    query = f"{artist} {track}".replace(" ", "+")
    url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if data['resultCount'] > 0:
                print(data['results'][0]['artworkUrl100'].replace('100x100bb', '600x600bb'))
            else:
                print('No artwork found')
    except Exception as e:
        print(f'Error: {e}')

get_album_art("IVE", "BANG BANG")
get_album_art("BLACKPINK", "GO")
