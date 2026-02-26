from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import List
import random

app = FastAPI(title="🎮 Whack-a-Mole Game API", version="1.0.0")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class ScoreSubmit(BaseModel):
    name: str
    score: int
    level: int = 1

class ScoreRecord(BaseModel):
    name: str
    score: int
    level: int
    timestamp: str
    rank: int = 0

# --- In-memory storage ---
scores_db: List[dict] = [
    {"name": "🐱 Kitty", "score": 120, "level": 3, "timestamp": "2026-02-26T00:00:00"},
    {"name": "🐶 Doggo", "score": 95, "level": 2, "timestamp": "2026-02-26T00:01:00"},
    {"name": "🐰 Bunny", "score": 80, "level": 2, "timestamp": "2026-02-26T00:02:00"},
    {"name": "🦊 Foxy", "score": 65, "level": 1, "timestamp": "2026-02-26T00:03:00"},
    {"name": "🐼 Panda", "score": 50, "level": 1, "timestamp": "2026-02-26T00:04:00"},
]

ENCOURAGEMENTS = [
    "Amazing! 🎉", "You're on fire! 🔥", "Incredible! ⭐",
    "Mole master! 🏆", "Keep smashing! 💪", "Unstoppable! 🚀",
]

# --- Routes ---
@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "service": "whack-a-mole-api",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/api/scores")
def get_scores():
    sorted_scores = sorted(scores_db, key=lambda x: x["score"], reverse=True)[:10]
    result = []
    for i, s in enumerate(sorted_scores):
        result.append(ScoreRecord(
            name=s["name"], score=s["score"], level=s["level"],
            timestamp=s["timestamp"], rank=i + 1,
        ))
    return {"leaderboard": result, "total_players": len(scores_db)}

@app.post("/api/scores")
def submit_score(entry: ScoreSubmit):
    record = {
        "name": entry.name,
        "score": entry.score,
        "level": entry.level,
        "timestamp": datetime.now().isoformat(),
    }
    scores_db.append(record)
    sorted_scores = sorted(scores_db, key=lambda x: x["score"], reverse=True)
    rank = next(i + 1 for i, s in enumerate(sorted_scores) if s["timestamp"] == record["timestamp"] and s["name"] == record["name"])
    return {
        "message": random.choice(ENCOURAGEMENTS),
        "rank": rank,
        "total_players": len(scores_db),
    }

@app.get("/api/game/config")
def game_config():
    return {
        "game_duration": 30,
        "grid_size": 9,
        "mole_show_min_ms": 600,
        "mole_show_max_ms": 1200,
        "mole_interval_min_ms": 400,
        "mole_interval_max_ms": 900,
        "points_per_hit": 10,
        "bonus_per_streak": 5,
        "streak_threshold": 3,
    }
