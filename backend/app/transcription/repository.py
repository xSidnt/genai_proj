import sqlite3
import json
from pathlib import Path


class TranscriptionRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_tables()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _create_tables(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transcription_results (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    tuning TEXT NOT NULL,
                    tempo_bpm INTEGER,
                    notes_json TEXT NOT NULL,
                    audio_source TEXT NOT NULL DEFAULT 'original'
                )
                """
            )
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(transcription_results)")
            }
            if "audio_source" not in columns:
                connection.execute(
                    "ALTER TABLE transcription_results "
                    "ADD COLUMN audio_source TEXT NOT NULL DEFAULT 'original'"
                )

    def get_upload_audio_path(self, job_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT audio_path FROM upload_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        return row[0] if row else None

    def save(
        self,
        *,
        job_id: str,
        status: str,
        tuning: list[str],
        tempo_bpm: int | None,
        notes: list[dict],
        audio_source: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO transcription_results
                (job_id, status, tuning, tempo_bpm, notes_json, audio_source)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status = excluded.status,
                    tuning = excluded.tuning,
                    tempo_bpm = excluded.tempo_bpm,
                    notes_json = excluded.notes_json,
                    audio_source = excluded.audio_source
                """,
                (
                    job_id,
                    status,
                    json.dumps(tuning),
                    tempo_bpm,
                    json.dumps(notes),
                    audio_source,
                ),
            )

    def get(self, job_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT status, tuning, tempo_bpm, notes_json, audio_source
                FROM transcription_results WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if not row:
            return None

        return {
            "status": row[0],
            "tuning": json.loads(row[1]),
            "tempo_bpm": row[2],
            "notes": json.loads(row[3]),
            "audio_source": row[4],
        }
