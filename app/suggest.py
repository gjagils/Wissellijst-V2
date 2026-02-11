# -*- coding: utf-8 -*-
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from openai import OpenAI

from config import (
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI,
    SPOTIFY_PLAYLIST_ID, SPOTIFY_SCOPE, CACHE_PATH,
    OPENAI_API_KEY, HISTORY_FILE, SUGGESTIONS_FILE, QUEUE_FILE,
)
import os


def get_spotify_client():
    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        cache_path=CACHE_PATH,
        open_browser=False,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def search_spotify(sp, artist, title):
    """Zoek een track op Spotify en geef de URI terug."""
    results = sp.search(q=f"track:{title} artist:{artist}", limit=1, type="track")
    tracks = results.get("tracks", {}).get("items", [])
    return tracks[0]["uri"] if tracks else None


def load_history():
    """Laad artiesten en URI's uit de historie."""
    artists = []
    uris = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split(" - ")
                if len(parts) >= 4:
                    artists.append(parts[1].strip())
                    uris.append(parts[3].strip())
    return artists, uris


def ask_gpt_for_suggestions(exclude_artists):
    """Vraag GPT-4o om 5 suggesties (1 per decennium)."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    prompt = (
        "Geef 5 nieuwe suggesties (een uit de 80s, 90s, 00s, 10s en 20s). "
        f"NIET GEBRUIKEN (staan in playlist of historie): {', '.join(exclude_artists[:50])}. "
        "Syntax per regel: decennium | artiest | titel"
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Muziekexpert. Geef alleen de gevraagde syntax regels."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip().split("\n")


def get_suggestions():
    """Genereer suggesties, valideer op Spotify, en zet ze klaar."""
    sp = get_spotify_client()

    # Verzamel artiesten om te vermijden
    current_tracks = sp.playlist_items(SPOTIFY_PLAYLIST_ID)["items"]
    active_artists = [t["track"]["artists"][0]["name"] for t in current_tracks]
    history_artists, history_uris = load_history()
    exclude = active_artists[:25] + history_artists[-25:]

    # Vraag GPT om suggesties
    raw_suggestions = ask_gpt_for_suggestions(exclude)

    readable_lines = []
    just_links = []

    for line in raw_suggestions:
        if "|" not in line:
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue

        decade = parts[0].strip()
        artist = parts[1].strip()
        title = parts[2].strip()

        uri = search_spotify(sp, artist, title)
        if uri and uri not in history_uris:
            readable_lines.append(f"{decade} - {artist} - {title} - {uri}")
            just_links.append(uri)

    # Schrijf aanbevelingen (leesbaar overzicht)
    with open(SUGGESTIONS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(readable_lines))
        f.write("\n\n--- KOPIEER BLOK HIERONDER ---\n")
        f.write("\n".join(just_links))

    # Vul wachtrij als we precies 5 hebben
    if len(just_links) == 5:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(just_links))
        print("Suggesties gegenereerd en klaargezet in volgende_blokje.txt")
    else:
        print(f"Let op: {len(just_links)} links gevonden (5 nodig). Wachtrij niet gevuld.")


if __name__ == "__main__":
    get_suggestions()
