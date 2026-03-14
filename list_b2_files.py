import os
import sys
import base64
import requests

# Manual .env loading
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value

B2_KEY_ID = os.getenv('B2_KEY_ID')
B2_APPLICATION_KEY = os.getenv('B2_APPLICATION_KEY')
B2_BUCKET_NAME = os.getenv('B2_BUCKET_NAME')

def get_b2_auth_token():
    id_and_key = f"{B2_KEY_ID}:{B2_APPLICATION_KEY}"
    basic_auth_string = 'Basic ' + base64.b64encode(id_and_key.encode('ascii')).decode('ascii')
    headers = {'Authorization': basic_auth_string}
    response = requests.get('https://api.backblazeb2.com/b2api/v2/b2_authorize_account', headers=headers)
    data = response.json()
    return data['authorizationToken'], data['apiUrl'], data['accountId']

def list_files():
    token, api_url, account_id = get_b2_auth_token()
    headers = {'Authorization': token}
    bucket_response = requests.get(f"{api_url}/b2api/v2/b2_list_buckets?accountId={account_id}", headers=headers)
    buckets = bucket_response.json().get('buckets', [])
    bucket = next((b for b in buckets if b['bucketName'] == B2_BUCKET_NAME), None)
    
    if not bucket:
        print("Bucket not found")
        return

    post_params = {'bucketId': bucket['bucketId']}
    response = requests.post(f"{api_url}/b2api/v2/b2_list_file_names", json=post_params, headers=headers)
    files = response.json().get('files', [])
    for f in files:
        print(f['fileName'])

if __name__ == "__main__":
    list_files()
