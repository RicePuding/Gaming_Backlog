import os
import time
import requests
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from database import engine, Base, SessionLocal
from models import Game
from recommendation import score_resume, score_something_new, get_reason

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://gaming-backlog-steel.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Looking at every class that inherits from Base
Base.metadata.create_all(bind=engine)

# starting server: uvicorn main:app --reload

TWITCH_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET")

# In-memory cache for the IGDB access token, so we don't request a new one
# on every single game lookup. Twitch tokens last a long time (~60 days),
# we just refresh a little before they actually expire.
_igdb_token_cache = {"access_token": None, "expires_at": 0}


def get_igdb_token():
    """Returns a valid IGDB/Twitch access token, fetching a new one only
    when we don't have one cached or it's about to expire."""
    if _igdb_token_cache["access_token"] and time.time() < _igdb_token_cache["expires_at"]:
        return _igdb_token_cache["access_token"]

    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        print("[igdb] Missing TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET env var")
        return None

    try:
        response = requests.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": TWITCH_CLIENT_ID,
                "client_secret": TWITCH_CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
            timeout=5,
        )
        print(f"[igdb] Twitch token request status: {response.status_code}")
        if response.status_code != 200:
            print(f"[igdb] Twitch token response body: {response.text}")
        response.raise_for_status()
        data = response.json()
        _igdb_token_cache["access_token"] = data["access_token"]
        # Refresh 60 seconds early as a safety margin
        _igdb_token_cache["expires_at"] = time.time() + data["expires_in"] - 60
        return _igdb_token_cache["access_token"]
    except requests.RequestException as e:
        print(f"[igdb] Twitch token request failed: {e}")
        return None


def fetch_game_metadata(title: str):
    """Looks up a game on IGDB by title and returns its cover image URL and
    primary genre in one request. Returns {"cover_url": None, "genre": None}
    (never raises) if credentials are missing, the request fails, or
    there's no match — a failed lookup should never block adding a game."""
    empty = {"cover_url": None, "genre": None}
    token = get_igdb_token()
    if not TWITCH_CLIENT_ID or not token:
        print("[metadata] No token available, skipping IGDB lookup")
        return empty

    safe_title = title.replace('"', "")

    try:
        response = requests.post(
            "https://api.igdb.com/v4/games",
            headers={
                "Client-ID": TWITCH_CLIENT_ID,
                "Authorization": f"Bearer {token}",
                "Content-Type": "text/plain",
            },
            data=f'search "{safe_title}"; fields cover.url,genres.name; limit 1;',
            timeout=5,
        )
        print(f"[metadata] IGDB request status for '{title}': {response.status_code}")
        response.raise_for_status()
        results = response.json()
        if not results:
            print(f"[metadata] No IGDB match for '{title}'")
            return empty

        game = results[0]
        cover_url = None
        if game.get("cover"):
            cover_url = "https:" + game["cover"]["url"].replace("t_thumb", "t_cover_big")

        genre = None
        if game.get("genres"):
            genre = game["genres"][0]["name"]

        return {"cover_url": cover_url, "genre": genre}
    except requests.RequestException as e:
        print(f"[metadata] IGDB request failed: {e}")
        return empty


def get_game_or_404(db, game_id: int):
    game = db.query(Game).filter(Game.id == game_id).first()
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@app.get("/health")
def health():
    return {"status": "ok"}

# http://127.0.0.1:8000/health


@app.get("/games")
def get_games():
    db = SessionLocal()
    games = db.query(Game).all()
    db.close()
    return games


@app.get("/games/search")
def search_games(q: str):
    """Used by the frontend's autocomplete as the user types a game title.
    Returns up to 5 IGDB matches with name, cover, and genres so the user
    can pick the correct canonical title instead of free-typing one."""
    token = get_igdb_token()
    if not TWITCH_CLIENT_ID or not token or not q:
        return []

    safe_q = q.replace('"', "")

    try:
        response = requests.post(
            "https://api.igdb.com/v4/games",
            headers={
                "Client-ID": TWITCH_CLIENT_ID,
                "Authorization": f"Bearer {token}",
                "Content-Type": "text/plain",
            },
            data=f'search "{safe_q}"; fields name,cover.url,genres.name; limit 5;',
            timeout=5,
        )
        response.raise_for_status()
        results = response.json()

        suggestions = []
        for game in results:
            cover_url = None
            if game.get("cover"):
                cover_url = "https:" + game["cover"]["url"].replace("t_thumb", "t_cover_big")
            genres = [g["name"] for g in game.get("genres", [])]
            suggestions.append({
                "name": game.get("name"),
                "cover_url": cover_url,
                "genres": genres,
            })
        return suggestions
    except requests.RequestException as e:
        print(f"[search] IGDB search failed: {e}")
        return []


@app.post("/games")
def create_game(title: str, status: str, priority: int = 3, estimated_hours: int = None):
    db = SessionLocal()
    metadata = fetch_game_metadata(title)
    new_game = Game(
        title=title,
        status=status,
        priority=priority,
        estimated_hours=estimated_hours,
        cover_url=metadata["cover_url"],
        genre=metadata["genre"],
    )
    db.add(new_game)
    db.commit()
    db.refresh(new_game)
    db.close()
    return new_game


@app.delete("/games/{game_id}")
def delete_game(game_id: int):
    db = SessionLocal()
    game = get_game_or_404(db, game_id)
    db.delete(game)
    db.commit()
    db.close()
    return {"deleted": True}


@app.patch("/games/{game_id}")
def patch_game(game_id: int, title: str = None, status: str = None, priority: int = None, estimated_hours: int = None):
    db = SessionLocal()
    game = get_game_or_404(db, game_id)
    if title is not None:
        game.title = title
        # title changed -> re-look-up cover + genre so they don't go stale
        metadata = fetch_game_metadata(title)
        game.cover_url = metadata["cover_url"]
        game.genre = metadata["genre"]
    if status is not None:
        game.status = status
    if priority is not None:
        game.priority = priority
    if estimated_hours is not None:
        game.estimated_hours = estimated_hours

    db.commit()
    db.refresh(game)
    db.close()
    return game


@app.get("/recommendations")
def get_recommendations(mode: str = "resume"):
    db = SessionLocal()
    games = db.query(Game).all()
    db.close()

    if mode == "resume":
        scored = [(game, score_resume(game)) for game in games]
    else:
        not_started = [g for g in games if g.status == "Not Started"]
        scored = [(game, score_something_new(game)) for game in not_started]

    scored.sort(key=lambda pair: pair[1], reverse=True)

    top_three = scored[:3]

    return [
        {
            "title": game.title,
            "status": game.status,
            "score": score,
            "reason": get_reason(game, mode),
        }
        for game, score in top_three
    ]