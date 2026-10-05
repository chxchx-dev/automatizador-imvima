from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from .constants import SECTION_HEADINGS
from .models import ExtractionResult


def _normal_heading(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return re.sub(r"[\s:.;-]+$", "", value).casefold()


def _section(text: str, heading: str) -> str:
    lines = text.splitlines()
    target = _normal_heading(heading)
    heading_names = {_normal_heading(item): item for item in SECTION_HEADINGS}

    def heading_key(line: str) -> str | None:
        normalized = _normal_heading(line).replace("：", ":")
        for key in sorted(heading_names, key=len, reverse=True):
            if normalized == key or normalized.startswith(key + ":"):
                return key
        return None

    start_index = -1
    inline = ""

    for index, line in enumerate(lines):
        stripped = line.strip()
        key = heading_key(stripped)
        if key == target:
            start_index = index
            canonical = heading_names[key]
            inline = re.sub(
                r"^\s*" + re.escape(canonical) + r"\s*[:：]?\s*",
                "",
                stripped,
                flags=re.IGNORECASE,
            ).strip()
    if start_index < 0:
        return ""

    end_index = len(lines)
    for index in range(start_index + 1, len(lines)):
        if heading_key(lines[index]):
            end_index = index
            break
    captured = ([inline] if inline else []) + lines[start_index + 1:end_index]
    while captured and not captured[0].strip():
        captured.pop(0)
    while captured and not captured[-1].strip():
        captured.pop()
    return "\n".join(captured).strip()


def _label_value(text: str, labels: tuple[str, ...]) -> str:
    lines = text.splitlines()
    label_pattern = re.compile(r"^\s*(?:" + "|".join(labels) + r")\s*(?:[:：-]|\s{2,})\s*(.*)$", re.IGNORECASE)
    plain_pattern = re.compile(r"^\s*(?:" + "|".join(labels) + r")\s*$", re.IGNORECASE)
    results: list[str] = []
    for index, line in enumerate(lines):
        match = label_pattern.match(line)
        if match:
            value = match.group(1).strip()
            if not value and index + 1 < len(lines):
                value = lines[index + 1].strip()
            if value and value not in results:
                results.append(value)
        elif plain_pattern.match(line) and index + 1 < len(lines):
            value = lines[index + 1].strip()
            if value and value not in results:
                results.append(value)
    return "\n".join(results)


def _find_code(text: str, pdf_url: str) -> str:
    labeled = re.search(r"\balerta\s+(?:sanitaria\s+)?(?:no\.?|n[uú]mero)?\s*[:#]?\s*(\d{1,4}\s*[-–]\s*20\d{2})\b", text, re.IGNORECASE)
    if labeled:
        return re.sub(r"\s+", "", labeled.group(1)).replace("–", "-")
    patterns = (
        r"\b[A-Z]{1,3}\d{4,6}-\d{3,6}\b",
        r"\b\d{1,4}\s*[-–]\s*20\d{2}\b",
    )
    for source in (text, pdf_url):
        for pattern in patterns:
            match = re.search(pattern, source, re.IGNORECASE)
            if match:
                return re.sub(r"\s+", "", match.group(0)).replace("–", "-").upper()
    return ""


def _find_registration(text: str) -> str:
    no_record = re.search(
        r"[^\n]*(?:no posee registro sanitario|sin nso o registro sanitario|no cuenta con registro sanitario)[^\n]*",
        text,
        re.IGNORECASE,
    )
    if no_record:
        return no_record.group(0).strip()
    explicit = re.search(
        r"(?:no\.?\s*(?:posee|cuenta con)\s+)?(?:registro\s+sanitario|reg\.?\s*invima|nso\s*(?:o|/)?\s*registro\s+sanitario)[^\n:]{0,35}[:]?\s*([^\n]{1,180})",
        text,
        re.IGNORECASE,
    )
    if explicit:
        value = explicit.group(0).strip(" :-\t")
        return value
    return ""


def extract_pdf(path: str | Path, pdf_url: str = "", candidate_title: str = "", document_type: str = "") -> ExtractionResult:
    result = ExtractionResult()
    try:
        reader = PdfReader(str(path), strict=False)
        text_parts = [(page.extract_text() or "") for page in reader.pages]
        result.text = "\n\n".join(part for part in text_parts if part).strip()
    except Exception as exc:  # a broken or encrypted document must not block the batch
        result.warnings.append(f"No se pudo extraer texto: {exc}")
        return result

    if len(result.text) < 40:
        result.warnings.append("El PDF no contiene texto suficiente para extracción automática; puede requerir revisión/OCR.")

    result.code = _find_code(result.text, pdf_url)
    result.product_name = re.sub(
        r"^\s*(?:alerta\s+sanitaria|informe\s+de\s+seguridad)(?:\s+sobre)?\s*:?\s*",
        "",
        candidate_title,
        flags=re.IGNORECASE,
    ).strip()
    result.registry = _find_registration(result.text)
    result.internal_file_number = _label_value(result.text, (r"expediente", r"n[uú]mero de expediente", r"exp\."))
    result.presentation = _label_value(result.text, (r"presentaci[oó]n", r"presentaci[oó]n comercial", r"forma farmac[eé]utica"))
    result.holder = _label_value(result.text, (r"titular(?: del registro sanitario)?", r"titular del producto"))
    result.manufacturer_importer = _label_value(result.text, (r"fabricante(?:\s*/\s*importador)?", r"importador"))
    result.reference_code = _label_value(result.text, (r"referencia(?:\s*/\s*c[oó]digo)?", r"modelo", r"c[oó]digo de producto"))
    result.lot_serial = _label_value(result.text, (r"lote(?:s)?(?:\s*/\s*serial(?:es)?)?", r"serial(?:es)?", r"n[uú]mero de serie"))
    result.description = _section(result.text, "Descripción del caso")
    result.indication_use = _section(result.text, "Indicaciones y uso establecido")
    if not result.indication_use and document_type.casefold() == "informe de seguridad":
        result.indication_use = _section(result.text, "Antecedentes")
    return result
