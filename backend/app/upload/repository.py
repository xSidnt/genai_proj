import sqlite3
from pathlib import Path


class UploadRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_table()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _create_table(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS upload_jobs (
                    id TEXT PRIMARY KEY,
                    original_name TEXT NOT NULL,
                    video_path TEXT NOT NULL,
                    audio_path TEXT NOT NULL,
                    duration_seconds REAL NOT NULL,
                    width INTEGER,
                    height INTEGER,
                    frame_rate REAL,
                    status TEXT NOT NULL
                )
                """
            )

    def create(
        self,
        *,
        job_id: str,
        original_name: str,
        video_path: str,
        audio_path: str,
        duration_seconds: float,
        width: int | None,
        height: int | None,
        frame_rate: float | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO upload_jobs
                (id, original_name, video_path, audio_path, duration_seconds,
                 width, height, frame_rate, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    original_name,
                    video_path,
                    audio_path,
                    duration_seconds,
                    width,
                    height,
                    frame_rate,
                    "ready",
                ),
            )
