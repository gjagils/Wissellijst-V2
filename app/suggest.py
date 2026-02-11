# -*- coding: utf-8 -*-
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from openai import OpenAI

from config import (
    SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI,
    SPOTIFY_SCOPE, CACHE_PATH,
    OPENAI_API_KEY, HISTORY_FILE, SUGGESTIONS_FILE, QUEUE_FILE,
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


def search_spotify(sp, artist, title):
    """Zoek een track op Spotify en geef de URI terug."""
    results = sp.search(q=f"track:{title} artist:{artist}", limit=1, type="track")
    tracks = results.get("tracks", {}).get("items", [])
    return tracks[0]["uri"] if tracks else None


def load_history(history_file=None):
    """Laad artiesten en URI's uit de historie."""
    history_file = history_file or HISTORY_FILE
    artists = []
    uris = []
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.split(" - ")
                if len(parts) >= 4:
                    artists.append(parts[1].strip())
                    uris.append(parts[3].strip())
    return artists, uris


def ask_gpt_for_suggestions(categorieen, exclude_artists):
    """Vraag GPT om suggesties op basis van vrije categorieën."""
    client = OpenAI(api_key=OPENAI_API_KEY)

    cat_beschrijving = ", ".join(f"{i+1}. {c}" for i, c in enumerate(categorieen))

    prompt = (
        f"Geef {len(categorieen)} muziek suggesties, exact één per categorie.\n"
        f"Categorieën: {cat_beschrijving}\n"
        f"NIET GEBRUIKEN (staan in playlist of historie): {', '.join(exclude_artists[:50])}.\n"
        "Syntax per regel: categorie | artiest | titel\n"
        "Geef ALLEEN de regels, geen extra tekst."
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Je bent een muziekexpert. Geef alleen de gevraagde syntax regels."},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content.strip().split("\n")


def generate_block(sp, playlist_id, categorieen, history_file=None):
    """Genereer één blok suggesties (1 per categorie), gevalideerd op Spotify.

    Returns: lijst van dicts met {categorie, artiest, titel, uri} of None bij fout.
    """
    history_file = history_file or HISTORY_FILE

    # Verzamel artiesten om te vermijden
    current_tracks = sp.playlist_items(playlist_id)["items"]
    active_artists = [t["track"]["artists"][0]["name"] for t in current_tracks if t.get("track")]
    history_artists, history_uris = load_history(history_file)
    exclude = list(set(active_artists[:25] + history_artists[-25:]))

    raw_suggestions = ask_gpt_for_suggestions(categorieen, exclude)

    results = []
    for line in raw_suggestions:
        if "|" not in line:
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue

        categorie = parts[0].strip()
        artist = parts[1].strip()
        title = parts[2].strip()

        uri = search_spotify(sp, artist, title)
        if uri and uri not in history_uris:
            results.append({
                "categorie": categorie,
                "artiest": artist,
                "titel": title,
                "uri": uri,
            })

    return results if len(results) == len(categorieen) else None


def initial_fill(playlist_id, categorieen, history_file=None, on_progress=None):
    """Vul een playlist met 10 blokken + 1 volgend blokje.

    Args:
        playlist_id: Spotify playlist ID
        categorieen: lijst van categorieën (bijv. ["80s", "90s", "vrouwen met jazzy voice"])
        history_file: pad naar historie bestand (optioneel)
        on_progress: callback(blok_nr, totaal, status_tekst) voor voortgang

    Returns: dict met resultaten
    """
    history_file = history_file or HISTORY_FILE
    sp = get_spotify_client()
    alle_tracks = []
    mislukt = 0
    max_retries = 3

    for blok_nr in range(1, 12):  # 10 voor playlist + 1 voor wachtrij
        is_wachtrij = blok_nr == 11
        label = "volgend blokje" if is_wachtrij else f"blok {blok_nr}/10"

        if on_progress:
            on_progress(blok_nr, 11, f"Genereren {label}...")

        block = None
        for poging in range(max_retries):
            block = generate_block(sp, playlist_id, categorieen, history_file)
            if block:
                break

        if not block:
            mislukt += 1
            continue

        if is_wachtrij:
            # Laatste blok gaat naar de wachtrij
            uris = [t["uri"] for t in block]
            queue_file = os.path.join(os.path.dirname(history_file), "volgende_blokje.txt")
            with open(queue_file, "w", encoding="utf-8") as f:
                f.write("\n".join(uris))

            # Schrijf ook leesbaar naar aanbevelingen
            suggestions_file = os.path.join(os.path.dirname(history_file), "aanbevelingen.txt")
            with open(suggestions_file, "w", encoding="utf-8") as f:
                for t in block:
                    f.write(f"{t['categorie']} - {t['artiest']} - {t['titel']} - {t['uri']}\n")
        else:
            # Voeg toe aan playlist
            uris = [t["uri"] for t in block]
            sp.playlist_add_items(playlist_id, uris)
            alle_tracks.extend(block)

    return {
        "toegevoegd": len(alle_tracks),
        "blokken": len(alle_tracks) // len(categorieen) if categorieen else 0,
        "mislukt": mislukt,
        "wachtrij_klaar": mislukt < 2,  # minimaal het wachtrij-blok is gelukt
    }


# Standalone mode (backwards compatible)
if __name__ == "__main__":
    from config import HISTORY_FILE as _hf
    DEFAULT_CATEGORIES = ["80s", "90s", "00s", "10s", "20s"]

    sp = get_spotify_client()
    # Lees playlist ID uit env (oude manier)
    playlist_id = os.environ.get("SPOTIFY_PLAYLIST_ID", "")
    if not playlist_id:
        print("SPOTIFY_PLAYLIST_ID niet ingesteld.")
        exit(1)

    block = generate_block(sp, playlist_id, DEFAULT_CATEGORIES)
    if block and len(block) == 5:
        uris = [t["uri"] for t in block]
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(uris))

        with open(SUGGESTIONS_FILE, "w", encoding="utf-8") as f:
            for t in block:
                f.write(f"{t['categorie']} - {t['artiest']} - {t['titel']} - {t['uri']}\n")
            f.write("\n--- KOPIEER BLOK HIERONDER ---\n")
            f.write("\n".join(uris))

        print("Suggesties gegenereerd en klaargezet.")
    else:
        print("Niet genoeg geldige suggesties gevonden.")
