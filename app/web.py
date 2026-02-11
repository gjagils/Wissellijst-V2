# -*- coding: utf-8 -*-
import uuid
import threading
from flask import Flask, render_template, request, jsonify

from config import (
    load_wissellijsten, save_wissellijsten, get_wissellijst,
    DATA_DIR,
)
from suggest import get_spotify_client, initial_fill

app = Flask(__name__)

# Voortgang bijhouden per taak
_tasks = {}


@app.route("/")
def index():
    return render_template("index.html")


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
