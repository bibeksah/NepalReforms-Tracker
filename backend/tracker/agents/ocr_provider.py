"""
OCR provider abstraction for ingestion.

Primary goal:
  - decouple OCR engine choice from ingestion flow
  - support provider fallback without changing parser code
"""

from __future__ import annotations

import logging
import os
from typing import Protocol

from .parsers import parse_vision_response
from .router import router

logger = logging.getLogger(__name__)


class OCRProvider(Protocol):
    name: str

    def extract_projects(self, image_bytes: bytes, page_num: int, log_context: str = "") -> list[dict]:
        ...


class VisionOCRProvider:
    name = "vision"

    def extract_projects(self, image_bytes: bytes, page_num: int, log_context: str = "") -> list[dict]:
        prompt = (
            "Extract all budget project data from this Nepali government document page. "
            'Return a JSON array: [{"title_ne": "...", "budget": 50000000}, ...]'
        )
        response = router.query_vision(image_bytes, prompt)
        projects = parse_vision_response(response)
        if not isinstance(projects, list):
            return []
        for project in projects:
            if isinstance(project, dict):
                project["budget_source"] = "vision"
                project["ocr_provider"] = self.name
        return [p for p in projects if isinstance(p, dict)]


class DocumentIntelligenceOCRProvider:
    name = "document_intelligence"

    def __init__(self):
        self.endpoint = os.getenv("AZURE_DOC_INTELLIGENCE_ENDPOINT", "").strip()
        self.key = os.getenv("AZURE_DOC_INTELLIGENCE_KEY", "").strip()
        self._client = None
        self._unavailable_reason = ""
        if not self.endpoint or not self.key:
            self._unavailable_reason = "missing_doc_intelligence_credentials"
            return
        try:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.core.credentials import AzureKeyCredential
        except Exception as exc:  # pragma: no cover - import depends on optional package
            self._unavailable_reason = f"azure_doc_intelligence_not_installed:{type(exc).__name__}"
            return
        self._client = DocumentIntelligenceClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.key),
        )

    @property
    def available(self) -> bool:
        return self._client is not None

    def extract_projects(self, image_bytes: bytes, page_num: int, log_context: str = "") -> list[dict]:
        if not self.available:
            logger.warning("Doc intelligence unavailable, provider skipped: %s", self._unavailable_reason)
            return []

        poller = self._client.begin_analyze_document(
            "prebuilt-read",
            body=image_bytes,
            content_type="image/jpeg",
        )
        result = poller.result()
        lines: list[str] = []
        for page in getattr(result, "pages", []) or []:
            for line in getattr(page, "lines", []) or []:
                content = getattr(line, "content", "")
                if content:
                    lines.append(content)
        ocr_text = "\n".join(lines).strip()
        if not ocr_text:
            return []

        prompt = f"""
Extract budget projects from OCR text.
Return strict JSON array with keys: title_ne, budget.
OCR text:
{ocr_text[:16000]}
"""
        response = router.query_fast(prompt, max_tokens=2500)
        projects = parse_vision_response(response)
        if not isinstance(projects, list):
            return []
        for project in projects:
            if isinstance(project, dict):
                project["budget_source"] = "document_intelligence"
                project["ocr_provider"] = self.name
        return [p for p in projects if isinstance(p, dict)]


class FallbackOCRProvider:
    def __init__(self, primary: OCRProvider, fallback: OCRProvider):
        self.primary = primary
        self.fallback = fallback
        self.name = f"{getattr(primary, 'name', 'primary')}+fallback:{getattr(fallback, 'name', 'fallback')}"

    def extract_projects(self, image_bytes: bytes, page_num: int, log_context: str = "") -> list[dict]:
        try:
            primary_projects = self.primary.extract_projects(image_bytes, page_num, log_context=log_context)
            if primary_projects:
                return primary_projects
        except Exception as exc:
            logger.warning(
                "[%s] OCR primary provider failed on page=%s: %s: %s",
                log_context,
                page_num,
                type(exc).__name__,
                exc,
            )
        return self.fallback.extract_projects(image_bytes, page_num, log_context=log_context)


def get_ocr_provider() -> OCRProvider:
    mode = os.getenv("TRACKER_OCR_PROVIDER", "auto").strip().lower()
    vision = VisionOCRProvider()
    docintel = DocumentIntelligenceOCRProvider()

    if mode == "vision":
        return vision
    if mode in {"docintel", "document_intelligence"}:
        if docintel.available:
            return docintel
        return FallbackOCRProvider(vision, vision)

    if docintel.available:
        return FallbackOCRProvider(docintel, vision)
    return vision
