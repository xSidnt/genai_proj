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
            legacy_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(transcription_results)")
            }
            needs_migration = bool(legacy_columns) and (
                "start_seconds" not in legacy_columns
                or "end_seconds" not in legacy_columns
                or "video_observations_json" not in legacy_columns
            )

            if needs_migration:
                connection.execute("ALTER TABLE transcription_results RENAME TO transcription_results_legacy")

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS transcription_results (
                    job_id TEXT NOT NULL,
                    start_seconds REAL NOT NULL DEFAULT 0,
                    end_seconds REAL NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    tuning TEXT NOT NULL,
                    tempo_bpm INTEGER,
                    notes_json TEXT NOT NULL,
                    audio_source TEXT NOT NULL DEFAULT 'original',
                    video_observations_json TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY (job_id, start_seconds, end_seconds)
                )
                """
            )

            if needs_migration:
                required = {"job_id", "status", "tuning", "tempo_bpm", "notes_json", "audio_source"}
                if required.issubset(legacy_columns):
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO transcription_results
                        (job_id, start_seconds, end_seconds, status, tuning, tempo_bpm,
                         notes_json, audio_source, video_observations_json)
                        SELECT job_id, 0, 0, status, tuning, tempo_bpm,
                               notes_json, audio_source, '[]'
                        FROM transcription_results_legacy
                        """
                    )
                connection.execute("DROP TABLE transcription_results_legacy")

    def get_upload_media(self, job_id: str) -> tuple[str, str, float] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT audio_path, video_path, duration_seconds FROM upload_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        return (row[0], row[1], float(row[2])) if row else None

    def save(
        self,
        *,
        job_id: str,
        start_seconds: float,
        end_seconds: float,
        status: str,
        tuning: list[str],
        tempo_bpm: int | None,
        notes: list[dict],
        audio_source: str,
        video_observations: list[dict],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO transcription_results
                (job_id, start_seconds, end_seconds, status, tuning, tempo_bpm,
                 notes_json, audio_source, video_observations_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id, start_seconds, end_seconds) DO UPDATE SET
                    status = excluded.status,
                    tuning = excluded.tuning,
                    tempo_bpm = excluded.tempo_bpm,
                    notes_json = excluded.notes_json,
                    audio_source = excluded.audio_source,
                    video_observations_json = excluded.video_observations_json
                """,
                (
                    job_id,
                    round(start_seconds, 3),
                    round(end_seconds, 3),
                    status,
                    json.dumps(tuning),
                    tempo_bpm,
                    json.dumps(notes),
                    audio_source,
                    json.dumps(video_observations),
                ),
            )

    def get(self, job_id: str, start_seconds: float, end_seconds: float) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT status, tuning, tempo_bpm, notes_json, audio_source,
                       video_observations_json
                FROM transcription_results
                WHERE job_id = ? AND start_seconds = ? AND end_seconds = ?
                """,
                (job_id, round(start_seconds, 3), round(end_seconds, 3)),
            ).fetchone()

        if not row:
            return None

        return {
            "status": row[0],
            "tuning": json.loads(row[1]),
            "tempo_bpm": row[2],
            "notes": json.loads(row[3]),
            "audio_source": row[4],
            "video_observations": json.loads(row[5]),
        }
