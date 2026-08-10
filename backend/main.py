import os
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

RAWG_API_KEY = os.environ.get("RAWG_API_KEY")


def fetch_cover_image(title: str):
    """Looks up a game's cover image on RAWG by title.
    Returns None (never raises) if the key is missing, the request fails,
    or there's no match — a failed lookup should never block adding a game."""
    if not RAWG_API_KEY:
        return None
    try:
        response = requests.get(
            "https://api.rawg.io/api/games",
            params={"key": RAWG_API_KEY, "search": title, "page_size": 1},
            timeout=5,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        if results:
            return results[0].get("background_image")
    except requests.RequestException:
        pass
    return None


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


@app.post("/games")
def create_game(title: str, status: str, priority: int = 3, estimated_hours: int = None):
    db = SessionLocal()
    cover_url = fetch_cover_image(title)
    new_game = Game(
        title=title,
        status=status,
        priority=priority,
        estimated_hours=estimated_hours,
        cover_url=cover_url,
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
        # title changed -> re-look-up the cover so it doesn't go stale
        game.cover_url = fetch_cover_image(title)
        
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