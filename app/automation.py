import os

from config import (
    QUEUE_FILE, HISTORY_FILE,
    load_wissellijsten, get_history_file, get_queue_file,
)
from suggest import _parse_history_line, get_spotify_client


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
        return {"status": "leeg", "tekst": "Wachtrij is leeg."}

    # Lees wachtrij - ondersteunt zowel URI-only als volledig formaat
    new_uris = []
    with open(queue_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parsed = _parse_history_line(line)
            if parsed:
                new_uris.append(parsed["uri"])
            elif line.startswith("spotify:"):
                new_uris.append(line)

    if not new_uris:
        print("Wachtrij is leeg.")
        return {"status": "leeg", "tekst": "Wachtrij is leeg."}

    block_size = len(new_uris)
    sp = get_spotify_client()

    # Haal huidige playlist op en log de oudste naar historie
    current_items = sp.playlist_items(playlist_id, limit=50)["items"]
    tracks_to_remove = []

    with open(history_file, "a", encoding="utf-8") as hf:
        for item in current_items[:block_size]:
            track = item["track"]
            if not track:
                continue
            decade = get_decade(track["album"]["release_date"])
            artist = track["artists"][0]["name"]
            name = track["name"]
            uri = track["uri"]
            hf.write(f"{decade} - {artist} - {name} - {uri}\n")
            tracks_to_remove.append(uri)

    # Verwijder oud, voeg nieuw toe
    if tracks_to_remove:
        sp.playlist_remove_all_occurrences_of_items(playlist_id, tracks_to_remove)
        sp.playlist_add_items(playlist_id, new_uris)
        print("Playlist succesvol geroteerd.")

    # Wachtrij leegmaken
    with open(queue_file, "w") as f:
        f.write("")

    return {
        "status": "ok",
        "tekst": f"{len(tracks_to_remove)} nummers geroteerd.",
        "verwijderd": len(tracks_to_remove),
        "toegevoegd": len(new_uris),
    }


def rotate_and_regenerate(wl):
    """Roteer een wissellijst en genereer een nieuw wachtrij-blok.

    Voor discovery: eerst nieuw blok analyseren, dan pas roteren.
    Voor categorie: eerst roteren, dan nieuw blok genereren.

    Args:
        wl: wissellijst dict met alle configuratie
    Returns: dict met resultaten
    """
    from suggest import generate_block

    queue_file = get_queue_file(wl["id"])
    history_file = get_history_file(wl["id"])
    is_discovery = wl.get("type") == "discovery"

    if is_discovery:
        return _rotate_discovery(wl, queue_file, history_file)

    # --- Categorie flow: roteer eerst, genereer daarna ---

    # Stap 1: Roteer
    result = rotate_playlist(wl["playlist_id"], queue_file=queue_file,
                             history_file=history_file)

    if result["status"] == "leeg":
        return result

    # Stap 2: Genereer nieuw blokje voor de wachtrij
    sp = get_spotify_client()
    block = None
    max_retries = 3
    for _ in range(max_retries):
        block = generate_block(sp, wl["playlist_id"],
                               wl.get("categorieen", []),
                               history_file=history_file,
                               max_per_artiest=wl.get("max_per_artiest", 0))
        if block:
            break

    if block:
        with open(queue_file, "w", encoding="utf-8") as f:
            for t in block:
                f.write(f"{t['categorie']} - {t['artiest']} - {t['titel']} - {t['uri']}\n")
        result["nieuw_blok"] = True
    else:
        result["nieuw_blok"] = False
        result["tekst"] += " (Nieuw wachtrij-blok genereren mislukt)"

    return result


def _rotate_discovery(wl, queue_file, history_file):
    """Discovery rotatie: eerst analyseren, dan roteren.

    1. Genereer nieuw blok (scan bronlijsten + GPT scoring)
    2. Schrijf naar wachtrij
    3. Roteer playlist (oud eruit, wachtrij erin)
    """
    from discovery import generate_discovery_block

    sp = get_spotify_client()

    # Stap 1: Genereer nieuw blok
    print(f"[discovery-rotate] Stap 1: Analyseren voor {wl['naam']}...",
          flush=True)
    block = generate_discovery_block(
        sp, wl, history_file,
        block_size=wl.get("blok_grootte", 10),
    )

    if not block:
        return {
            "status": "fout",
            "tekst": "Kon geen nieuw blok genereren uit bronlijsten.",
        }

    # Stap 2: Schrijf naar wachtrij
    with open(queue_file, "w", encoding="utf-8") as f:
        for t in block:
            f.write(f"{t['categorie']} - {t['artiest']} - "
                    f"{t['titel']} - {t['uri']}\n")
    print(f"[discovery-rotate] Stap 2: {len(block)} tracks in wachtrij",
          flush=True)

    # Stap 3: Roteer
    print(f"[discovery-rotate] Stap 3: Roteren...", flush=True)
    result = rotate_playlist(wl["playlist_id"], queue_file=queue_file,
                             history_file=history_file)
    result["nieuw_blok"] = True
    return result


if __name__ == "__main__":
    # Roteer alle wissellijsten
    data = load_wissellijsten()
    if not data["wissellijsten"]:
        # Fallback naar oude env-var manier
        playlist_id = os.environ.get("SPOTIFY_PLAYLIST_ID", "")
        if not playlist_id:
            print("Geen wissellijsten gevonden en SPOTIFY_PLAYLIST_ID niet ingesteld.")
            exit(1)
        rotate_playlist(playlist_id)
    else:
        for wl in data["wissellijsten"]:
            print(f"Roteer: {wl['naam']}...")
            queue_file = get_queue_file(wl["id"])
            history_file = get_history_file(wl["id"])
            rotate_playlist(wl["playlist_id"], queue_file=queue_file,
                            history_file=history_file)
