' This part is to implement the recommendations logic!'
' There is some nuance so hopefully I will improve it'


def score_resume(game):
    score = 0
    score += game.priority * 3
    if game.status == "Playing":
        score += 8
    if game.status == "Paused":
        score += 5
    if game.status == "Dropped":
        score -= 5
    return score


def score_something_new(game):
    score = 0
    score += game.priority * 3
    if game.status == "Not Started":
        score += 8
    if game.status == "Dropped":
        score -= 5
    return score


def get_reason(game, mode):
    if mode == "resume":
        return f"You're already {game.priority}/5 interested and currently {game.status.lower()}."
    if mode == "something_new":
        return f"Priority {game.priority}/5, currently {game.status.lower()}."


# --- Quiz-based recommendation logic ---
# This powers the "what should I play?" chat-style flow: the user picks a
# session length and a genre, and we score/filter the backlog against that.

def score_quiz(game):
    """Same idea as score_resume/score_something_new, just not tied to one
    specific mode — this scores ANY game generically, since the quiz can
    surface games in any status (except Dropped, which we filter out
    entirely before scoring)."""
    score = 0
    score += game.priority * 3
    if game.status == "Playing":
        score += 8
    elif game.status == "Paused":
        score += 6
    elif game.status == "Not Started":
        score += 4
    # Finished games intentionally get no bonus — nothing wrong with them
    # showing up, but we don't want to actively push someone back into a
    # game they already completed.
    return score


def get_quiz_reason(game, session_length, genre, relaxed_filters):
    """Builds a natural-sounding sentence explaining the pick. `relaxed_filters`
    is a list of which filters we had to drop (e.g. ["genre"]) because
    nothing matched all of them — this keeps the response honest instead of
    pretending it was a perfect match."""
    session_labels = {
        "quick": "a quick session",
        "medium": "a medium-length session",
        "long": "a longer session",
    }
    session_phrase = session_labels.get(session_length, "your session")

    if not relaxed_filters:
        return (
            f"{game.title} is a good fit for {session_phrase} — "
            f"it's tagged {game.genre} and you're currently {game.status.lower()}."
        )

    if "genre" in relaxed_filters:
        return (
            f"Nothing in your backlog matched {genre} exactly for {session_phrase}, "
            f"so here's the next best fit: {game.title} ({game.genre}), currently {game.status.lower()}."
        )

    if "session_length" in relaxed_filters:
        return (
            f"Nothing was tagged for {session_phrase} specifically, "
            f"but {game.title} ({game.genre}) matches your mood and you're currently {game.status.lower()}."
        )

    return f"{game.title} seemed like the best overall fit from your backlog."