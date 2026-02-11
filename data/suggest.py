# -*- coding: utf-8 -*-
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from openai import OpenAI

# CONFIGURATIE
CLIENT_ID = 'f07f3d5b917a4a019b46259ba063a629'
CLIENT_SECRET = '7ad604e14ce842e2881ddbb00493ca04'
REDIRECT_URI = 'http://127.0.0.1:8888/callback'
PLAYLIST_ID = '4xSVIQpVLDBsBvwA10xzqj'
OPENAI_API_KEY = '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'

BASE_DIR = '/app/data'
HISTORY_FILE = os.path.join(BASE_DIR, 'historie.txt')
SUGGESTIONS_FILE = os.path.join(BASE_DIR, 'aanbevelingen.txt')
QUEUE_FILE = os.path.join(BASE_DIR, 'volgende_blokje.txt')
CACHE_PATH = os.path.join(BASE_DIR, '.cache')

client = OpenAI(api_key=OPENAI_API_KEY)

def search_spotify(sp, artist, title):
    query = f"track:{title} artist:{artist}"
    results = sp.search(q=query, limit=1, type='track')
    tracks = results.get('tracks', {}).get('items', [])
    return tracks[0]['uri'] if tracks else "GEEN LINK GEVONDEN"

def get_suggestions():
    auth_manager = SpotifyOAuth(client_id=CLIENT_ID, client_secret=CLIENT_SECRET, 
                                redirect_uri=REDIRECT_URI, cache_path=CACHE_PATH, open_browser=False)
    sp = spotipy.Spotify(auth_manager=auth_manager)
    
    current_tracks = sp.playlist_items(PLAYLIST_ID)['items']
    active_artists = [t['track']['artists'][0]['name'] for t in current_tracks]
    
    history_uris = []
    history_artists = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.split(' - ')
                if len(parts) >= 4:
                    history_artists.append(parts[1].strip())
                    history_uris.append(parts[3].strip())

    prompt = f"""Geef 5 nieuwe suggesties (een uit de 80s, 90s, 00s, 10s en 20s). 
    NIET GEBRUIKEN (staan in playlist of historie): {", ".join(active_artists[:25])}, {", ".join(history_artists[-25:])}.
    Syntax per regel: decennium | artiest | titel"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": "Muziekexpert. Geef alleen de gevraagde syntax regels."},
                  {"role": "user", "content": prompt}]
    )

    raw_suggestions = response.choices[0].message.content.strip().split('\n')
    
    readable_lines = []
    just_links = []

    for line in raw_suggestions:
        if '|' in line:
            parts = line.split('|')
            decade = parts[0].strip()
            artist = parts[1].strip()
            title = parts[2].strip()
            
            uri = search_spotify(sp, artist, title)
            
            # Alleen toevoegen als het geen duplicaat is en de link gevonden is
            if uri != "GEEN LINK GEVONDEN" and uri not in history_uris:
                readable_lines.append(f"{decade} - {artist} - {title} - {uri}")
                just_links.append(uri)

    # 1. Schrijf naar aanbevelingen.txt voor jouw overzicht
    with open(SUGGESTIONS_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(readable_lines))
        f.write("\n\n--- KOPIEER BLOK HIERONDER ---\n")
        f.write("\n".join(just_links))
    
    # 2. Vul automatisch volgende_blokje.txt voor de volgende run
    if len(just_links) == 5:
        with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
            f.write("\n".join(just_links))
        print("Suggesties gegenereerd en automatisch klaargezet in volgende_blokje.txt")
    else:
        print(f"Let op: Slechts {len(just_links)} links gevonden. Volgende blokje niet automatisch gevuld.")

if __name__ == "__main__":
    get_suggestions()