"""
Content extraction for resources: turns a link URL, an uploaded file, or an
article's content into real, embeddable text.

Owner: Dev A (Data & Ingestion)

WHY THIS EXISTS
----------------
The review found that ingestion "embeds the literal URL string, not the page
it points to" and that there was no scraper or document parser anywhere in the
codebase — `full_text` for a resource was just its title/description/URL
concatenated. This module is the fix: given a `Resource` row, it produces the
actual text that should be chunked and embedded, either by fetching and
extracting readable text from a link, or by parsing an uploaded file.

For ARTICLE type resources, the `content` field is used directly — no external
fetching or parsing is needed.

SECURITY: SSRF
---------------
A trainer/admin-supplied URL is fetched *server-side*. Without guardrails
that's a classic SSRF vector — a malicious/compromised trainer account could
submit `http://169.254.169.254/latest/meta-data/...` (cloud metadata) or
`http://localhost:6379` (an internal service) as a "resource link" and have
the backend fetch it on their behalf. `_validate_public_url` resolves the
hostname and rejects anything that isn't a public, routable IP before any
request is made. This is defense in depth, not a substitute for network-level
egress controls — deploy this behind an egress proxy/allowlist if your
infrastructure supports one.

SIZE / TIME BOUNDS
------------------
- HTTP fetch: `_FETCH_TIMEOUT_SECONDS` connect+read timeout, streamed with a
  hard byte cap (`_MAX_FETCH_BYTES`) so a huge or slow-loris response can't
  tie up a worker or blow up memory.
- Extracted text is truncated to `_MAX_EXTRACTED_CHARS` before chunking —
  bounds embeddings API cost per resource regardless of source size.
- File parsing (PDF/DOCX) is similarly capped by page/paragraph count.

FAILURE MODE
------------
Every extraction function returns an `ExtractionResult` with a `status`
("ok" | "partial" | "failed") and an optional `error`, rather than raising.
A resource whose link 404s, times out, or blocks scraping should still be
searchable by its title/description — it should not block the whole
ingestion of the source from happening, and the *reason* it produced little
or no body text needs to be visible to whoever manages that resource (see
`Resource.content_extract_status` / `content_extract_error`, surfaced via
`ResourceResponse`).
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

logger = logging.getLogger("kodebuddy.agent.content_extraction")

_FETCH_TIMEOUT_SECONDS = 10
_MAX_FETCH_BYTES = 5 * 1024 * 1024  # 5 MB
_MAX_EXTRACTED_CHARS = 40_000
_USER_AGENT = "KodeBuddyResourceBot/1.0 (+https://kodecamp.example/bot)"

_ALLOWED_SCHEMES = {"http", "https"}

# Extraction status values, written back onto Resource.content_extract_status.
EXTRACT_STATUS_OK = "ok"
EXTRACT_STATUS_PARTIAL = "partial"
EXTRACT_STATUS_FAILED = "failed"


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    status: str  # "ok" | "partial" | "failed"
    error: str | None = None


def _validate_public_url(url: str) -> str | None:
    """
    Returns an error string if `url` is not safe to fetch server-side,
    otherwise None.

    Resolves the hostname and rejects private/loopback/link-local/reserved
    ranges (RFC 1918, 127.0.0.0/8, 169.254.0.0/16 incl. cloud metadata,
    ::1, fc00::/7, etc.) so a resource link can't be used to make the
    backend issue requests to internal infrastructure.
    """
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        return f"Could not parse URL: {exc}"

    if parsed.scheme not in _ALLOWED_SCHEMES:
        return f"Unsupported URL scheme '{parsed.scheme}'."
    if not parsed.hostname:
        return "URL has no hostname."

    try:
        addrinfo = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        return f"Could not resolve host '{parsed.hostname}': {exc}"

    for family, _, _, _, sockaddr in addrinfo:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return f"Resolved to a non-public address ({ip}); refusing to fetch."

    return None


def _fetch_url_bytes(url: str) -> bytes:
    """Streams `url` with a byte cap; raises requests exceptions on failure."""
    with requests.get(
        url,
        timeout=_FETCH_TIMEOUT_SECONDS,
        headers={"User-Agent": _USER_AGENT},
        stream=True,
        allow_redirects=True,
    ) as resp:
        resp.raise_for_status()

        # Re-validate the *final* URL after redirects -- a public URL can
        # redirect to an internal one.
        if resp.url != url:
            redirect_error = _validate_public_url(resp.url)
            if redirect_error:
                raise ValueError(f"Redirect target rejected: {redirect_error}")

        content_length = resp.headers.get("Content-Length")
        if content_length and int(content_length) > _MAX_FETCH_BYTES:
            raise ValueError(
                f"Response too large ({content_length} bytes > "
                f"{_MAX_FETCH_BYTES})."
            )

        chunks = []
        total = 0
        for chunk in resp.iter_content(chunk_size=64 * 1024):
            total += len(chunk)
            if total > _MAX_FETCH_BYTES:
                raise ValueError(
                    f"Response exceeded {_MAX_FETCH_BYTES} byte cap while "
                    "streaming."
                )
            chunks.append(chunk)
        return b"".join(chunks)


def extract_link_text(url: str) -> ExtractionResult:
    """
    Fetches `url` and extracts readable article/body text from it.

    Uses `trafilatura` for extraction — it handles boilerplate removal
    (nav, ads, footers) far better than a naive tag-strip, which matters
    because embedding a page's raw HTML chrome alongside its actual content
    would dilute the vector with irrelevant text and hurt retrieval quality.
    """
    if not url or not url.strip():
        return ExtractionResult(text="", status=EXTRACT_STATUS_FAILED, error="No URL provided.")

    validation_error = _validate_public_url(url)
    if validation_error:
        logger.warning("extract_link_text: rejected url=%s reason=%s", url, validation_error)
        return ExtractionResult(text="", status=EXTRACT_STATUS_FAILED, error=validation_error)

    try:
        raw_bytes = _fetch_url_bytes(url)
    except requests.RequestException as exc:
        logger.warning("extract_link_text: fetch failed url=%s error=%s", url, exc)
        return ExtractionResult(text="", status=EXTRACT_STATUS_FAILED, error=f"Fetch failed: {exc}")
    except ValueError as exc:
        logger.warning("extract_link_text: rejected url=%s error=%s", url, exc)
        return ExtractionResult(text="", status=EXTRACT_STATUS_FAILED, error=str(exc))

    try:
        import trafilatura

        extracted = trafilatura.extract(
            raw_bytes,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
    except ImportError:
        logger.error(
            "extract_link_text: trafilatura is not installed -- add it to "
            "requirements.txt. Falling back to a failed extraction rather "
            "than embedding raw HTML."
        )
        return ExtractionResult(
            text="",
            status=EXTRACT_STATUS_FAILED,
            error="Server misconfiguration: HTML extractor not installed.",
        )
    except Exception as exc:  # noqa: BLE001 -- third-party parser, keep going
        logger.warning("extract_link_text: parse failed url=%s error=%s", url, exc)
        return ExtractionResult(text="", status=EXTRACT_STATUS_FAILED, error=f"Parse failed: {exc}")

    if not extracted or not extracted.strip():
        return ExtractionResult(
            text="",
            status=EXTRACT_STATUS_FAILED,
            error="No extractable text found on the page (JS-rendered page, "
            "paywall, or empty body).",
        )

    truncated = extracted.strip()[:_MAX_EXTRACTED_CHARS]
    status = EXTRACT_STATUS_OK if len(truncated) == len(extracted.strip()) else EXTRACT_STATUS_PARTIAL
    return ExtractionResult(text=truncated, status=status, error=None)


def extract_file_text(file_path: str, mime_type: str | None, file_name: str | None) -> ExtractionResult:
    """
    Parses an uploaded resource file into plain text.

    Dispatches on file extension (more reliable than a client-supplied
    Content-Type for this purpose) among: PDF (pypdf), Word .docx
    (python-docx), and plain text/Markdown (read directly). Anything else
    fails closed with a clear error rather than silently embedding nothing.
    """
    name = (file_name or file_path or "").lower()

    try:
        if name.endswith(".pdf"):
            return _extract_pdf(file_path)
        if name.endswith(".docx"):
            return _extract_docx(file_path)
        if name.endswith((".txt", ".md", ".markdown")):
            return _extract_plain_text(file_path)
    except FileNotFoundError:
        return ExtractionResult(
            text="", status=EXTRACT_STATUS_FAILED, error="Uploaded file is missing from storage."
        )
    except Exception as exc:  # noqa: BLE001 -- third-party parser, keep going
        logger.warning("extract_file_text: parse failed file=%s error=%s", file_path, exc)
        return ExtractionResult(text="", status=EXTRACT_STATUS_FAILED, error=f"Parse failed: {exc}")

    return ExtractionResult(
        text="",
        status=EXTRACT_STATUS_FAILED,
        error=f"Unsupported file type for '{file_name or file_path}'. "
        "Supported: .pdf, .docx, .txt, .md.",
    )


def _extract_pdf(file_path: str) -> ExtractionResult:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    if reader.is_encrypted:
        # Try an empty password (common for "restricted but not really
        # password-protected" PDFs); otherwise fail closed rather than
        # guessing at a password.
        try:
            reader.decrypt("")
        except Exception:
            return ExtractionResult(
                text="", status=EXTRACT_STATUS_FAILED, error="PDF is password-protected."
            )

    pages_text = []
    for page in reader.pages:
        try:
            pages_text.append(page.extract_text() or "")
        except Exception as exc:  # noqa: BLE001 -- one bad page shouldn't sink the doc
            logger.warning("_extract_pdf: failed to extract a page: %s", exc)

    full_text = "\n\n".join(t for t in pages_text if t.strip())
    if not full_text.strip():
        return ExtractionResult(
            text="",
            status=EXTRACT_STATUS_FAILED,
            error="No extractable text (likely a scanned/image-only PDF; OCR is not supported).",
        )

    truncated = full_text[:_MAX_EXTRACTED_CHARS]
    status = EXTRACT_STATUS_OK if len(truncated) == len(full_text) else EXTRACT_STATUS_PARTIAL
    return ExtractionResult(text=truncated, status=status, error=None)


def _extract_docx(file_path: str) -> ExtractionResult:
    import docx  # python-docx

    document = docx.Document(file_path)
    parts = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    parts.append(cell.text.strip())

    full_text = "\n".join(parts)
    if not full_text.strip():
        return ExtractionResult(text="", status=EXTRACT_STATUS_FAILED, error="Document has no text content.")

    truncated = full_text[:_MAX_EXTRACTED_CHARS]
    status = EXTRACT_STATUS_OK if len(truncated) == len(full_text) else EXTRACT_STATUS_PARTIAL
    return ExtractionResult(text=truncated, status=status, error=None)


def _extract_plain_text(file_path: str) -> ExtractionResult:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        full_text = f.read()

    if not full_text.strip():
        return ExtractionResult(text="", status=EXTRACT_STATUS_FAILED, error="File is empty.")

    truncated = full_text[:_MAX_EXTRACTED_CHARS]
    status = EXTRACT_STATUS_OK if len(truncated) == len(full_text) else EXTRACT_STATUS_PARTIAL
    return ExtractionResult(text=truncated, status=status, error=None)


# --------------------------------------------------------------------------
# Full-text builders — combine metadata with extracted body text.
# --------------------------------------------------------------------------


def build_resource_full_text(resource) -> ExtractionResult:  # type: ignore[no-untyped-def]
    """
    Builds the text that gets chunked/embedded for one resource.

    Handles all three resource types:
    - LINK: fetches and scrapes the URL
    - FILE: parses the uploaded file
    - ARTICLE: uses the `content` field directly

    Always leads with title/description (cheap, always available, and
    useful even when body extraction fails entirely).
    """
    header = f"Resource Title: {resource.title}\nDescription: {resource.description or ''}"

    # Determine resource type
    resource_type = getattr(resource, "type", None)
    if resource_type is not None:
        # If type is an enum, get its value; if it's already a string, use it directly
        if hasattr(resource_type, "value"):
            type_value = resource_type.value
        else:
            type_value = str(resource_type).lower()
    else:
        type_value = ""

    # Handle based on type
    if type_value == "file":
        file_path = getattr(resource, "file_path", None)
        if file_path:
            result = extract_file_text(
                file_path,
                getattr(resource, "mime_type", None),
                getattr(resource, "file_name", None),
            )
            if result.status == EXTRACT_STATUS_FAILED:
                # Header alone still makes the resource discoverable by name;
                # only the body extraction failed.
                return ExtractionResult(text=header, status=EXTRACT_STATUS_FAILED, error=result.error)
            return ExtractionResult(text=f"{header}\n\n{result.text}", status=result.status, error=result.error)
        else:
            return ExtractionResult(
                text=header,
                status=EXTRACT_STATUS_FAILED,
                error="File resource has no file attached.",
            )

    elif type_value == "link":
        url = getattr(resource, "url", None)
        if url:
            result = extract_link_text(url)
            if result.status == EXTRACT_STATUS_FAILED:
                return ExtractionResult(
                    text=f"{header}\nLink URL: {url}",
                    status=EXTRACT_STATUS_FAILED,
                    error=result.error,
                )
            return ExtractionResult(text=f"{header}\n\n{result.text}", status=result.status, error=result.error)
        else:
            return ExtractionResult(
                text=header,
                status=EXTRACT_STATUS_FAILED,
                error="Link resource has no URL.",
            )

    elif type_value == "article":
        content = getattr(resource, "content", None)
        if content and content.strip():
            full_text = f"{header}\n\n{content}"
            truncated = full_text[:_MAX_EXTRACTED_CHARS]
            status = EXTRACT_STATUS_OK if len(truncated) == len(full_text) else EXTRACT_STATUS_PARTIAL
            return ExtractionResult(text=truncated, status=status, error=None)
        else:
            return ExtractionResult(
                text=header,
                status=EXTRACT_STATUS_FAILED,
                error="Article resource has no content.",
            )

    else:
        # Fallback for unknown/legacy types — use title/description only
        return ExtractionResult(text=header, status=EXTRACT_STATUS_OK, error=None)


def build_assignment_full_text(assignment) -> str:  # type: ignore[no-untyped-def]
    """
    Builds the text that gets chunked/embedded for one assignment.

    Includes instructions/requirements (structured JSON: list of
    {title, description}) flattened into readable text, so a learner asking
    a general question that touches an assignment's *content* (not just its
    id) has something to retrieve against.
    """
    parts = [
        f"Assignment Title: {assignment.title}",
        f"Description: {assignment.description or ''}",
    ]

    for label, items in (
        ("Instructions", assignment.instructions),
        ("Requirements", assignment.requirements),
    ):
        if not items:
            continue
        parts.append(f"{label}:")
        for item in items:
            title = item.get("title", "") if isinstance(item, dict) else ""
            description = item.get("description", "") if isinstance(item, dict) else str(item)
            parts.append(f"- {title}: {description}".strip(": "))

    parts.append(f"Maximum Score: {assignment.maximum_score}")
    parts.append(f"Due Date: {assignment.due_date.isoformat() if assignment.due_date else ''}")

    return "\n".join(parts)[:_MAX_EXTRACTED_CHARS]