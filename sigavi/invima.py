from __future__ import annotations

import re
import time
from datetime import date, datetime
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, Tag
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .constants import INVIMA_URL
from .models import AlertCandidate

USER_AGENT = "SIGAVI/1.0 (institutional sanitary-alert monitoring; contact configured by user)"
DATE_RE = re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b|\b(\d{1,2})/(\d{1,2})/(20\d{2})\b")


def _parse_date(value: str) -> date | None:
    match = DATE_RE.search(value)
    if not match:
        return None
    if match.group(1):
        year, month, day = map(int, match.group(1, 2, 3))
    else:
        day, month, year = map(int, match.group(4, 5, 6))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _set_page(url: str, page: int) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query, keep_blank_values=True)
    query["page"] = [str(page)]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def _is_pdf_url(url: str) -> bool:
    if urlparse(url).hostname != "app.invima.gov.co":
        return False
    lowered = url.lower()
    return ".pdf" in lowered or "ckfinder/userfiles/files" in lowered


def _visible_card_text(anchor: Tag) -> tuple[str, Tag]:
    chosen = anchor
    for parent in anchor.parents:
        if not isinstance(parent, Tag):
            continue
        chosen = parent
        text = " ".join(parent.stripped_strings)
        if len(text) > 35 and (
            parent.name in {"article", "li"}
            or "views-row" in " ".join(parent.get("class", []))
            or DATE_RE.search(text)
        ):
            break
        if len(text) > 180:
            break
    return "\n".join(chosen.stripped_strings), chosen


def _extract_title(card_text: str, anchor: Tag, card: Tag) -> str:
    candidates = []
    for link in card.find_all("a", href=True):
        if _is_pdf_url(urljoin(INVIMA_URL, str(link.get("href", "")))):
            continue
        label = " ".join(link.stripped_strings).strip()
        if label and len(label) > 12 and normalize_label(label) not in {"ver", "ver documento", "ver alerta"}:
            candidates.append(label)
    if candidates:
        return max(candidates, key=len)

    lines = [line.strip() for line in card_text.splitlines() if line.strip()]
    cleaned = []
    for line in lines:
        if DATE_RE.search(line) or normalize_label(line) in {"ver", "ver documento", "ver alerta", "alerta sanitaria", "informe de seguridad"}:
            continue
        if line.lower().startswith("alertas_sanitarias_") or line.lower().startswith("documentos_"):
            continue
        cleaned.append(line)
    if cleaned:
        return max(cleaned, key=len)
    return " ".join(anchor.stripped_strings).strip()


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _document_type(text: str) -> str:
    normalized = normalize_label(text)
    if "informe de seguridad" in normalized:
        return "Informe de Seguridad"
    if "alerta sanitaria" in normalized or "alerta sobre" in normalized:
        return "Alerta Sanitaria"
    return ""


def _source_category(text: str) -> str:
    for line in text.splitlines():
        value = line.strip()
        if re.match(r"^(alertas_sanitarias_|documentos_)", value, flags=re.IGNORECASE):
            return value
    return ""


def _find_next_page(soup: BeautifulSoup, current_url: str, page: int) -> str | None:
    for anchor in soup.find_all("a", href=True):
        label = normalize_label(" ".join(anchor.stripped_strings))
        classes = " ".join(anchor.get("class", [])).casefold()
        rel = " ".join(anchor.get("rel", [])).casefold()
        href = urljoin(current_url, str(anchor["href"]))
        query = parse_qs(urlparse(href).query)
        page_values = query.get("page", [])
        if not page_values:
            continue
        try:
            target_page = int(page_values[0])
        except ValueError:
            continue
        if target_page <= page:
            continue
        is_next = (
            "next" in rel
            or "next" in classes
            or "siguiente" in label
            or label in {"›", ">", "»", "siguiente"}
        )
        if is_next:
            return href

    numeric_pages: list[tuple[int, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(current_url, str(anchor["href"]))
        query = parse_qs(urlparse(href).query)
        try:
            target_page = int(query.get("page", [""])[0])
        except ValueError:
            continue
        if target_page > page:
            numeric_pages.append((target_page, href))
    if numeric_pages:
        return min(numeric_pages, key=lambda item: item[0])[1]
    return None


class InvimaClient:
    def __init__(self, timeout_seconds: int = 35, delay_seconds: float = 0.2) -> None:
        self.timeout_seconds = timeout_seconds
        self.delay_seconds = delay_seconds
        self.session = requests.Session()
        self.last_scan_complete = False
        self.last_scan_issue = ""
        retry = Retry(
            total=3,
            connect=3,
            read=2,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
        })

    def _get_soup(self, url: str) -> BeautifulSoup:
        response = self.session.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        return BeautifulSoup(response.text, "html.parser")

    def discover(self, start_date: date, max_pages: int = 500, listing_url: str = INVIMA_URL, progress=None) -> tuple[list[AlertCandidate], int]:
        if urlparse(listing_url).hostname != "app.invima.gov.co":
            raise ValueError("La captura debe consultar el dominio oficial app.invima.gov.co.")
        found: dict[str, AlertCandidate] = {}
        visited_pages: set[str] = set()
        url = _set_page(listing_url, 0)
        page_number = 0
        pages_scanned = 0
        self.last_scan_complete = False
        self.last_scan_issue = ""

        for _ in range(max(1, max_pages)):
            if url in visited_pages:
                self.last_scan_issue = "Se detectó un ciclo de paginación; no se marca el recorrido como completo."
                break
            visited_pages.add(url)
            if pages_scanned and self.delay_seconds:
                time.sleep(self.delay_seconds)
            try:
                soup = self._get_soup(url)
            except Exception as exc:
                self.last_scan_issue = f"No se pudo consultar la página {page_number + 1}: {exc}"
                break
            pages_scanned += 1
            page_candidates: list[AlertCandidate] = []

            for anchor in soup.find_all("a", href=True):
                pdf_url = urljoin(url, str(anchor["href"]))
                if not _is_pdf_url(pdf_url):
                    continue
                card_text, card = _visible_card_text(anchor)
                alert_date = _parse_date(card_text)
                if alert_date is not None and alert_date < start_date:
                    continue
                title = _extract_title(card_text, anchor, card)
                doc_type = _document_type(card_text)
                category = _source_category(card_text)
                alert_link = ""
                for link in card.find_all("a", href=True):
                    href = urljoin(url, str(link["href"]))
                    label = normalize_label(" ".join(link.stripped_strings))
                    if not _is_pdf_url(href) and label not in {"ver", "ver documento", "ver alerta"}:
                        alert_link = href
                        break
                candidate = AlertCandidate(
                    alert_url=alert_link or url,
                    pdf_url=pdf_url,
                    alert_date=alert_date,
                    title=title,
                    document_type=doc_type,
                    source_category=category,
                    listing_url=url,
                )
                page_candidates.append(candidate)
                found.setdefault(pdf_url.casefold(), candidate)

            if progress:
                progress(min(25, pages_scanned * 2), 25, f"Página {page_number + 1}: {len(page_candidates)} documentos")

            # The main INVIMA view is newest-first. Once every card on a page is older
            # than the configured cutoff, later pages cannot contain eligible alerts.
            dated = [item.alert_date for item in page_candidates if item.alert_date is not None]
            all_links = [
                _parse_date(_visible_card_text(anchor)[0])
                for anchor in soup.find_all("a", href=True)
                if _is_pdf_url(urljoin(url, str(anchor["href"])))
            ]
            if all_links and len(dated) == len(all_links) and all(value < start_date for value in all_links):
                self.last_scan_complete = True
                break

            next_url = _find_next_page(soup, url, page_number)
            if not next_url:
                self.last_scan_complete = True
                break
            next_page = parse_qs(urlparse(next_url).query).get("page", [str(page_number + 1)])[0]
            try:
                page_number = int(next_page)
            except ValueError:
                page_number += 1
            url = next_url
        else:
            self.last_scan_issue = f"Se alcanzó el límite de {max_pages} páginas antes de confirmar el final del listado."

        return list(found.values()), pages_scanned

    def download(self, url: str, max_bytes: int = 80_000_000) -> bytes:
        if urlparse(url).hostname != "app.invima.gov.co":
            raise ValueError("Solo se descargan documentos alojados en el portal oficial app.invima.gov.co.")
        response = self.session.get(url, timeout=self.timeout_seconds, stream=True)
        try:
            response.raise_for_status()
            if urlparse(response.url).hostname != "app.invima.gov.co":
                raise ValueError("El portal redirigió el PDF fuera del dominio oficial del INVIMA.")
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_content(chunk_size=128 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("El PDF supera el límite de descarga de 80 MB.")
                chunks.append(chunk)
            data = b"".join(chunks)
            if not data.startswith(b"%PDF"):
                content_type = response.headers.get("Content-Type", "")
                raise ValueError(f"La URL no entregó un PDF válido (Content-Type: {content_type or 'desconocido'}).")
            return data
        finally:
            response.close()
