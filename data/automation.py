import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os

# CONFIGURATIE
CLIENT_ID = 'f07f3d5b917a4a019b46259ba063a629'
CLIENT_SECRET = '7ad604e14ce842e2881ddbb00493ca04'
REDIRECT_URI = 'http://127.0.0.1:8888/callback'
PLAYLIST_ID = '4xSVIQpVLDBsBvwA10xzqj' 
SCOPE = 'playlist-modify-public playlist-modify-private'

# PADEN
BASE_DIR = '/app/data'
QUEUE_FILE = os.path.join(BASE_DIR, 'volgende_blokje.txt')
CACHE_PATH = os.path.join(BASE_DIR, '.cache')
HISTORY_FILE = os.path.join(BASE_DIR, 'historie.txt')

def get_decade(release_date):
    try:
        year = int(release_date.split('-')[0])
        decade_year = (year // 10) * 10
        decade_short = str(decade_year)[2:4]
        return f"{decade_short}s"
    except:
        return "Unknown"

def rotate_playlist():
    auth_manager = SpotifyOAuth(
        client_id=CLIENT_ID, client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI, scope=SCOPE, 
        cache_path=CACHE_PATH, open_browser=False 
    )
    sp = spotipy.Spotify(auth_manager=auth_manager)

    if not os.path.exists(QUEUE_FILE) or os.stat(QUEUE_FILE).st_size == 0:
        print("Wachtrij is leeg. Geen update nodig.")
        return

    with open(QUEUE_FILE, 'r') as f:
        new_tracks = [line.strip() for line in f.readlines() if line.strip()]

    if len(new_tracks) != 5:
        print(f"Fout: {len(new_tracks)} nummers gevonden, moeten er 5 zijn.")
        return

    current_tracks_data = sp.playlist_items(PLAYLIST_ID, limit=50)['items']
    removed_tracks_info = []
    track_ids_to_remove = []

    for item in current_tracks_data[:5]:
        track = item['track']
        decade_label = get_decade(track['album']['release_date'])
        history_line = f"{decade_label} - {track['artists'][0]['name']} - {track['name']} - {track['uri']}"
        removed_tracks_info.append(history_line)
        track_ids_to_remove.append(track['uri'])

    with open(HISTORY_FILE, 'a', encoding='utf-8') as hf:
        for line in removed_tracks_info:
            hf.write(line + '\n')
    
    if track_ids_to_remove:
        sp.playlist_remove_all_occurrences_of_items(PLAYLIST_ID, track_ids_to_remove)
        sp.playlist_add_items(PLAYLIST_ID, new_tracks)
        print("Playlist succesvol geroteerd.")

    with open(QUEUE_FILE, 'w') as f:
        f.write("")

if __name__ == "__main__":
    rotate_playlist()