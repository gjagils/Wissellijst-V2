import os
from dotenv import load_dotenv

load_dotenv()

# Spotify
SPOTIFY_CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
SPOTIFY_CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
SPOTIFY_PLAYLIST_ID = os.environ["SPOTIFY_PLAYLIST_ID"]
SPOTIFY_SCOPE = "playlist-modify-public playlist-modify-private"

# OpenAI
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# Paden
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
QUEUE_FILE = os.path.join(DATA_DIR, "volgende_blokje.txt")
HISTORY_FILE = os.path.join(DATA_DIR, "historie.txt")
SUGGESTIONS_FILE = os.path.join(DATA_DIR, "aanbevelingen.txt")
CACHE_PATH = os.path.join(DATA_DIR, ".cache")
