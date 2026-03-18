import sqlite3
import os
import logging
from datetime import datetime

log = logging.getLogger("walle.db")

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "../data/walle.db"))


class Database:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self.path = DB_PATH

    def get_conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self):
        with self.get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS picks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    player_name TEXT NOT NULL,
                    team TEXT,
                    opponent TEXT,
                    stat_type TEXT NOT NULL,
                    line REAL NOT NULL,
                    direction TEXT NOT NULL,
                    true_prob REAL,
                    book_prob REAL,
                    ev REAL,
                    grade_label TEXT,
                    grade_score INTEGER,
                    confidence TEXT,
                    reasoning TEXT,
                    watch_out TEXT,
                    knowledge_flag TEXT,
                    platform TEXT,
                    result TEXT DEFAULT NULL,
                    actual_value REAL DEFAULT NULL,
                    date TEXT NOT NULL,
                    parlay_id TEXT DEFAULT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS parlays (
                    id TEXT PRIMARY KEY,
                    legs INTEGER,
                    overall_grade TEXT,
                    overall_result TEXT DEFAULT NULL,
                    date TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        log.info(f"Database initialized at {self.path}")

    def save_pick(self, pick: dict) -> int:
        with self.get_conn() as conn:
            cur = conn.execute("""
                INSERT INTO picks (
                    player_name, team, opponent, stat_type, line, direction,
                    true_prob, book_prob, ev, grade_label, grade_score,
                    confidence, reasoning, watch_out, knowledge_flag,
                    platform, date, parlay_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pick.get("player_name"), pick.get("team"), pick.get("opponent"),
                pick.get("stat_type"), pick.get("line"), pick.get("direction"),
                pick.get("true_prob"), pick.get("book_prob"), pick.get("ev"),
                pick.get("grade_label"), pick.get("grade_score"),
                pick.get("confidence"), pick.get("reasoning"), pick.get("watch_out"),
                pick.get("knowledge_flag"), pick.get("platform"),
                pick.get("date", datetime.now().strftime("%Y-%m-%d")),
                pick.get("parlay_id")
            ))
            conn.commit()
            return cur.lastrowid

    def save_parlay(self, parlay_id: str, legs: int, overall_grade: str = None):
        with self.get_conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO parlays (id, legs, overall_grade, date)
                VALUES (?, ?, ?, ?)
            """, (parlay_id, legs, overall_grade, datetime.now().strftime("%Y-%m-%d")))
            conn.commit()

    def update_result(self, pick_id: int, result: str, actual_value: float = None):
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE picks SET result = ?, actual_value = ? WHERE id = ?",
                (result, actual_value, pick_id)
            )
            conn.commit()
        log.info(f"Pick #{pick_id} updated: {result} (actual: {actual_value})")

    def get_intelligence_report(self) -> dict:
        with self.get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM picks WHERE result IN ('win','loss')"
            ).fetchone()[0]
            wins = conn.execute(
                "SELECT COUNT(*) FROM picks WHERE result = 'win'"
            ).fetchone()[0]

            elite = conn.execute("""
                SELECT COUNT(*), SUM(CASE WHEN result='win' THEN 1 ELSE 0 END)
                FROM picks WHERE grade_label LIKE '%Elite%' AND result IN ('win','loss')
            """).fetchone()

            good = conn.execute("""
                SELECT COUNT(*), SUM(CASE WHEN result='win' THEN 1 ELSE 0 END)
                FROM picks WHERE grade_label LIKE '%Good%' AND result IN ('win','loss')
            """).fetchone()

            stat_rates = conn.execute("""
                SELECT stat_type,
                       COUNT(*) as cnt,
                       ROUND(AVG(CASE WHEN result='win' THEN 1.0 ELSE 0.0 END)*100) as win_pct
                FROM picks
                WHERE result IN ('win','loss')
                GROUP BY stat_type
                HAVING cnt >= 3
                ORDER BY win_pct DESC
                LIMIT 5
            """).fetchall()

            top_players = conn.execute("""
                SELECT player_name,
                       COUNT(*) as cnt,
                       ROUND(AVG(CASE WHEN result='win' THEN 1.0 ELSE 0.0 END)*100) as win_pct
                FROM picks
                WHERE result IN ('win','loss')
                GROUP BY player_name
                ORDER BY cnt DESC
                LIMIT 5
            """).fetchall()

            total_analyzed = conn.execute("SELECT COUNT(*) FROM picks").fetchone()[0]

            return {
                "total": total,
                "wins": wins,
                "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
                "elite_total": elite[0] or 0,
                "elite_wins": elite[1] or 0,
                "elite_rate": round((elite[1] or 0) / elite[0] * 100) if elite[0] else 0,
                "good_total": good[0] or 0,
                "good_wins": good[1] or 0,
                "good_rate": round((good[1] or 0) / good[0] * 100) if good[0] else 0,
                "stat_rates": [dict(r) for r in stat_rates],
                "top_players": [dict(r) for r in top_players],
                "total_analyzed": total_analyzed,
            }

    def get_pending_picks(self) -> list:
        with self.get_conn() as conn:
            rows = conn.execute("""
                SELECT id, player_name, stat_type, line, direction, grade_label, platform, date
                FROM picks WHERE result IS NULL
                ORDER BY created_at DESC LIMIT 25
            """).fetchall()
            return [dict(r) for r in rows]
