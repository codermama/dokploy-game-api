from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import List, Optional
from contextlib import asynccontextmanager
import random
import os
import html
import asyncpg

# ─── Database ───────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")

pool: Optional[asyncpg.Pool] = None

async def init_db():
    global pool
    if not DATABASE_URL:
        print("⚠️  DATABASE_URL not set, running in memory-only mode")
        return
    try:
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS scores (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(50) NOT NULL,
                    score INTEGER NOT NULL DEFAULT 0,
                    level INTEGER NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            # Seed data if empty
            count = await conn.fetchval("SELECT COUNT(*) FROM scores")
            if count == 0:
                seeds = [
                    ("🐱 Kitty", 120, 3), ("🐶 Doggo", 95, 2),
                    ("🐰 Bunny", 80, 2), ("🦊 Foxy", 65, 1), ("🐼 Panda", 50, 1),
                ]
                for name, score, level in seeds:
                    await conn.execute(
                        "INSERT INTO scores (name, score, level) VALUES ($1, $2, $3)",
                        name, score, level
                    )
        print("✅ Database connected and initialized")
    except Exception as e:
        print(f"❌ Database connection failed: {e}, falling back to memory mode")

async def close_db():
    global pool
    if pool:
        await pool.close()

# ─── In-memory fallback ─────────────────────────────
memory_scores: List[dict] = [
    {"name": "🐱 Kitty", "score": 120, "level": 3, "timestamp": "2026-02-26T00:00:00"},
    {"name": "🐶 Doggo", "score": 95, "level": 2, "timestamp": "2026-02-26T00:01:00"},
    {"name": "🐰 Bunny", "score": 80, "level": 2, "timestamp": "2026-02-26T00:02:00"},
    {"name": "🦊 Foxy", "score": 65, "level": 1, "timestamp": "2026-02-26T00:03:00"},
    {"name": "🐼 Panda", "score": 50, "level": 1, "timestamp": "2026-02-26T00:04:00"},
]

# ─── Lifespan ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

# ─── App ────────────────────────────────────────────
app = FastAPI(title="🎮 Whack-a-Mole Game API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Models ─────────────────────────────────────────
class ScoreSubmit(BaseModel):
    name: str
    score: int
    level: int = 1

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = html.escape(v.strip())
        if not v or len(v) > 50:
            raise ValueError("Name must be 1-50 characters")
        return v

    @field_validator("score")
    @classmethod
    def validate_score(cls, v: int) -> int:
        if v < 0 or v > 99999:
            raise ValueError("Score must be between 0 and 99999")
        return v

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("Level must be between 1 and 100")
        return v

class ScoreRecord(BaseModel):
    name: str
    score: int
    level: int
    timestamp: str
    rank: int = 0

ENCOURAGEMENTS = [
    "Amazing! 🎉", "You're on fire! 🔥", "Incredible! ⭐",
    "Mole master! 🏆", "Keep smashing! 💪", "Unstoppable! 🚀",
]

# ─── Routes ─────────────────────────────────────────
@app.get("/api/health")
async def health():
    db_status = "connected" if pool else "memory-only"
    return {
        "status": "healthy",
        "service": "whack-a-mole-api",
        "version": "2.0.0",
        "database": db_status,
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/api/scores")
async def get_scores():
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT name, score, level, created_at FROM scores ORDER BY score DESC LIMIT 10"
            )
            leaderboard = [
                ScoreRecord(
                    name=r["name"], score=r["score"], level=r["level"],
                    timestamp=r["created_at"].isoformat(), rank=i + 1
                ) for i, r in enumerate(rows)
            ]
            total = await conn.fetchval("SELECT COUNT(*) FROM scores")
        return {"leaderboard": leaderboard, "total_players": total}
    else:
        sorted_scores = sorted(memory_scores, key=lambda x: x["score"], reverse=True)[:10]
        leaderboard = [
            ScoreRecord(name=s["name"], score=s["score"], level=s["level"],
                        timestamp=s["timestamp"], rank=i + 1)
            for i, s in enumerate(sorted_scores)
        ]
        return {"leaderboard": leaderboard, "total_players": len(memory_scores)}

@app.post("/api/scores")
async def submit_score(entry: ScoreSubmit):
    now = datetime.now()
    if pool:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO scores (name, score, level, created_at) VALUES ($1, $2, $3, $4)",
                entry.name, entry.score, entry.level, now
            )
            rank = await conn.fetchval(
                "SELECT COUNT(*) FROM scores WHERE score > $1", entry.score
            ) + 1
            total = await conn.fetchval("SELECT COUNT(*) FROM scores")
    else:
        record = {"name": entry.name, "score": entry.score, "level": entry.level, "timestamp": now.isoformat()}
        memory_scores.append(record)
        sorted_scores = sorted(memory_scores, key=lambda x: x["score"], reverse=True)
        rank = next(i + 1 for i, s in enumerate(sorted_scores) if s["name"] == entry.name and s["timestamp"] == record["timestamp"])
        total = len(memory_scores)

    return {
        "message": random.choice(ENCOURAGEMENTS),
        "rank": rank,
        "total_players": total,
    }

@app.get("/api/game/config")
async def game_config():
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


@app.get("/api/stats")
async def get_stats():
    """Return aggregate game statistics."""
    if pool:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    COUNT(*)        AS total_games,
                    MAX(score)      AS highest_score,
                    ROUND(AVG(score)) AS avg_score,
                    COUNT(DISTINCT name) AS total_players
                FROM scores
            """)
            return {
                "total_games": row["total_games"],
                "highest_score": row["highest_score"] or 0,
                "avg_score": int(row["avg_score"] or 0),
                "total_players": row["total_players"],
            }
    else:
        names = {s["name"] for s in memory_scores}
        scores_list = [s["score"] for s in memory_scores]
        return {
            "total_games": len(memory_scores),
            "highest_score": max(scores_list) if scores_list else 0,
            "avg_score": int(sum(scores_list) / len(scores_list)) if scores_list else 0,
            "total_players": len(names),
        }


@app.get("/api/scores/recent")
async def get_recent_scores():
    """Return the 5 most recent score submissions for live feed."""
    if pool:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT name, score, level, created_at FROM scores ORDER BY created_at DESC LIMIT 5"
            )
            return {
                "recent": [
                    {
                        "name": r["name"],
                        "score": r["score"],
                        "level": r["level"],
                        "timestamp": r["created_at"].isoformat(),
                    }
                    for r in rows
                ]
            }
    else:
        recent = sorted(memory_scores, key=lambda x: x["timestamp"], reverse=True)[:5]
        return {"recent": recent}
