import requests
from urllib.parse import parse_qs, urlparse
import re
import time
from config import load_config, load_token, save_token

CONFIG = load_config()
API_BASE = CONFIG['rtv']['base_url']
POLL_INTERVAL = CONFIG['rtv']['poll_interval']

def get_valid_token():
    """Get a valid API token, prompting user and verifying if necessary."""
    token = load_token()
    if token:
        try:
            # Verify existing token
            response = requests.get(f'{API_BASE}user', headers=get_headers(token))
            response.raise_for_status()
            return token
        except Exception:
            print("Existing token is invalid.")
    
    # Prompt for new token
    token = input("Please enter your Real-Debrid API token: ").strip()
    if not token:
        raise ValueError("API token is required.")
    
    # Verify new token
    try:
        response = requests.get(f'{API_BASE}user', headers=get_headers(token))
        response.raise_for_status()
        save_token(token)
        print("Token saved successfully.")
        return token
    except Exception as e:
        raise ValueError(f"Invalid token or API error: {e}")

def get_headers(token):
    """Return headers with Bearer token for API requests."""
    return {'Authorization': f'Bearer {token}'}

def extract_magnet_hash(magnet):
    """Extract the torrent hash from a magnet link."""
    parsed = urlparse(magnet)
    params = parse_qs(parsed.query)
    xt = params.get('xt', [''])[0]
    match = re.match(r'urn:btih:([0-9a-fA-F]{40})', xt)
    if match:
        return match.group(1).upper()
    raise ValueError("Invalid magnet link: no valid hash found")

def check_existing_torrent(token, input_val, is_magnet, is_hash):
    """Check if torrent/magnet/hash is already added in Real-Debrid."""
    url = API_BASE + 'torrents'
    response = requests.get(url, headers=get_headers(token))
    response.raise_for_status()
    torrents = response.json()
    input_hash = input_val if is_hash else extract_magnet_hash(input_val)
    for torrent in torrents:
        if torrent['hash'].upper() == input_hash:
            return torrent['id']
    return None

def add_magnet(token, magnet):
    """Add a magnet link to Real-Debrid."""
    url = API_BASE + 'torrents/addMagnet'
    data = {'magnet': magnet}
    response = requests.post(url, headers=get_headers(token), data=data)
    response.raise_for_status()
    return response.json()['id']

def get_torrent_info(token, torrent_id):
    """Fetch information for a specific torrent."""
    url = API_BASE + f'torrents/info/{torrent_id}'
    response = requests.get(url, headers=get_headers(token))
    response.raise_for_status()
    return response.json()

def get_torrent_files(token, torrent_id):
    """Fetch the list of files in a torrent."""
    torrent_info = get_torrent_info(token, torrent_id)
    return torrent_info.get('files', [])

def select_files(token, torrent_id, files='all'):
    """Select files for a torrent."""
    url = API_BASE + f'torrents/selectFiles/{torrent_id}'
    data = {'files': files}
    response = requests.post(url, headers=get_headers(token), data=data)
    response.raise_for_status()

def unrestrict_link(token, link):
    """Unrestrict a link to get a direct download URL."""
    url = API_BASE + 'unrestrict/link'
    data = {'link': link}
    response = requests.post(url, headers=get_headers(token), data=data)
    response.raise_for_status()
    return response.json()['download']

def get_rdplayer_link(token, link):
    """Get Real-Debrid player link for a given link."""
    url = API_BASE + 'streaming/mediaInfos'
    data = {'link': link}
    response = requests.post(url, headers=get_headers(token), data=data)
    response.raise_for_status()
    player_link = response.json().get('streamable')
    if not player_link:
        raise ValueError("No streamable link found for RDPlayer.")
    return player_link

def wait_for_torrent_ready(token, torrent_id):
    """Wait for a torrent to be ready and return its info."""
    while True:
        info = get_torrent_info(token, torrent_id)
        status = info['status']
        if status == 'downloaded':
            return info
        elif status in ['error', 'magnet_error', 'virus', 'dead']:
            raise ValueError(f"Torrent failed with status: {status}")
        time.sleep(POLL_INTERVAL)