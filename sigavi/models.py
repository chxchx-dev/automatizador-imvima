from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable


@dataclass(slots=True)
class AlertRecord:
    alert_url: str
    pdf_url: str
    alert_date: date | None = None
    code: str = ""
    document_type: str = ""
    source_category: str = ""
    product_name: str = ""
    registry: str = ""
    internal_file_number: str = ""
    presentation: str = ""
    holder: str = ""
    manufacturer_importer: str = ""
    reference_code: str = ""
    lot_serial: str = ""
    description: str = ""
    indication_use: str = ""
    classification: str = ""
    classification_confidence: str = "pending"
    surveillance_type: str = ""
    pdf_path: str = ""
    downloaded_at: datetime | None = None
    document_hash: str = ""
    duplicate_status: str = "new"
    duplicate_of: int | None = None
    status: str = "discovered"
    last_error: str = ""
    matrix_synced: bool = False
    matrix_row: int | None = None
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def identity_key(self) -> str:
        from .duplicates import identity_key

        return identity_key(self.code, self.alert_date, self.product_name, self.alert_url, self.pdf_url)


@dataclass(slots=True)
class AlertCandidate:
    alert_url: str
    pdf_url: str
    alert_date: date | None
    title: str
    document_type: str
    source_category: str
    listing_url: str


@dataclass(slots=True)
class ExtractionResult:
    text: str = ""
    code: str = ""
    product_name: str = ""
    registry: str = ""
    internal_file_number: str = ""
    presentation: str = ""
    holder: str = ""
    manufacturer_importer: str = ""
    reference_code: str = ""
    lot_serial: str = ""
    description: str = ""
    indication_use: str = ""
    warnings: list[str] = field(default_factory=list)


ProgressCallback = Callable[[str, int, int, str], None]
