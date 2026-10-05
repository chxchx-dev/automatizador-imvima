from __future__ import annotations

import logging
import re
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from .classification import classify_alert
from .config import Settings
from .constants import SPANISH_MONTHS
from .duplicates import content_hash, normalize_text, windows_safe_name
from .invima import InvimaClient
from .matrix import MatrixWriter
from .models import AlertCandidate, AlertRecord, ProgressCallback
from .pdf_extract import extract_pdf
from .repository import AlertRepository
from .timeutil import now_colombia, today_colombia


def configure_logging(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("sigavi")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(handler)
    return logger


def _date_from_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _candidate_code(candidate: AlertCandidate) -> str:
    source = f"{candidate.title} {candidate.pdf_url}"
    patterns = (r"\b[A-Z]{1,3}\d{4,6}-\d{3,6}\b", r"\b\d{1,4}\s*[-–]\s*20\d{2}\b")
    for pattern in patterns:
        match = re.search(pattern, source, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", "", match.group(0)).replace("–", "-").upper()
    return ""


def _title_product(title: str) -> str:
    return re.sub(
        r"^\s*(?:alerta\s+sanitaria|informe\s+de\s+seguridad)(?:\s+sobre)?\s*:?\s*",
        "",
        title or "",
        flags=re.IGNORECASE,
    ).strip()


def _path_for(candidate: AlertCandidate, record: AlertRecord, evidence_dir: Path) -> Path:
    when = candidate.alert_date or today_colombia()
    surveillance = record.surveillance_type or "Pendiente de clasificar"
    month = SPANISH_MONTHS[when.month - 1]
    code = record.code or "Sin_codigo"
    product = record.product_name or candidate.title or "Alerta"
    url_suffix = content_hash(candidate.pdf_url.encode("utf-8"))[:8]
    stem = windows_safe_name(f"{when:%Y-%m-%d}_Alerta_{code}_{product}_{url_suffix}")
    if not stem.lower().endswith(".pdf"):
        stem += ".pdf"
    return evidence_dir / windows_safe_name(surveillance, 40) / str(when.year) / month / stem


def _record_from_row(row: dict) -> AlertRecord:
    downloaded_at = None
    if row.get("downloaded_at"):
        try:
            downloaded_at = datetime.fromisoformat(row["downloaded_at"])
        except ValueError:
            pass
    return AlertRecord(
        alert_url=row.get("alert_url", ""),
        pdf_url=row.get("pdf_url", ""),
        alert_date=_date_from_iso(row.get("alert_date")),
        code=row.get("code", ""),
        document_type=row.get("document_type", ""),
        source_category=row.get("source_category", ""),
        product_name=row.get("product_name", ""),
        registry=row.get("registry", ""),
        internal_file_number=row.get("internal_file_number", ""),
        presentation=row.get("presentation", ""),
        holder=row.get("holder", ""),
        manufacturer_importer=row.get("manufacturer_importer", ""),
        reference_code=row.get("reference_code", ""),
        lot_serial=row.get("lot_serial", ""),
        description=row.get("description", ""),
        indication_use=row.get("indication_use", ""),
        classification=row.get("classification", ""),
        classification_confidence=row.get("classification_confidence", "pending"),
        surveillance_type=row.get("surveillance_type", ""),
        pdf_path=row.get("pdf_path", ""),
        downloaded_at=downloaded_at,
        document_hash=row.get("document_hash", ""),
        duplicate_status=row.get("duplicate_status", "new"),
        duplicate_of=row.get("duplicate_of"),
        status=row.get("status", "discovered"),
        last_error=row.get("last_error", ""),
        matrix_synced=bool(row.get("matrix_synced")),
        matrix_row=row.get("matrix_row"),
    )


class SigaviService:
    def __init__(self, settings: Settings, repository: AlertRepository | None = None, client: InvimaClient | None = None) -> None:
        self.settings = settings
        self.settings.data_dir = str(Path(self.settings.data_dir).expanduser())
        Path(self.settings.data_dir).mkdir(parents=True, exist_ok=True)
        self.repository = repository or AlertRepository(settings.database_path)
        self.client = client or InvimaClient(settings.timeout_seconds)
        self.logger = configure_logging(settings.log_path)

    def update(self, progress: ProgressCallback | None = None) -> dict[str, int | str]:
        try:
            start_date = date.fromisoformat(self.settings.start_date)
        except ValueError as exc:
            raise ValueError("La fecha inicial debe tener formato AAAA-MM-DD.") from exc

        run_id = self.repository.create_run(start_date)
        discovered = inserted = already = downloaded = reused = errors = 0
        pages_scanned = matrix_added = not_seen = 0
        scan_complete = False
        self.logger.info("Inicia actualización INVIMA desde %s", start_date)

        try:
            self._progress(progress, "Consultando INVIMA", 0, 100, "Leyendo alertas y páginas disponibles")
            candidates, pages_scanned = self.client.discover(
                start_date,
                max_pages=self.settings.max_pages,
                listing_url=self.settings.listing_url,
                progress=lambda current, total, message: self._progress(
                    progress, "Consultando INVIMA", min(25, int(current / max(total, 1) * 25)), 100, message
                ),
            )
            discovered = len(candidates)
            scan_complete = bool(getattr(self.client, "last_scan_complete", False))
            scan_issue = str(getattr(self.client, "last_scan_issue", "") or "")
            if not scan_complete and scan_issue:
                errors += 1
                self.logger.warning(scan_issue)
            self._progress(progress, "Procesando alertas", 27, 100, f"{discovered} documentos elegibles encontrados")

            for index, candidate in enumerate(candidates, start=1):
                try:
                    url_matches = self.repository.find_all_by_pdf_url(candidate.pdf_url)
                    candidate_code = _candidate_code(candidate)
                    candidate_date = candidate.alert_date.isoformat() if candidate.alert_date else ""
                    candidate_product = _title_product(candidate.title)
                    existing = None
                    for row in url_matches:
                        compared = 0
                        conflict = False
                        for field, candidate_value in (
                            ("code", candidate_code),
                            ("alert_date", candidate_date),
                            ("product_name", candidate_product),
                        ):
                            stored_value = str(row.get(field) or "").strip()
                            candidate_value = str(candidate_value or "").strip()
                            if stored_value and candidate_value:
                                compared += 1
                                if normalize_text(stored_value) != normalize_text(candidate_value):
                                    conflict = True
                        if compared >= 2 and not conflict:
                            existing = row
                            break
                    ambiguous_url_match = bool(url_matches) and existing is None
                    if existing and existing.get("status") not in {"download_error", "extract_error", "discovered"}:
                        already += 1
                        continue

                    if existing:
                        alert_id = int(existing["id"])
                        record = _record_from_row(existing)
                        if not record.product_name:
                            record.product_name = _title_product(candidate.title)
                        record.alert_date = record.alert_date or candidate.alert_date
                        record.document_type = record.document_type or candidate.document_type
                        record.source_category = record.source_category or candidate.source_category
                    else:
                        product_name = _title_product(candidate.title)
                        code = candidate_code
                        classification, surveillance, confidence = classify_alert(candidate.source_category, product_name)
                        record = AlertRecord(
                            alert_url=candidate.alert_url,
                            pdf_url=candidate.pdf_url,
                            alert_date=candidate.alert_date,
                            code=code,
                            document_type=candidate.document_type,
                            source_category=candidate.source_category,
                            product_name=product_name,
                            classification=classification,
                            classification_confidence=confidence,
                            surveillance_type=surveillance,
                            status="discovered",
                        )
                        matches = self.repository.find_code_matches(code)
                        if matches:
                            record.duplicate_status = "review"
                            record.status = "pending_review"
                            record.last_error = "Código reutilizado por INVIMA; se compara el documento completo antes de resolver la duplicidad."
                        if ambiguous_url_match:
                            record.duplicate_status = "review"
                            record.status = "pending_review"
                            record.last_error = "La URL del PDF ya existe, pero la fecha, el código o el producto difieren; se conserva para revisión."
                        alert_id = self.repository.insert_candidate(record, candidate.listing_url)
                        inserted += 1

                    target = Path(record.pdf_path) if record.pdf_path else _path_for(candidate, record, self.settings.evidence_dir)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    data: bytes | None = None
                    if target.is_file() and target.stat().st_size > 0:
                        data = target.read_bytes()
                        reused += 1
                    elif ambiguous_url_match and url_matches:
                        source_path = next((Path(row["pdf_path"]) for row in url_matches if row.get("pdf_path") and Path(row["pdf_path"]).is_file()), None)
                        if source_path:
                            shutil.copy2(source_path, target)
                            data = target.read_bytes()
                            reused += 1
                        else:
                            try:
                                data = self.client.download(candidate.pdf_url)
                                temporary = target.with_suffix(".download")
                                temporary.write_bytes(data)
                                temporary.replace(target)
                                downloaded += 1
                            except Exception as exc:
                                record.pdf_path = str(target)
                                record.status = "download_error"
                                record.last_error = f"Descarga de PDF pendiente: {exc}"
                                self.repository.update_alert(alert_id, record)
                                self.logger.exception("No se pudo descargar %s", candidate.pdf_url)
                                errors += 1
                                continue
                    else:
                        try:
                            data = self.client.download(candidate.pdf_url)
                            temporary = target.with_suffix(".download")
                            temporary.write_bytes(data)
                            temporary.replace(target)
                            downloaded += 1
                        except Exception as exc:
                            record.pdf_path = str(target)
                            record.status = "download_error"
                            record.last_error = f"Descarga de PDF pendiente: {exc}"
                            self.repository.update_alert(alert_id, record)
                            self.logger.exception("No se pudo descargar %s", candidate.pdf_url)
                            errors += 1
                            continue

                    record.pdf_path = str(target)
                    record.document_hash = content_hash(data)
                    record.downloaded_at = now_colombia()
                    record.status = "downloaded"
                    if record.duplicate_status != "review":
                        record.last_error = ""

                    prior_hash = self.repository.find_by_hash(record.document_hash)
                    if prior_hash and int(prior_hash["id"]) != alert_id:
                        same_meta = (
                            prior_hash.get("code", "").casefold() == record.code.casefold()
                            and prior_hash.get("alert_date") == (record.alert_date.isoformat() if record.alert_date else None)
                            and prior_hash.get("product_name", "").strip().casefold() == record.product_name.strip().casefold()
                        )
                        if same_meta:
                            record.duplicate_status = "confirmed"
                            record.duplicate_of = int(prior_hash["id"])
                        else:
                            record.duplicate_status = "review"
                            record.last_error = "El PDF coincide con otro registro, pero los metadatos difieren; requiere revisión."

                    try:
                        extracted = extract_pdf(target, candidate.pdf_url, candidate.title, candidate.document_type)
                        record.code = extracted.code or record.code
                        record.product_name = extracted.product_name or record.product_name
                        record.registry = extracted.registry
                        record.internal_file_number = extracted.internal_file_number
                        record.presentation = extracted.presentation
                        record.holder = extracted.holder
                        record.manufacturer_importer = extracted.manufacturer_importer
                        record.reference_code = extracted.reference_code
                        record.lot_serial = extracted.lot_serial
                        record.description = extracted.description
                        record.indication_use = extracted.indication_use
                        record.classification, record.surveillance_type, record.classification_confidence = classify_alert(
                            candidate.source_category, record.product_name, extracted.text
                        )
                        organized_target = _path_for(candidate, record, self.settings.evidence_dir)
                        if target != organized_target:
                            organized_target.parent.mkdir(parents=True, exist_ok=True)
                            if not organized_target.exists():
                                target.replace(organized_target)
                                target = organized_target
                            elif content_hash(organized_target.read_bytes()) == record.document_hash:
                                target.unlink(missing_ok=True)
                                target = organized_target
                            else:
                                suffix = record.document_hash[:10] or "duplicado"
                                organized_target = organized_target.with_name(f"{organized_target.stem}_{suffix}{organized_target.suffix}")
                                if not organized_target.exists():
                                    target.replace(organized_target)
                                    target = organized_target
                        record.pdf_path = str(target)
                        record.status = "processed" if extracted.text else "extract_error"
                        if extracted.warnings:
                            warning_text = "; ".join(extracted.warnings)
                            record.last_error = f"{record.last_error}; {warning_text}" if record.last_error else warning_text
                            if record.status == "extract_error":
                                errors += 1
                        self.repository.update_alert(alert_id, record, extracted.text)
                    except Exception as exc:
                        record.status = "extract_error"
                        detail = f"Error de extracción: {exc}"
                        record.last_error = f"{record.last_error}; {detail}" if record.last_error else detail
                        self.repository.update_alert(alert_id, record)
                        errors += 1
                        self.logger.exception("No se pudo extraer %s", target)
                except Exception as exc:
                    errors += 1
                    self.logger.exception("Error procesando %s", candidate.pdf_url)
                    continue

                percent = 28 + int(index / max(len(candidates), 1) * 55)
                self._progress(progress, "Procesando alertas", percent, 100, f"Procesada {index} de {len(candidates)}")

            self.repository.mark_seen_urls(run_id, [candidate.pdf_url for candidate in candidates])
            if scan_complete:
                not_seen = self.repository.mark_not_seen_in_run(run_id, start_date)

            pending = self.repository.pending_matrix()
            self._progress(progress, "Actualizando matriz", 88, 100, f"Sincronizando {len(pending)} registros con Excel")
            try:
                writer = MatrixWriter(self.settings.template_path, self.settings.matrix_output_path)
                synced_rows, matrix_added, already_in_matrix = writer.sync(pending)
                self.repository.mark_matrix_synced(list(synced_rows), synced_rows)
                self.logger.info("Matriz sincronizada: %s nuevas; %s existentes", matrix_added, already_in_matrix)
            except Exception as exc:
                errors += 1
                self.logger.exception("Matriz pendiente de sincronización")
                self._progress(progress, "Matriz pendiente", 92, 100, str(exc))

            status = "completed_with_errors" if errors else "completed"
            missing_text = f"; {not_seen} ya no visibles en el portal" if scan_complete and not_seen else ""
            incomplete_text = f"; revisión parcial: {scan_issue}" if scan_issue else ""
            summary = f"{discovered} encontradas; {inserted} nuevas; {already} ya registradas; {downloaded} PDFs descargados; {matrix_added} filas añadidas{missing_text}{incomplete_text}."
            self.repository.finish_run(
                run_id,
                status=status,
                pages_scanned=pages_scanned,
                alerts_found=discovered,
                alerts_new=inserted,
                alerts_existing=already,
                pdf_downloaded=downloaded,
                pdf_reused=reused,
                matrix_added=matrix_added,
                errors=errors,
                scan_complete=int(scan_complete),
                alerts_not_seen=not_seen,
                summary=summary,
            )
            self._progress(progress, "Actualización terminada", 100, 100, summary)
            self.logger.info(summary)
            return {
                "run_id": run_id,
                "status": status,
                "pages_scanned": pages_scanned,
                "found": discovered,
                "new": inserted,
                "existing": already,
                "pdf_downloaded": downloaded,
                "pdf_reused": reused,
                "matrix_added": matrix_added,
                "errors": errors,
                "scan_complete": int(scan_complete),
                "alerts_not_seen": not_seen,
                "summary": summary,
            }
        except Exception as exc:
            self.repository.finish_run(
                run_id,
                status="failed",
                pages_scanned=pages_scanned,
                alerts_found=discovered,
                alerts_new=inserted,
                alerts_existing=already,
                pdf_downloaded=downloaded,
                pdf_reused=reused,
                matrix_added=matrix_added,
                errors=errors + 1,
                scan_complete=int(scan_complete),
                alerts_not_seen=not_seen,
                summary=str(exc),
            )
            self.logger.exception("Falló la actualización")
            raise

    @staticmethod
    def _progress(callback: ProgressCallback | None, stage: str, current: int, total: int, message: str) -> None:
        if callback:
            callback(stage, current, total, message)
