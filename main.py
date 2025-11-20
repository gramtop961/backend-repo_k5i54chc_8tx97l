import os
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from bson import ObjectId

from database import (
    db,
    create_document,
    get_documents,
    get_document_by_id,
    find_one,
    update_document,
    increment_field,
)
from schemas import PupfiUser, Game, Match, Leaderboard, Quest, Claim, Transaction

app = FastAPI(title="Pupfi Arcade API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"name": "Pupfi Arcade", "status": "ok"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected"
            response["database_url"] = "✅ Set"
            response["database_name"] = getattr(db, 'name', 'unknown')
            try:
                response["collections"] = db.list_collection_names()[:10]
            except Exception as e:
                response["collections"] = [f"error: {str(e)[:50]}"]
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


# -------- Users --------
class CreateUser(BaseModel):
    username: str
    display_name: Optional[str] = None


@app.post("/users", response_model=dict)
def create_user(data: CreateUser):
    existing = find_one("pupfiuser", {"username": data.username})
    if existing:
        return existing
    user = PupfiUser(username=data.username, display_name=data.display_name)
    user_id = create_document("pupfiuser", user)
    return get_document_by_id("pupfiuser", user_id)  # type: ignore


@app.get("/users/{user_id}")
def get_user(user_id: str):
    doc = get_document_by_id("pupfiuser", user_id)
    if not doc:
        raise HTTPException(404, "User not found")
    return doc


@app.post("/users/{user_id}/earn")
def earn_tokens(user_id: str, amount: int, reason: str = "game_reward"):
    if amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    updated = increment_field("pupfiuser", user_id, {"balance": amount, "xp": amount})
    if not updated:
        raise HTTPException(404, "User not found")
    create_document("transaction", Transaction(user_id=user_id, amount=amount, type="earn", reason=reason))
    return updated


@app.post("/users/{user_id}/spend")
def spend_tokens(user_id: str, amount: int, reason: str = "entry_fee"):
    if amount <= 0:
        raise HTTPException(400, "Amount must be positive")
    user = get_document_by_id("pupfiuser", user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.get("balance", 0) < amount:
        raise HTTPException(400, "Insufficient balance")
    updated = increment_field("pupfiuser", user_id, {"balance": -amount})
    create_document("transaction", Transaction(user_id=user_id, amount=-amount, type="spend", reason=reason))
    return updated


@app.get("/leaderboard/{game_key}")
def leaderboard(game_key: str, limit: int = 50):
    docs = get_documents("leaderboard", {"game_key": game_key}, limit)
    # sort by score desc
    docs.sort(key=lambda x: x.get("score", 0), reverse=True)
    return docs


# -------- Games & Matches --------
@app.get("/games")
def list_games():
    return [
        {
            "key": "pup-run",
            "name": "Pup Run",
            "description": "Reflex mini-game: click at the right time to sprint",
            "max_players": 2
        },
        {
            "key": "pup-pairs",
            "name": "Pup Pairs",
            "description": "Memory match against a friend",
            "max_players": 2
        },
        {
            "key": "pup-drift",
            "name": "Pup Drift",
            "description": "Timing-based drift around corners",
            "max_players": 4
        }
    ]


class CreateMatch(BaseModel):
    game_key: str
    creator_id: str
    entry_fee: int = 0
    seed: int = 0


@app.post("/matches")
def create_match(data: CreateMatch):
    # optional entry fee
    if data.entry_fee > 0:
        spend_tokens(data.creator_id, data.entry_fee, reason="match_entry")
    m = Match(
        game_key=data.game_key,
        creator_id=data.creator_id,
        status="waiting",
        players=[data.creator_id],
        reward=int(data.entry_fee * 1.8) if data.entry_fee else 0,
        seed=data.seed,
    )
    match_id = create_document("match", m)
    return get_document_by_id("match", match_id)


@app.post("/matches/{match_id}/join")
def join_match(match_id: str, user_id: str):
    match = get_document_by_id("match", match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    if match["status"] != "waiting":
        raise HTTPException(400, "Match already started")
    if user_id in match["players"]:
        return match
    if len(match["players"]) >= match.get("max_players", 2):
        # fallback to game preset
        pass
    update = update_document("match", match_id, {"players": match["players"] + [user_id]})
    return update


class SubmitScore(BaseModel):
    user_id: str
    score: int


@app.post("/matches/{match_id}/score")
def submit_score(match_id: str, payload: SubmitScore):
    match = get_document_by_id("match", match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    if payload.user_id not in match.get("players", []):
        raise HTTPException(403, "Not in match")
    scores = match.get("scores", {})
    scores[payload.user_id] = max(scores.get(payload.user_id, 0), payload.score)
    update = update_document("match", match_id, {"scores": scores})
    return update


@app.post("/matches/{match_id}/finish")
def finish_match(match_id: str):
    match = get_document_by_id("match", match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    if match.get("status") == "finished":
        return match
    # determine winner
    scores: Dict[str, int] = match.get("scores", {})
    if not scores:
        update = update_document("match", match_id, {"status": "finished"})
        return update
    winner_id = max(scores.items(), key=lambda x: x[1])[0]
    update = update_document("match", match_id, {"status": "finished", "winner_id": winner_id})
    # payout
    reward = match.get("reward", 0)
    if reward > 0:
        increment_field("pupfiuser", winner_id, {"balance": reward, "xp": reward})
        create_document("transaction", Transaction(user_id=winner_id, amount=reward, type="earn", reason="match_win"))
    # leaderboard update
    create_document("leaderboard", Leaderboard(game_key=match["game_key"], user_id=winner_id, score=scores[winner_id], username=""))
    return update


# -------- Quests & Rewards --------
@app.get("/quests")
def list_quests():
    # static plus database-defined
    static = [
        {"key": "daily-login", "title": "Daily Login", "description": "Open the app", "reward": 5, "type": "daily"},
        {"key": "first-win", "title": "First Victory", "description": "Win a match", "reward": 25, "type": "special"},
    ]
    db_quests = get_documents("quest")
    return static + db_quests


@app.post("/quests/{key}/claim")
def claim_quest(key: str, user_id: str):
    # prevent duplicate claim for daily
    today = datetime.utcnow().date().isoformat()
    existing = find_one("claim", {"user_id": user_id, "quest_key": f"{key}:{today}"})
    if existing:
        raise HTTPException(400, "Already claimed today")
    reward = 5 if key == "daily-login" else 25
    create_document("claim", {"user_id": user_id, "quest_key": f"{key}:{today}", "claimed_at": datetime.utcnow()})
    increment_field("pupfiuser", user_id, {"balance": reward, "xp": reward})
    create_document("transaction", Transaction(user_id=user_id, amount=reward, type="earn", reason=f"quest:{key}"))
    return {"ok": True, "reward": reward}


# -------- Utility --------
@app.get("/schema")
def schema_info():
    # Expose schema names for admin tools
    return {
        "collections": ["pupfiuser", "game", "match", "leaderboard", "quest", "claim", "transaction"]
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
