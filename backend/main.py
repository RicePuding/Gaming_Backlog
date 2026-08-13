import os
import time
import requests
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException
from database import engine, Base, SessionLocal
from models import Game
from recommendation import (
    score_resume,
    score_something_new,
    get_reason,
    score_quiz,
    get_quiz_reason,
)

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


def _igdb_headers(token):
    return {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {token}",
        "Content-Type": "text/plain",
    }


def fetch_game_metadata(title: str):
    """Looks up a game on IGDB by title and returns everything we want to
    auto-fill: cover image, a combined genre+theme tag list, and a
    quick/medium/long "commitment size" derived from how long the game
    typically takes to beat. Never raises — a failed lookup just means
    empty metadata, it should never block adding a game."""
    empty = {"cover_url": None, "tags": None, "session_length": None, "estimated_hours": None}

    token = get_igdb_token()
    if not TWITCH_CLIENT_ID or not token:
        print("[metadata] No token available, skipping IGDB lookup")
        return empty

    safe_title = title.replace('"', "")

    try:
        # Step 1: find the game itself, its cover, genres, themes, and its
        # internal IGDB id (we need the id for the time-to-beat lookup below)
        response = requests.post(
            "https://api.igdb.com/v4/games",
            headers=_igdb_headers(token),
            data=f'search "{safe_title}"; fields id,cover.url,genres.name,themes.name; limit 1;',
            timeout=5,
        )
        print(f"[metadata] IGDB game search status for '{title}': {response.status_code}")
        response.raise_for_status()
        results = response.json()
        if not results:
            print(f"[metadata] No IGDB match for '{title}'")
            return empty

        game = results[0]

        cover_url = None
        if game.get("cover"):
            cover_url = "https:" + game["cover"]["url"].replace("t_thumb", "t_cover_big")

        # Combine genres + themes into one deduplicated tag list, e.g.
        # "Role-playing (RPG), Adventure, Fantasy, Open world" — this is
        # what lets the quiz offer things like "Horror" (a theme) alongside
        # "Shooter" (a genre) as one unified set of options.
        tag_names = []
        for g in game.get("genres", []):
            if g["name"] not in tag_names:
                tag_names.append(g["name"])
        for t in game.get("themes", []):
            if t["name"] not in tag_names:
                tag_names.append(t["name"])
        tags = ", ".join(tag_names) if tag_names else None

        # Step 2: look up how long this game takes to beat, so we can
        # auto-categorize it instead of asking the user to guess a number.
        session_length = None
        estimated_hours = None
        game_id = game.get("id")
        if game_id:
            try:
                tt_response = requests.post(
                    "https://api.igdb.com/v4/game_time_to_beats",
                    headers=_igdb_headers(token),
                    data=f'where game_id = {game_id}; fields normally;',
                    timeout=5,
                )
                print(f"[metadata] Time-to-beat status for '{title}': {tt_response.status_code}")
                tt_response.raise_for_status()
                tt_results = tt_response.json()
                if tt_results and tt_results[0].get("normally"):
                    # IGDB gives this in seconds; convert to a rough hour count
                    seconds = tt_results[0]["normally"]
                    hours = round(seconds / 3600)
                    estimated_hours = hours
                    if hours < 10:
                        session_length = "quick"
                    elif hours < 30:
                        session_length = "medium"
                    else:
                        session_length = "long"
            except requests.RequestException as e:
                print(f"[metadata] Time-to-beat lookup failed: {e}")
                # Not finding a time-to-beat entry is common (lots of games
                # don't have community data yet) — that's fine, we just
                # leave session_length/estimated_hours as None.

        return {
            "cover_url": cover_url,
            "tags": tags,
            "session_length": session_length,
            "estimated_hours": estimated_hours,
        }
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
            headers=_igdb_headers(token),
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


@app.get("/genres")
def get_genres():
    """Returns the distinct list of genre/theme tags actually present in the
    user's backlog. Since each game's `genre` column can now hold several
    comma-separated tags, we split every game's tag string and flatten them
    into one deduplicated, sorted list. This is what powers the quiz's mood
    buttons — it never offers a tag with zero matching games."""
    db = SessionLocal()
    rows = db.query(Game.genre).filter(Game.genre.isnot(None)).all()
    db.close()

    all_tags = set()
    for (genre_string,) in rows:
        if not genre_string:
            continue
        for tag in genre_string.split(","):
            tag = tag.strip()
            if tag:
                all_tags.add(tag)

    return sorted(all_tags)


@app.post("/games")
def create_game(title: str, status: str, priority: int = 3):
    """Note: cover, genre/theme tags, and session-length category are no
    longer accepted as manual input — they're always auto-derived from
    IGDB, same as the cover image already was."""
    db = SessionLocal()
    metadata = fetch_game_metadata(title)
    new_game = Game(
        title=title,
        status=status,
        priority=priority,
        estimated_hours=metadata["estimated_hours"],
        cover_url=metadata["cover_url"],
        genre=metadata["tags"],
        session_length=metadata["session_length"],
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
def patch_game(game_id: int, title: str = None, status: str = None, priority: int = None):
    db = SessionLocal()
    game = get_game_or_404(db, game_id)
    if title is not None:
        game.title = title
        # title changed -> re-derive everything so it doesn't go stale
        metadata = fetch_game_metadata(title)
        game.cover_url = metadata["cover_url"]
        game.genre = metadata["tags"]
        game.session_length = metadata["session_length"]
        game.estimated_hours = metadata["estimated_hours"]
    if status is not None:
        game.status = status
    if priority is not None:
        game.priority = priority

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


@app.get("/quiz-recommendation")
def quiz_recommendation(session_length: str = "any", genre: str = "any"):
    """The core of the 'what should I play?' chat flow. Filters the backlog
    by commitment size and genre/theme, scores what's left, and returns up
    to the top 3 matches (not just one) with a natural-language explanation
    each — so a near-miss doesn't feel like a dead wrong answer.

    If nothing matches BOTH filters, we relax them one at a time (genre
    first, then session length) rather than returning nothing.
    """
    db = SessionLocal()
    games = db.query(Game).all()
    db.close()

    # Dropped games are never worth suggesting, regardless of filters
    candidates = [g for g in games if g.status != "Dropped"]

    def game_tags(g):
        if not g.genre:
            return []
        return [t.strip() for t in g.genre.split(",")]

    def matches_session(g):
        return session_length == "any" or g.session_length == session_length

    def matches_genre(g):
        return genre == "any" or genre in game_tags(g)

    relaxed_filters = []

    filtered = [g for g in candidates if matches_session(g) and matches_genre(g)]

    if not filtered and genre != "any":
        relaxed_filters = ["genre"]
        filtered = [g for g in candidates if matches_session(g)]

    if not filtered and session_length != "any":
        relaxed_filters = ["session_length"]
        filtered = candidates

    if not filtered:
        return {"found": False, "message": "Your backlog is empty — add some games first!"}

    scored = [(g, score_quiz(g)) for g in filtered]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    top_matches = scored[:3]

    return {
        "found": True,
        "results": [
            {
                "title": g.title,
                "status": g.status,
                "genre": g.genre,
                "cover_url": g.cover_url,
                "reason": get_quiz_reason(g, session_length, genre, relaxed_filters),
            }
            for g, _ in top_matches
        ],
    }