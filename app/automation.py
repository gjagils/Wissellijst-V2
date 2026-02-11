import spotipy
from spotipy.oauth2 import SpotifyOAuth

from config import (
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI,
    SPOTIFY_SCOPE, CACHE_PATH,
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


def rotate_playlist(playlist_id, queue_file=None, history_file=None):
    """Verwijder de oudste nummers en voeg nieuwe toe uit de wachtrij."""
    queue_file = queue_file or QUEUE_FILE
    history_file = history_file or HISTORY_FILE

    if not os.path.exists(queue_file) or os.stat(queue_file).st_size == 0:
        print("Wachtrij is leeg. Geen update nodig.")
        return

    with open(queue_file, "r") as f:
        new_tracks = [line.strip() for line in f if line.strip()]

    if not new_tracks:
        print("Wachtrij is leeg.")
        return

    block_size = len(new_tracks)
    sp = get_spotify_client()

    # Haal huidige playlist op en log de oudste naar historie
    current_items = sp.playlist_items(playlist_id, limit=50)["items"]
    tracks_to_remove = []

    with open(history_file, "a", encoding="utf-8") as hf:
        for item in current_items[:block_size]:
            track = item["track"]
            decade = get_decade(track["album"]["release_date"])
            artist = track["artists"][0]["name"]
            name = track["name"]
            uri = track["uri"]
            hf.write(f"{decade} - {artist} - {name} - {uri}\n")
            tracks_to_remove.append(uri)

    # Verwijder oud, voeg nieuw toe
    if tracks_to_remove:
        sp.playlist_remove_all_occurrences_of_items(playlist_id, tracks_to_remove)
        sp.playlist_add_items(playlist_id, new_tracks)
        print("Playlist succesvol geroteerd.")

    # Wachtrij leegmaken
    with open(queue_file, "w") as f:
        f.write("")


if __name__ == "__main__":
    playlist_id = os.environ.get("SPOTIFY_PLAYLIST_ID", "")
    if not playlist_id:
        print("SPOTIFY_PLAYLIST_ID niet ingesteld.")
        exit(1)
    rotate_playlist(playlist_id)
