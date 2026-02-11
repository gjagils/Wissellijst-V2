# -*- coding: utf-8 -*-
import os
import uuid
import threading
from flask import Flask, render_template, request, jsonify, redirect
from spotipy.oauth2 import SpotifyOAuth

from config import (
    load_wissellijsten, save_wissellijsten, get_wissellijst,
    get_history_file, DATA_DIR, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI, SPOTIFY_SCOPE, CACHE_PATH,
)
from suggest import get_spotify_client, initial_fill, load_history

app = Flask(__name__)

# Voortgang bijhouden per taak
_tasks = {}


def _get_auth_manager():
    return SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SPOTIFY_SCOPE,
        cache_path=CACHE_PATH,
        open_browser=False,
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login")
def login():
    """Redirect naar Spotify login."""
    auth_manager = _get_auth_manager()
    auth_url = auth_manager.get_authorize_url()
    return redirect(auth_url)


@app.route("/callback")
def callback():
    """Ontvang de auth code van Spotify en sla het token op."""
    code = request.args.get("code")
    error = request.args.get("error")

    if error:
        return jsonify({"error": error}), 400

    if not code:
        return jsonify({"error": "Geen code ontvangen"}), 400

    auth_manager = _get_auth_manager()
    auth_manager.get_access_token(code)
    return redirect("/")


@app.route("/api/playlists")
def api_playlists():
    """Haal alle playlists van de Spotify gebruiker op."""
    try:
        sp = get_spotify_client()
        results = []
        offset = 0
        while True:
            batch = sp.current_user_playlists(limit=50, offset=offset)
            results.extend(batch["items"])
            if not batch["next"]:
                break
            offset += 50

        playlists = [
            {"id": p["id"], "naam": p["name"], "tracks": p["tracks"]["total"]}
            for p in results
        ]
        return jsonify(playlists)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/wissellijsten")
def api_wissellijsten():
    """Haal alle opgeslagen wissellijst-configuraties op."""
    data = load_wissellijsten()
    return jsonify(data["wissellijsten"])


@app.route("/api/wissellijsten", methods=["POST"])
def api_wissellijst_opslaan():
    """Maak een nieuwe wissellijst aan of update een bestaande."""
    body = request.json
    data = load_wissellijsten()

    lijst_id = body.get("id")
    if lijst_id:
        # Update bestaande
        for i, wl in enumerate(data["wissellijsten"]):
            if wl["id"] == lijst_id:
                data["wissellijsten"][i] = body
                break
    else:
        # Nieuwe aanmaken
        body["id"] = str(uuid.uuid4())[:8]
        data["wissellijsten"].append(body)

    save_wissellijsten(data)
    return jsonify(body)


@app.route("/api/wissellijsten/<lijst_id>", methods=["DELETE"])
def api_wissellijst_verwijderen(lijst_id):
    """Verwijder een wissellijst-configuratie."""
    data = load_wissellijsten()
    data["wissellijsten"] = [wl for wl in data["wissellijsten"] if wl["id"] != lijst_id]
    save_wissellijsten(data)
    return jsonify({"ok": True})


@app.route("/api/vullen", methods=["POST"])
def api_vullen():
    """Start het initieel vullen van een wissellijst (async)."""
    body = request.json
    lijst_id = body.get("lijst_id")

    wl = get_wissellijst(lijst_id)
    if not wl:
        return jsonify({"error": "Wissellijst niet gevonden"}), 404

    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {"status": "bezig", "voortgang": 0, "tekst": "Starten...", "resultaat": None}

    def run():
        def on_progress(blok_nr, totaal, tekst):
            _tasks[task_id]["voortgang"] = round(blok_nr / totaal * 100)
            _tasks[task_id]["tekst"] = tekst

        try:
            result = initial_fill(
                playlist_id=wl["playlist_id"],
                categorieen=wl["categorieen"],
                history_file=get_history_file(lijst_id),
                max_per_artiest=wl.get("max_per_artiest", 0),
                on_progress=on_progress,
            )
            _tasks[task_id]["status"] = "klaar"
            _tasks[task_id]["voortgang"] = 100
            _tasks[task_id]["tekst"] = f"{result['toegevoegd']} nummers toegevoegd ({result['blokken']} blokken)"
            _tasks[task_id]["resultaat"] = result
        except Exception as e:
            _tasks[task_id]["status"] = "fout"
            _tasks[task_id]["tekst"] = str(e)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    return jsonify({"task_id": task_id})


@app.route("/api/vullen/<task_id>")
def api_vullen_status(task_id):
    """Check de voortgang van een vul-taak."""
    task = _tasks.get(task_id)
    if not task:
        return jsonify({"error": "Taak niet gevonden"}), 404
    return jsonify(task)


@app.route("/api/wissellijsten/<lijst_id>/historie")
def api_historie(lijst_id):
    """Haal de historie op van een wissellijst."""
    wl = get_wissellijst(lijst_id)
    if not wl:
        return jsonify({"error": "Wissellijst niet gevonden"}), 404

    history_file = get_history_file(lijst_id)
    entries = []
    if os.path.exists(history_file):
        with open(history_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" - ")
                if len(parts) >= 4:
                    entries.append({
                        "categorie": parts[0].strip(),
                        "artiest": parts[1].strip(),
                        "titel": parts[2].strip(),
                        "uri": parts[3].strip(),
                    })

    return jsonify(entries)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
