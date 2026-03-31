import base64
import logging
import os
import random
import threading
import time

from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()
logger = logging.getLogger(__name__)


class _TokenBucket:
    """Thread-safe token bucket limiter for model TPM budgets."""

    def __init__(self, tokens_per_minute: int):
        capacity = max(1, int(tokens_per_minute))
        self.capacity = float(capacity)
        self.tokens = float(capacity)
        self.refill_rate = float(capacity) / 60.0
        self.updated_at = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self, now: float):
        elapsed = max(0.0, now - self.updated_at)
        if elapsed <= 0:
            return
        self.tokens = min(self.capacity, self.tokens + (elapsed * self.refill_rate))
        self.updated_at = now

    def acquire(self, amount: int):
        needed = max(1.0, float(amount))
        while True:
            with self._lock:
                now = time.monotonic()
                self._refill(now)
                if self.tokens >= needed:
                    self.tokens -= needed
                    return
                missing = needed - self.tokens
                wait_seconds = missing / self.refill_rate if self.refill_rate else 0.05
            time.sleep(min(max(wait_seconds, 0.01), 2.0))

    def refund(self, amount: int):
        delta = max(0.0, float(amount))
        if delta <= 0:
            return
        with self._lock:
            self._refill(time.monotonic())
            self.tokens = min(self.capacity, self.tokens + delta)

    def burn(self, amount: int):
        delta = max(0.0, float(amount))
        if delta <= 0:
            return
        with self._lock:
            self._refill(time.monotonic())
            self.tokens = max(0.0, self.tokens - delta)


class ModelRouter:
    def __init__(self):
        # Client 1: Primary OpenAI (GPT-5.4)
        self.client_54 = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-02-01",
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
        )
        self.deployment_54 = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

        # Client 2: Vision/Fast (Nexalaris GPT-4o) - PRIMARY FOR OCR
        self.client_vision = AzureOpenAI(
            api_key=os.getenv("AZURE_VISION_KEY"),
            api_version=os.getenv("AZURE_VISION_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_VISION_ENDPOINT")
        )
        self.deployment_vision = os.getenv("AZURE_VISION_DEPLOYMENT")

        self.oss_model = "gpt-oss:latest"

        # Global shared limiter for all GPT-4o traffic (text + vision).
        self.vision_tpm = int(os.getenv("TRACKER_4O_TPM", "25000000"))
        self._vision_limiter = _TokenBucket(self.vision_tpm)
        self._chars_per_token = max(1, int(os.getenv("TRACKER_4O_CHARS_PER_TOKEN", "4")))
        self._req_overhead_tokens = int(os.getenv("TRACKER_4O_REQUEST_OVERHEAD_TOKENS", "120"))
        self._vision_image_tokens = int(os.getenv("TRACKER_4O_VISION_IMAGE_TOKEN_ESTIMATE", "1800"))
        self._max_retries = max(1, int(os.getenv("TRACKER_4O_MAX_RETRIES", "5")))
        self._retry_base = float(os.getenv("TRACKER_4O_RETRY_BASE_SEC", "0.75"))
        self._retry_cap = float(os.getenv("TRACKER_4O_RETRY_MAX_SEC", "20"))

    def query_vision(self, image_bytes, prompt=None):
        """Uses GPT-4o Vision via Nexalaris resource (Verified)."""
        if not prompt:
            prompt = "Extract the budget table from this page. Return ONLY a JSON list of objects with keys: 'title_ne' and 'budget'."
        estimate_tokens = self._estimate_vision_tokens(prompt, image_bytes, max_tokens=2000)

        def _request():
            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            return self.client_vision.chat.completions.create(
                model=self.deployment_vision,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}},
                ]}],
                max_tokens=2000,
            )

        return self._call_vision_with_scheduler(
            request_fn=_request,
            estimate_tokens=estimate_tokens,
            context="vision_ocr",
        )

    def query_fast(self, prompt, max_tokens=2000):
        estimate_tokens = self._estimate_text_tokens(prompt, max_tokens)

        def _request():
            return self.client_vision.chat.completions.create(
                model=self.deployment_vision,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )

        return self._call_vision_with_scheduler(
            request_fn=_request,
            estimate_tokens=estimate_tokens,
            context="fast_text",
        )

    def query_reasoning(self, prompt, max_tokens=4000):
        try:
            resp = self.client_54.chat.completions.create(
                model=self.deployment_54,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return "[]"

    def query_local(self, prompt):
        return "[]"

    def _estimate_text_tokens(self, prompt: str, max_tokens: int) -> int:
        prompt_tokens = max(1, len(prompt or "") // self._chars_per_token)
        return int(prompt_tokens + max_tokens + self._req_overhead_tokens)

    def _estimate_vision_tokens(self, prompt: str, image_bytes: bytes, max_tokens: int) -> int:
        prompt_tokens = max(1, len(prompt or "") // self._chars_per_token)
        # Small dynamic component from payload size while keeping a conservative floor.
        image_tokens = max(self._vision_image_tokens, len(image_bytes or b"") // 900)
        return int(prompt_tokens + image_tokens + max_tokens + self._req_overhead_tokens)

    @staticmethod
    def _is_rate_limited(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        if status_code == 429:
            return True
        response = getattr(exc, "response", None)
        if response is not None and getattr(response, "status_code", None) == 429:
            return True
        text = str(exc).lower()
        return "rate limit" in text or "too many requests" in text or "429" in text

    def _compute_backoff(self, attempt: int, exc: Exception) -> float:
        delay = min(self._retry_cap, self._retry_base * (2 ** attempt))
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", {}) or {}
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after is not None:
            try:
                delay = max(delay, float(retry_after))
            except (TypeError, ValueError):
                pass
        return min(self._retry_cap, delay + random.uniform(0.0, 0.25))

    def _extract_content(self, response) -> str:
        try:
            content = response.choices[0].message.content
            if isinstance(content, str):
                return content.strip()
            return str(content).strip()
        except Exception:
            return "[]"

    def _reconcile_token_usage(self, response, reserved_tokens: int):
        usage = getattr(response, "usage", None)
        actual_total = getattr(usage, "total_tokens", None)
        if actual_total is None:
            return
        try:
            actual = int(actual_total)
        except (TypeError, ValueError):
            return

        delta = int(reserved_tokens) - actual
        if delta > 0:
            self._vision_limiter.refund(delta)
        elif delta < 0:
            self._vision_limiter.burn(-delta)

    def _call_vision_with_scheduler(self, request_fn, estimate_tokens: int, context: str) -> str:
        reserved = max(1, int(estimate_tokens))
        for attempt in range(self._max_retries):
            self._vision_limiter.acquire(reserved)
            try:
                response = request_fn()
                self._reconcile_token_usage(response, reserved)
                return self._extract_content(response)
            except Exception as exc:
                if self._is_rate_limited(exc):
                    # Request rejected; release reservation and retry with backoff.
                    self._vision_limiter.refund(reserved)
                    delay = self._compute_backoff(attempt, exc)
                    logger.warning(
                        "GPT-4o rate limited (%s), retry %d/%d in %.2fs",
                        context,
                        attempt + 1,
                        self._max_retries,
                        delay,
                    )
                    time.sleep(delay)
                    continue
                logger.warning("GPT-4o request failed (%s): %s", context, exc)
                return "[]"
        logger.error("GPT-4o retries exhausted (%s)", context)
        return "[]"


router = ModelRouter()
