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