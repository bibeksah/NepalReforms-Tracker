import uuid

from django.db import models


class TranslationCache(models.Model):
    """Caches non-English to English translations to avoid redundant LLM calls."""

    original_text = models.TextField(unique=True)
    translated_text = models.TextField()
    category = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.original_text[:50]


class FailedIngestionItem(models.Model):
    """Durable queue of ingestion failures for retry and human intervention."""

    STATUS_CHOICES = [
        ("pending_retry", "Pending Retry"),
        ("retrying", "Retrying"),
        ("resolved", "Resolved"),
        ("ignored", "Ignored"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_type = models.CharField(max_length=50, default="lal_kitab")
    source_path = models.CharField(max_length=1000, db_index=True)
    source_document = models.CharField(max_length=500, blank=True)
    source_hash = models.CharField(max_length=64, blank=True, db_index=True)

    stage = models.CharField(max_length=40, default="ingestion")
    failure_reason = models.CharField(max_length=255)
    failure_detail = models.TextField(blank=True)

    page_num = models.IntegerField(null=True, blank=True)
    page_numbers = models.JSONField(default=list, blank=True)

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending_retry", db_index=True
    )
    retry_count = models.IntegerField(default=0)
    last_retry_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    extra_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="tracker_fai_status_54d00e_idx"),
            models.Index(fields=["source_hash", "status"], name="tracker_fai_source__bfde94_idx"),
            models.Index(fields=["source_path", "stage"], name="tracker_fai_source__38f02a_idx"),
        ]

    def __str__(self):
        return (
            f"{self.status} {self.stage} {self.failure_reason} "
            f"{self.source_document or self.source_path}"
        )


class IngestionJob(models.Model):
    """Centralized ingestion run controller."""

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("planning", "Planning"),
        ("running", "Running"),
        ("review_hold", "Review Hold"),
        ("published", "Published"),
        ("failed", "Failed"),
        ("dead_letter", "Dead Letter"),
        ("completed", "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, default="smart_ingestion_job")
    manifest_path = models.CharField(max_length=1000, blank=True)
    requested_by = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    priority = models.IntegerField(default=50)

    source_count = models.IntegerField(default=0)
    processed_count = models.IntegerField(default=0)
    published_count = models.IntegerField(default=0)
    held_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)

    options = models.JSONField(default=dict, blank=True)
    error_summary = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"], name="tracker_ing_status_44a5fd_idx"),
            models.Index(fields=["created_at"], name="tracker_ing_created_912cff_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({str(self.id)[:8]}) {self.status}"


class IngestionDocument(models.Model):
    """Document-level unit of work for smart ingestion jobs."""

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("planning", "Planning"),
        ("extracting", "Extracting"),
        ("publishing", "Publishing"),
        ("review_hold", "Review Hold"),
        ("published", "Published"),
        ("failed", "Failed"),
    ]

    SOURCE_CHOICES = [
        ("lal_kitab", "Lal Kitab"),
        ("manifesto", "Manifesto"),
        ("media", "Media"),
        ("citizen", "Citizen"),
        ("other", "Other"),
    ]

    TIER_CHOICES = [
        ("A", "Tier A"),
        ("B", "Tier B"),
        ("C", "Tier C"),
    ]

    DESTINATION_CHOICES = [
        ("tracker", "Tracker"),
        ("platform", "Platform"),
        ("both", "Both"),
    ]

    job = models.ForeignKey(
        "IngestionJob",
        on_delete=models.CASCADE,
        related_name="documents",
    )
    source_path = models.CharField(max_length=1000, db_index=True)
    source_document = models.CharField(max_length=500, blank=True)
    source_hash = models.CharField(max_length=64, blank=True, db_index=True)
    source_type = models.CharField(max_length=30, choices=SOURCE_CHOICES, default="lal_kitab")
    source_tier = models.CharField(max_length=1, choices=TIER_CHOICES, default="A")
    destination = models.CharField(max_length=20, choices=DESTINATION_CHOICES, default="tracker")

    gov_level = models.CharField(max_length=20, blank=True)
    province_name = models.CharField(max_length=100, blank=True)
    fiscal_year = models.CharField(max_length=20, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued", db_index=True)
    plan_strategy = models.CharField(max_length=40, blank=True)
    plan_confidence = models.FloatField(default=0.0)
    plan_reason = models.TextField(blank=True)
    requires_vision = models.BooleanField(default=False)
    requires_ocr = models.BooleanField(default=False)
    estimated_pages = models.IntegerField(default=0)

    extracted_count = models.IntegerField(default=0)
    published_count = models.IntegerField(default=0)
    held_count = models.IntegerField(default=0)
    attempt_count = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    error_detail = models.TextField(blank=True)

    payload_schema = models.CharField(max_length=80, blank=True)
    extra_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["job", "status"], name="tracker_ing_job_id_d970ef_idx"),
            models.Index(fields=["source_hash", "status"], name="tracker_ing_source__8ae7a7_idx"),
            models.Index(fields=["source_type", "status"], name="tracker_ing_source__022457_idx"),
        ]

    def __str__(self):
        return f"{self.source_document or self.source_path} ({self.status})"


class ReviewQueueItem(models.Model):
    """Ambiguous records held for human review before Neo4j publish."""

    STATUS_CHOICES = [
        ("pending_review", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("resolved", "Resolved"),
    ]

    RISK_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        "IngestionJob",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="review_items",
    )
    document = models.ForeignKey(
        "IngestionDocument",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="review_items",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending_review")
    reason = models.CharField(max_length=255)
    risk_level = models.CharField(max_length=20, choices=RISK_CHOICES, default="medium")
    confidence = models.FloatField(default=0.0)

    entity_type = models.CharField(max_length=80, default="Project")
    record_key = models.CharField(max_length=128, blank=True)
    fingerprint = models.CharField(max_length=64, blank=True, db_index=True)

    proposed_payload = models.JSONField(default=dict, blank=True)
    provenance = models.JSONField(default=dict, blank=True)

    reviewer = models.CharField(max_length=100, blank=True)
    reviewer_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="tracker_rev_status_239d2c_idx"),
            models.Index(fields=["fingerprint", "status"], name="tracker_rev_fingerp_66c78a_idx"),
        ]

    def __str__(self):
        return f"{self.status} {self.reason} ({self.entity_type})"
