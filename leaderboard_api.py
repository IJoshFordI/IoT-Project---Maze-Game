"""Persistent score API for the Arcade Maze leaderboard."""

import os
import unicodedata

import psycopg
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from psycopg.rows import dict_row


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024
CORS(app, resources={r"/api/*": {"origins": "*"}})
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "30 per minute"],
    storage_uri="memory://",
)


def database_url():
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is not configured.")
    return value


def create_scores_table(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS maze_score_runs (
            id BIGSERIAL PRIMARY KEY,
            player_key TEXT NOT NULL,
            player_name VARCHAR(16) NOT NULL,
            score INTEGER NOT NULL CHECK (score >= 0),
            level SMALLINT NOT NULL DEFAULT 5,
            completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS maze_score_runs_completed_idx "
        "ON maze_score_runs (completed_at DESC)"
    )


@app.get("/healthz")
def health():
    return jsonify(status="ok", service="arcade-maze-leaderboard")


@app.get("/api/leaderboard")
def get_leaderboard():
    period = request.args.get("period", "all").lower()
    if period not in {"all", "week"}:
        return jsonify(error="Use period=all or period=week."), 400

    date_filter = "WHERE completed_at >= NOW() - INTERVAL '7 days'" if period == "week" else ""
    query = f"""
        SELECT player_name, score, level, completed_at
        FROM (
            SELECT DISTINCT ON (player_key)
                player_key, player_name, score, level, completed_at
            FROM maze_score_runs
            {date_filter}
            ORDER BY player_key, score DESC, completed_at DESC
        ) AS best_runs
        ORDER BY score DESC, completed_at ASC
        LIMIT 100
    """

    try:
        with psycopg.connect(database_url(), connect_timeout=5, row_factory=dict_row) as connection:
            create_scores_table(connection)
            rows = connection.execute(query).fetchall()
        entries = [
            {
                "rank": rank,
                "name": row["player_name"],
                "score": row["score"],
                "level": row["level"],
                "completed_at": row["completed_at"].isoformat(),
            }
            for rank, row in enumerate(rows, start=1)
        ]
        return jsonify(entries=entries, period=period)
    except (psycopg.Error, RuntimeError):
        app.logger.exception("Unable to load leaderboard")
        return jsonify(error="Leaderboard storage is unavailable."), 503


@app.post("/api/scores")
@limiter.limit("10 per minute")
def save_score():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify(error="Send a JSON object."), 400

    raw_name = body.get("name")
    raw_score = body.get("score")
    if not isinstance(raw_name, str):
        return jsonify(error="Name must be text."), 400

    name = " ".join(unicodedata.normalize("NFKC", raw_name).split())
    if not name or len(name) > 16:
        return jsonify(error="Name must be between 1 and 16 characters."), 400
    if isinstance(raw_score, bool) or not isinstance(raw_score, int) or not 0 <= raw_score <= 1_000_000:
        return jsonify(error="Score must be a whole number between 0 and 1,000,000."), 400

    player_key = name.casefold()
    try:
        with psycopg.connect(database_url(), connect_timeout=5, row_factory=dict_row) as connection:
            create_scores_table(connection)
            row = connection.execute(
                """
                INSERT INTO maze_score_runs (player_key, player_name, score)
                VALUES (%s, %s, %s)
                RETURNING player_name, score, level, completed_at
                """,
                (player_key, name, raw_score),
            ).fetchone()
        return jsonify(
            saved=True,
            entry={
                "name": row["player_name"],
                "score": row["score"],
                "level": row["level"],
                "completed_at": row["completed_at"].isoformat(),
            },
        ), 201
    except (psycopg.Error, RuntimeError):
        app.logger.exception("Unable to save completed game score")
        return jsonify(error="Score could not be saved. Please try again later."), 503
