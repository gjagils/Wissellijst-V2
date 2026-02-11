import spotipy
from spotipy.oauth2 import SpotifyOAuth

from config import (
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI,
    SPOTIFY_PLAYLIST_ID, SPOTIFY_SCOPE, CACHE_PATH,
    QUEUE_FILE, HISTORY_FILE,
)
import os


def get_spotify_client():
    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SPOTIFY_SCOPE,
        cache_path=CACHE_PATH,
        open_browser=False,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def get_decade(release_date):
    """Bepaal het decennium op basis van release datum, bijv. '90s'."""
    try:
        year = int(release_date.split("-")[0])
        return f"{str((year // 10) * 10)[2:]}s"
    except Exception:
        return "Unknown"


def rotate_playlist():
    """Verwijder de 5 oudste nummers en voeg 5 nieuwe toe uit de wachtrij."""
    if not os.path.exists(QUEUE_FILE) or os.stat(QUEUE_FILE).st_size == 0:
        print("Wachtrij is leeg. Geen update nodig.")
        return

    with open(QUEUE_FILE, "r") as f:
        new_tracks = [line.strip() for line in f if line.strip()]

    if len(new_tracks) != 5:
        print(f"Fout: {len(new_tracks)} nummers gevonden, moeten er 5 zijn.")
        return

    sp = get_spotify_client()

    # Haal huidige playlist op en log de eerste 5 (oudste) naar historie
    current_items = sp.playlist_items(SPOTIFY_PLAYLIST_ID, limit=50)["items"]
    tracks_to_remove = []

    with open(HISTORY_FILE, "a", encoding="utf-8") as hf:
        for item in current_items[:5]:
            track = item["track"]
            decade = get_decade(track["album"]["release_date"])
            artist = track["artists"][0]["name"]
            name = track["name"]
            uri = track["uri"]
            hf.write(f"{decade} - {artist} - {name} - {uri}\n")
            tracks_to_remove.append(uri)

    # Verwijder oud, voeg nieuw toe
    if tracks_to_remove:
        sp.playlist_remove_all_occurrences_of_items(SPOTIFY_PLAYLIST_ID, tracks_to_remove)
        sp.playlist_add_items(SPOTIFY_PLAYLIST_ID, new_tracks)
        print("Playlist succesvol geroteerd.")

    # Wachtrij leegmaken
    with open(QUEUE_FILE, "w") as f:
        f.write("")


if __name__ == "__main__":
    rotate_playlist()
