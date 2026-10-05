from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from .duplicates import identity_key, normalize_url
from .models import AlertRecord
from .timeutil import now_colombia, today_colombia


class AlertRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    identity_key TEXT NOT NULL,
                    alert_url TEXT NOT NULL DEFAULT '',
                    listing_url TEXT NOT NULL DEFAULT '',
                    pdf_url TEXT NOT NULL DEFAULT '',
                    alert_date TEXT,
                    review_date TEXT,
                    code TEXT NOT NULL DEFAULT '',
                    document_type TEXT NOT NULL DEFAULT '',
                    surveillance_type TEXT NOT NULL DEFAULT '',
                    classification TEXT NOT NULL DEFAULT '',
                    classification_confidence TEXT NOT NULL DEFAULT 'pending',
                    source_category TEXT NOT NULL DEFAULT '',
                    product_name TEXT NOT NULL DEFAULT '',
                    registry TEXT NOT NULL DEFAULT '',
                    internal_file_number TEXT NOT NULL DEFAULT '',
                    presentation TEXT NOT NULL DEFAULT '',
                    holder TEXT NOT NULL DEFAULT '',
                    manufacturer_importer TEXT NOT NULL DEFAULT '',
                    reference_code TEXT NOT NULL DEFAULT '',
                    lot_serial TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    indication_use TEXT NOT NULL DEFAULT '',
                    extracted_text TEXT NOT NULL DEFAULT '',
                    pdf_path TEXT NOT NULL DEFAULT '',
                    downloaded_at TEXT,
                    document_hash TEXT NOT NULL DEFAULT '',
                    duplicate_status TEXT NOT NULL DEFAULT 'new',
                    duplicate_of INTEGER REFERENCES alerts(id),
                    status TEXT NOT NULL DEFAULT 'discovered',
                    last_error TEXT NOT NULL DEFAULT '',
                    matrix_synced INTEGER NOT NULL DEFAULT 0,
                    matrix_row INTEGER,
                    last_seen_run_id INTEGER,
                    portal_presence TEXT NOT NULL DEFAULT 'unknown',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_alerts_pdf_url ON alerts(pdf_url);
                CREATE INDEX IF NOT EXISTS idx_alerts_alert_url ON alerts(alert_url);
                CREATE INDEX IF NOT EXISTS idx_alerts_document_hash ON alerts(document_hash);
                CREATE INDEX IF NOT EXISTS idx_alerts_code_date ON alerts(code, alert_date);
                CREATE INDEX IF NOT EXISTS idx_alerts_matrix ON alerts(matrix_synced, duplicate_status);

                CREATE TABLE IF NOT EXISTS update_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    start_date TEXT NOT NULL,
                    pages_scanned INTEGER NOT NULL DEFAULT 0,
                    alerts_found INTEGER NOT NULL DEFAULT 0,
                    alerts_new INTEGER NOT NULL DEFAULT 0,
                    alerts_existing INTEGER NOT NULL DEFAULT 0,
                    pdf_downloaded INTEGER NOT NULL DEFAULT 0,
                    pdf_reused INTEGER NOT NULL DEFAULT 0,
                    matrix_added INTEGER NOT NULL DEFAULT 0,
                    errors INTEGER NOT NULL DEFAULT 0,
                    scan_complete INTEGER NOT NULL DEFAULT 0,
                    alerts_not_seen INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'running',
                    summary TEXT NOT NULL DEFAULT ''
                );
                """
            )
            alert_columns = {row[1] for row in db.execute("PRAGMA table_info(alerts)")}
            if "last_seen_run_id" not in alert_columns:
                db.execute("ALTER TABLE alerts ADD COLUMN last_seen_run_id INTEGER")
            if "portal_presence" not in alert_columns:
                db.execute("ALTER TABLE alerts ADD COLUMN portal_presence TEXT NOT NULL DEFAULT 'unknown'")
            run_columns = {row[1] for row in db.execute("PRAGMA table_info(update_runs)")}
            if "scan_complete" not in run_columns:
                db.execute("ALTER TABLE update_runs ADD COLUMN scan_complete INTEGER NOT NULL DEFAULT 0")
            if "alerts_not_seen" not in run_columns:
                db.execute("ALTER TABLE update_runs ADD COLUMN alerts_not_seen INTEGER NOT NULL DEFAULT 0")

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)

    def create_run(self, start_date: date) -> int:
        now = now_colombia().isoformat(timespec="seconds")
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO update_runs(started_at, start_date) VALUES(?, ?)",
                (now, start_date.isoformat()),
            )
            return int(cursor.lastrowid)

    def finish_run(self, run_id: int, **values: Any) -> None:
        allowed = {
            "finished_at", "pages_scanned", "alerts_found", "alerts_new", "alerts_existing",
            "pdf_downloaded", "pdf_reused", "matrix_added", "errors", "scan_complete", "alerts_not_seen", "status", "summary",
        }
        values = {key: value for key, value in values.items() if key in allowed}
        values.setdefault("finished_at", now_colombia().isoformat(timespec="seconds"))
        assignments = ", ".join(f"{key} = ?" for key in values)
        with self._connect() as db:
            db.execute(f"UPDATE update_runs SET {assignments} WHERE id = ?", (*values.values(), run_id))

    def latest_run(self) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM update_runs ORDER BY id DESC LIMIT 1").fetchone()
            return self._row_to_dict(row) if row else None

    def find_by_pdf_url(self, url: str) -> dict[str, Any] | None:
        rows = self.find_all_by_pdf_url(url)
        return rows[0] if rows else None

    def find_all_by_pdf_url(self, url: str) -> list[dict[str, Any]]:
        normalized = normalize_url(url)
        if not normalized:
            return []
        with self._connect() as db:
            exact = db.execute("SELECT * FROM alerts WHERE pdf_url = ? ORDER BY id", (url,)).fetchall()
            if exact:
                return [self._row_to_dict(row) for row in exact]
            rows = db.execute("SELECT * FROM alerts WHERE pdf_url <> '' ORDER BY id").fetchall()
        matches = []
        for row in rows:
            if normalize_url(row["pdf_url"]) == normalized:
                matches.append(self._row_to_dict(row))
        return matches

    def find_by_alert_url(self, url: str) -> dict[str, Any] | None:
        normalized = normalize_url(url)
        if not normalized:
            return None
        with self._connect() as db:
            rows = db.execute("SELECT * FROM alerts WHERE alert_url <> '' ORDER BY id").fetchall()
        for row in rows:
            if normalize_url(row["alert_url"]) == normalized:
                return self._row_to_dict(row)
        return None

    def find_by_hash(self, document_hash: str) -> dict[str, Any] | None:
        if not document_hash:
            return None
        with self._connect() as db:
            row = db.execute("SELECT * FROM alerts WHERE document_hash = ? ORDER BY id LIMIT 1", (document_hash,)).fetchone()
            return self._row_to_dict(row) if row else None

    def mark_seen_urls(self, run_id: int, pdf_urls: list[str]) -> None:
        normalized_urls = {normalize_url(url) for url in pdf_urls if normalize_url(url)}
        if not normalized_urls:
            return
        now = now_colombia().isoformat(timespec="seconds")
        with self._connect() as db:
            rows = db.execute("SELECT id, pdf_url FROM alerts WHERE pdf_url <> ''").fetchall()
            ids = [row["id"] for row in rows if normalize_url(row["pdf_url"]) in normalized_urls]
            for alert_id in ids:
                db.execute(
                    "UPDATE alerts SET last_seen_run_id=?, portal_presence='visible', updated_at=? WHERE id=?",
                    (run_id, now, alert_id),
                )

    def mark_not_seen_in_run(self, run_id: int, start_date: date) -> int:
        now = now_colombia().isoformat(timespec="seconds")
        with self._connect() as db:
            cursor = db.execute(
                """UPDATE alerts SET portal_presence='not_seen', updated_at=?
                   WHERE alert_date IS NOT NULL AND alert_date >= ?
                   AND (last_seen_run_id IS NULL OR last_seen_run_id <> ?)
                   AND portal_presence <> 'not_seen'""",
                (now, start_date.isoformat(), run_id),
            )
            return cursor.rowcount

    def find_code_matches(self, code: str) -> list[dict[str, Any]]:
        if not code:
            return []
        with self._connect() as db:
            return [self._row_to_dict(row) for row in db.execute("SELECT * FROM alerts WHERE lower(code) = lower(?)", (code,))]

    def insert_candidate(self, record: AlertRecord, listing_url: str = "") -> int:
        now = now_colombia().isoformat(timespec="seconds")
        key = identity_key(record.code, record.alert_date, record.product_name, record.alert_url, record.pdf_url)
        values = (
            key, record.alert_url, listing_url, record.pdf_url,
            record.alert_date.isoformat() if record.alert_date else None,
            today_colombia().isoformat(), record.code, record.document_type, record.surveillance_type,
            record.classification, record.classification_confidence, record.source_category,
            record.product_name, record.registry, record.internal_file_number, record.presentation,
            record.holder, record.manufacturer_importer, record.reference_code, record.lot_serial,
            record.description, record.indication_use, "", record.pdf_path,
            record.downloaded_at.isoformat() if record.downloaded_at else None, record.document_hash,
            record.duplicate_status, record.duplicate_of, record.status, record.last_error,
            int(record.matrix_synced), record.matrix_row, now, now,
        )
        with self._connect() as db:
            cursor = db.execute(
                """INSERT INTO alerts(
                    identity_key, alert_url, listing_url, pdf_url, alert_date, review_date, code,
                    document_type, surveillance_type, classification, classification_confidence,
                    source_category, product_name, registry, internal_file_number, presentation,
                    holder, manufacturer_importer, reference_code, lot_serial, description, indication_use,
                    extracted_text, pdf_path, downloaded_at, document_hash, duplicate_status, duplicate_of,
                    status, last_error, matrix_synced, matrix_row, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                values,
            )
            return int(cursor.lastrowid)

    def update_alert(self, alert_id: int, record: AlertRecord, extracted_text: str = "") -> None:
        now = now_colombia().isoformat(timespec="seconds")
        key = identity_key(record.code, record.alert_date, record.product_name, record.alert_url, record.pdf_url)
        with self._connect() as db:
            db.execute(
                """UPDATE alerts SET
                    identity_key=?, alert_url=?, pdf_url=?, alert_date=?, code=?, document_type=?,
                    surveillance_type=?, classification=?, classification_confidence=?, source_category=?,
                    product_name=?, registry=?, internal_file_number=?, presentation=?, holder=?,
                    manufacturer_importer=?, reference_code=?, lot_serial=?, description=?, indication_use=?,
                    extracted_text=?, pdf_path=?, downloaded_at=?, document_hash=?, duplicate_status=?,
                    duplicate_of=?, status=?, last_error=?, matrix_synced=?, matrix_row=?, updated_at=?
                    WHERE id=?""",
                (
                    key, record.alert_url, record.pdf_url, record.alert_date.isoformat() if record.alert_date else None,
                    record.code, record.document_type, record.surveillance_type, record.classification,
                    record.classification_confidence, record.source_category, record.product_name, record.registry,
                    record.internal_file_number, record.presentation, record.holder, record.manufacturer_importer,
                    record.reference_code, record.lot_serial, record.description, record.indication_use,
                    extracted_text, record.pdf_path,
                    record.downloaded_at.isoformat() if record.downloaded_at else None, record.document_hash,
                    record.duplicate_status, record.duplicate_of, record.status, record.last_error,
                    int(record.matrix_synced), record.matrix_row, now, alert_id,
                ),
            )

    def get_alert(self, alert_id: int) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
            return self._row_to_dict(row) if row else None

    def get_alerts(self, limit: int = 500) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM alerts ORDER BY coalesce(alert_date, '0000-00-00') DESC, id DESC LIMIT ?", (limit,)).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def pending_matrix(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM alerts WHERE matrix_synced = 0 AND duplicate_status <> 'confirmed' ORDER BY coalesce(alert_date, '0000-00-00'), id"
            ).fetchall()
            return [self._row_to_dict(row) for row in rows]

    def mark_matrix_synced(self, alert_ids: list[int], row_by_id: dict[int, int]) -> None:
        now = now_colombia().isoformat(timespec="seconds")
        with self._connect() as db:
            for alert_id in alert_ids:
                db.execute(
                    "UPDATE alerts SET matrix_synced=1, matrix_row=?, updated_at=? WHERE id=?",
                    (row_by_id.get(alert_id), now, alert_id),
                )

    def dashboard(self) -> dict[str, Any]:
        with self._connect() as db:
            total = db.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
            new_pending = db.execute("SELECT COUNT(*) FROM alerts WHERE matrix_synced=0 AND duplicate_status <> 'confirmed'").fetchone()[0]
            pdf_ready = db.execute("SELECT COUNT(*) FROM alerts WHERE downloaded_at IS NOT NULL").fetchone()[0]
            failures = db.execute("SELECT COUNT(*) FROM alerts WHERE last_error <> '' OR status IN ('download_error','extract_error')").fetchone()[0]
            pending_review = db.execute("SELECT COUNT(*) FROM alerts WHERE duplicate_status='review' OR classification_confidence='pending' OR portal_presence='not_seen'").fetchone()[0]
        return {"total": total, "pending_matrix": new_pending, "pdf_ready": pdf_ready, "errors": failures, "pending_review": pending_review}
