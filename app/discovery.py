# -*- coding: utf-8 -*-
"""Discovery wissellijst: scan bronlijsten, bouw smaakprofiel, score met GPT."""
import os
import json
from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


def build_taste_profile(sp):
    """Bouw een smaakprofiel op basis van Spotify luistergedrag.

    Gebruikt top artiesten, genres en tracks van de afgelopen ~6 maanden.
    Returns: profiel als tekst string.
    """
    try:
        top_artists_medium = sp.current_user_top_artists(
            limit=50, time_range='medium_term')['items']
    except Exception:
        top_artists_medium = []

    try:
        top_artists_short = sp.current_user_top_artists(
            limit=20, time_range='short_term')['items']
    except Exception:
        top_artists_short = []

    try:
        top_tracks = sp.current_user_top_tracks(
            limit=50, time_range='medium_term')['items']
    except Exception:
        top_tracks = []

    # Genres verzamelen en tellen
    all_genres = {}
    for a in top_artists_medium:
        for g in a.get('genres', []):
            all_genres[g] = all_genres.get(g, 0) + 1
    sorted_genres = sorted(all_genres.items(), key=lambda x: -x[1])
    top_genres = [g for g, _ in sorted_genres[:20]]

    # Artiest namen
    medium_artists = [a['name'] for a in top_artists_medium[:25]]
    recent_artists = [a['name'] for a in top_artists_short[:10]]

    # Track info
    track_lines = []
    for t in top_tracks[:30]:
        artists = ', '.join(a['name'] for a in t['artists'])
        track_lines.append(f"  - {artists} - {t['name']}")

    profile_parts = ["=== SMAAKPROFIEL ==="]

    if top_genres:
        profile_parts.append(f"Favoriete genres: {', '.join(top_genres)}")
    if medium_artists:
        profile_parts.append(
            f"Top artiesten (afgelopen 6 maanden): {', '.join(medium_artists)}")
    if recent_artists:
        profile_parts.append(
            f"Recent veel geluisterd: {', '.join(recent_artists)}")
    if track_lines:
        profile_parts.append("Top nummers:")
        profile_parts.extend(track_lines)

    return '\n'.join(profile_parts)


def scan_source_playlists(sp, playlist_ids):
    """Scan bronlijsten en tel overlap.

    Returns: dict van URI -> {artiest, titel, album, uri, overlap, bronnen}
    """
    tracks_map = {}

    for pid in playlist_ids:
        try:
            results = sp.playlist_items(pid, limit=100)
            items = list(results['items'])
            while results.get('next'):
                results = sp.next(results)
                items.extend(results['items'])

            playlist_info = sp.playlist(pid, fields='name')
            playlist_name = playlist_info['name']

            for item in items:
                track = item.get('track')
                if not track or not track.get('uri'):
                    continue

                uri = track['uri']
                artiest = (track['artists'][0]['name']
                           if track.get('artists') else 'Onbekend')
                titel = track['name']
                album = track['album']['name'] if track.get('album') else ''

                if uri in tracks_map:
                    tracks_map[uri]['overlap'] += 1
                    tracks_map[uri]['bronnen'].append(playlist_name)
                else:
                    tracks_map[uri] = {
                        'artiest': artiest,
                        'titel': titel,
                        'album': album,
                        'uri': uri,
                        'overlap': 1,
                        'bronnen': [playlist_name],
                    }
        except Exception as e:
            print(f"Fout bij scannen playlist {pid}: {e}")

    return tracks_map


def _load_history_uris(history_file):
    """Lees historie en return set van URIs."""
    uris = set()
    if history_file and os.path.exists(history_file):
        with open(history_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().rsplit(' - ', 1)
                if len(parts) == 2 and parts[1].startswith('spotify:'):
                    uris.add(parts[1])
    return uris


def _load_playlist_uris(sp, playlist_id):
    """Haal alle URIs op uit een Spotify playlist."""
    uris = set()
    try:
        results = sp.playlist_items(
            playlist_id,
            fields='items(track(uri)),next',
            limit=100,
        )
        for item in results['items']:
            if item.get('track') and item['track'].get('uri'):
                uris.add(item['track']['uri'])
        while results.get('next'):
            results = sp.next(results)
            for item in results['items']:
                if item.get('track') and item['track'].get('uri'):
                    uris.add(item['track']['uri'])
    except Exception:
        pass
    return uris


def score_candidates(candidates, taste_profile):
    """Score tracks met GPT op basis van smaakprofiel.

    Args:
        candidates: lijst van dicts met artiest, titel, album, overlap
        taste_profile: tekst met smaakprofiel

    Returns: dict van index -> score (1-10)
    """
    if not candidates:
        return {}

    # Format tracks voor GPT
    track_lines = []
    for i, t in enumerate(candidates):
        overlap_text = (f" [{t['overlap']}x in bronlijsten]"
                        if t.get('overlap', 1) > 1 else "")
        track_lines.append(
            f"{i}. {t['artiest']} - {t['titel']} ({t.get('album', '')})"
            f"{overlap_text}"
        )

    tracks_text = '\n'.join(track_lines)

    prompt = f"""{taste_profile}

=== OPDRACHT ===
Beoordeel onderstaande tracks op basis van het smaakprofiel hierboven.
Geef elke track een score van 1-10 (10 = perfecte match met de smaak).

Let op:
- Focus op genre, stijl, en vergelijkbare artiesten
- Nummers van artiesten die in het profiel staan krijgen een hogere score
- Wees kritisch maar eerlijk

Tracks om te beoordelen:
{tracks_text}

Antwoord ALLEEN met een JSON array, geen andere tekst:
[{{"i": 0, "s": 8}}, {{"i": 1, "s": 5}}, ...]"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system",
                 "content": "Je bent een muziekexpert die tracks beoordeelt op "
                            "basis van iemands smaakprofiel. Antwoord alleen "
                            "met JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
        )

        content = response.choices[0].message.content.strip()
        # Handle markdown code blocks
        if content.startswith('```'):
            content = content.split('\n', 1)[1].rsplit('```', 1)[0].strip()

        scores_list = json.loads(content)
        scores = {}
        for item in scores_list:
            idx = item.get('i', item.get('index', -1))
            score = item.get('s', item.get('score', 5))
            if 0 <= idx < len(candidates):
                scores[idx] = score

        return scores

    except Exception as e:
        print(f"GPT scoring fout: {e}")
        # Fallback: geef alles een 5
        return {i: 5 for i in range(len(candidates))}


def rank_and_select(candidates, scores, count=10, max_per_artiest=0):
    """Rank candidates op gecombineerde score en selecteer top N.

    Score: smaak_score * 0.7 + overlap_bonus * 0.3
    overlap_bonus = min(overlap_count, 5) * 2  (genormaliseerd naar 0-10)
    """
    ranked = []
    for i, track in enumerate(candidates):
        smaak = scores.get(i, 5)
        overlap = min(track.get('overlap', 1), 5) * 2  # 0-10 range
        combined = smaak * 0.7 + overlap * 0.3
        ranked.append({
            **track,
            'smaak_score': smaak,
            'combined_score': combined,
        })

    ranked.sort(key=lambda x: -x['combined_score'])

    # Selecteer met optionele artiest-limiet
    selected = []
    artiest_count = {}

    for track in ranked:
        artiest = track['artiest']
        if max_per_artiest > 0:
            if artiest_count.get(artiest, 0) >= max_per_artiest:
                continue

        selected.append(track)
        artiest_count[artiest] = artiest_count.get(artiest, 0) + 1

        if len(selected) >= count:
            break

    return selected


def generate_discovery_block(sp, wl, history_file, block_size=10):
    """Genereer een discovery blok: scan -> score -> rank -> selecteer.

    Args:
        sp: Spotify client
        wl: wissellijst config dict
        history_file: pad naar historie bestand
        block_size: aantal tracks per blok

    Returns: lijst van track dicts [{categorie, artiest, titel, uri}] of None
    """
    source_ids = wl.get('bron_playlists', [])
    taste_profile = wl.get('smaakprofiel', '')
    max_per_artiest = wl.get('max_per_artiest', 0)

    if not source_ids:
        print("Geen bronlijsten geconfigureerd")
        return None

    if not taste_profile:
        print("Geen smaakprofiel beschikbaar")
        return None

    # Stap 1: Scan bronlijsten
    all_tracks = scan_source_playlists(sp, source_ids)

    # Stap 2: Filter reeds gebruikte tracks
    history_uris = _load_history_uris(history_file)
    playlist_uris = _load_playlist_uris(sp, wl['playlist_id'])
    used_uris = history_uris | playlist_uris

    candidates = [t for t in all_tracks.values() if t['uri'] not in used_uris]

    if not candidates:
        print("Geen nieuwe tracks gevonden in bronlijsten")
        return None

    # Stap 3: Score met GPT (in batches)
    all_scores = {}
    batch_size = 100
    for batch_start in range(0, len(candidates), batch_size):
        batch = candidates[batch_start:batch_start + batch_size]
        batch_scores = score_candidates(batch, taste_profile)
        for local_idx, score in batch_scores.items():
            all_scores[batch_start + local_idx] = score

    # Stap 4: Rank en selecteer
    selected = rank_and_select(candidates, all_scores, count=block_size,
                               max_per_artiest=max_per_artiest)

    if not selected:
        return None

    return [
        {
            'categorie': 'discovery',
            'artiest': t['artiest'],
            'titel': t['titel'],
            'uri': t['uri'],
        }
        for t in selected
    ]


def initial_fill_discovery(playlist_id, wl, history_file, queue_file,
                           on_progress=None):
    """Initieel vullen van een discovery wissellijst.

    Scant alle bronlijsten, scoort alles in 1x, verdeelt over blokken.

    Args:
        playlist_id: Spotify playlist ID
        wl: volledige wissellijst config
        history_file: pad naar historie bestand
        queue_file: pad naar wachtrij bestand
        on_progress: callback(blok_nr, totaal, tekst)

    Returns: dict met resultaten
    """
    from suggest import get_spotify_client

    sp = get_spotify_client()
    source_ids = wl.get('bron_playlists', [])
    taste_profile = wl.get('smaakprofiel', '')
    max_per_artiest = wl.get('max_per_artiest', 0)
    aantal_blokken = wl.get('aantal_blokken', 5)
    block_size = wl.get('blok_grootte', 10)
    totaal = aantal_blokken + 1  # +1 voor wachtrij

    if on_progress:
        on_progress(0, totaal, "Bronlijsten scannen...")

    # Stap 1: Scan alle bronlijsten (eenmalig)
    all_tracks = scan_source_playlists(sp, source_ids)

    # Stap 2: Filter historie + huidige playlist
    history_uris = _load_history_uris(history_file)
    playlist_uris = _load_playlist_uris(sp, playlist_id)
    used_uris = history_uris | playlist_uris

    candidates = [t for t in all_tracks.values() if t['uri'] not in used_uris]

    if not candidates:
        return {
            "toegevoegd": 0, "blokken": 0,
            "mislukt": totaal, "wachtrij_klaar": False,
        }

    if on_progress:
        on_progress(0, totaal,
                    f"{len(candidates)} unieke tracks gevonden, scoring...")

    # Stap 3: Score alles met GPT (in batches)
    all_scores = {}
    batch_size = 100
    for batch_start in range(0, len(candidates), batch_size):
        batch = candidates[batch_start:batch_start + batch_size]
        batch_scores = score_candidates(batch, taste_profile)
        for local_idx, score in batch_scores.items():
            all_scores[batch_start + local_idx] = score

    # Stap 4: Rank alles en selecteer genoeg voor alle blokken
    total_needed = totaal * block_size
    all_selected = rank_and_select(candidates, all_scores, count=total_needed,
                                   max_per_artiest=max_per_artiest)

    alle_tracks_added = []
    mislukt = 0

    for blok_nr in range(1, totaal + 1):
        is_wachtrij = blok_nr == totaal
        label = ("volgend blokje" if is_wachtrij
                 else f"blok {blok_nr}/{aantal_blokken}")

        if on_progress:
            on_progress(blok_nr, totaal, f"Toevoegen {label}...")

        # Pak de volgende block_size tracks
        start_idx = (blok_nr - 1) * block_size
        end_idx = start_idx + block_size
        block_tracks = all_selected[start_idx:end_idx]

        if not block_tracks:
            mislukt += 1
            continue

        block = [
            {
                'categorie': 'discovery',
                'artiest': t['artiest'],
                'titel': t['titel'],
                'uri': t['uri'],
            }
            for t in block_tracks
        ]

        if is_wachtrij:
            with open(queue_file, "w", encoding="utf-8") as f:
                for t in block:
                    f.write(
                        f"{t['categorie']} - {t['artiest']} - "
                        f"{t['titel']} - {t['uri']}\n"
                    )
        else:
            uris = [t['uri'] for t in block]
            sp.playlist_add_items(playlist_id, uris)
            alle_tracks_added.extend(block)

            with open(history_file, "a", encoding="utf-8") as hf:
                for t in block:
                    hf.write(
                        f"{t['categorie']} - {t['artiest']} - "
                        f"{t['titel']} - {t['uri']}\n"
                    )

    return {
        "toegevoegd": len(alle_tracks_added),
        "blokken": len(alle_tracks_added) // block_size if block_size else 0,
        "mislukt": mislukt,
        "wachtrij_klaar": mislukt < 2,
    }
