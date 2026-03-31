from django.contrib import admin

from .models import (
    FailedIngestionItem,
    IngestionDocument,
    IngestionJob,
    ReviewQueueItem,
    TranslationCache,
)


@admin.register(TranslationCache)
class TranslationCacheAdmin(admin.ModelAdmin):
    list_display = ("original_short", "translated_short", "category", "created_at")
    search_fields = ("original_text", "translated_text")
    list_filter = ("category",)

    @admin.display(description="Original")
    def original_short(self, obj):
        return obj.original_text[:60]

    @admin.display(description="Translation")
    def translated_short(self, obj):
        return obj.translated_text[:60]


@admin.register(FailedIngestionItem)
class FailedIngestionItemAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "status",
        "stage",
        "failure_reason",
        "source_document_short",
        "retry_count",
        "resolved_at",
    )
    list_filter = ("status", "stage", "source_type")
    search_fields = ("source_path", "source_document", "failure_reason", "failure_detail")
    readonly_fields = ("id", "created_at", "updated_at", "last_retry_at", "resolved_at")
    actions = ("mark_resolved", "mark_ignored", "mark_pending_retry")

    @admin.display(description="Source")
    def source_document_short(self, obj):
        label = obj.source_document or obj.source_path
        return label[:80]

    @admin.action(description="Mark selected as resolved")
    def mark_resolved(self, request, queryset):
        now = __import__("django.utils.timezone", fromlist=["now"]).now()
        count = queryset.update(status="resolved", resolved_at=now)
        self.message_user(request, f"Marked {count} item(s) resolved.")

    @admin.action(description="Mark selected as ignored")
    def mark_ignored(self, request, queryset):
        count = queryset.update(status="ignored")
        self.message_user(request, f"Marked {count} item(s) ignored.")

    @admin.action(description="Reset selected to pending retry")
    def mark_pending_retry(self, request, queryset):
        count = queryset.update(status="pending_retry", resolved_at=None)
        self.message_user(request, f"Reset {count} item(s) to pending retry.")


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "name",
        "status",
        "priority",
        "source_count",
        "processed_count",
        "published_count",
        "held_count",
        "failed_count",
    )
    list_filter = ("status", "priority")
    search_fields = ("name", "manifest_path", "requested_by")
    readonly_fields = ("id", "created_at", "started_at", "completed_at")


@admin.register(IngestionDocument)
class IngestionDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "job",
        "source_document_short",
        "source_type",
        "source_tier",
        "status",
        "plan_strategy",
        "extracted_count",
        "published_count",
        "held_count",
    )
    list_filter = ("status", "source_type", "source_tier", "destination", "gov_level")
    search_fields = ("source_path", "source_document", "province_name", "fiscal_year")
    readonly_fields = ("id", "created_at", "updated_at", "last_attempt_at")

    @admin.display(description="Source")
    def source_document_short(self, obj):
        return (obj.source_document or obj.source_path)[:90]


@admin.register(ReviewQueueItem)
class ReviewQueueItemAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "status",
        "entity_type",
        "reason",
        "risk_level",
        "confidence",
        "record_key",
    )
    list_filter = ("status", "risk_level", "entity_type")
    search_fields = ("reason", "record_key", "fingerprint", "reviewer")
    readonly_fields = ("id", "created_at", "updated_at", "reviewed_at", "resolved_at")
    actions = ("mark_approved", "mark_rejected", "mark_resolved")

    @admin.action(description="Mark selected as approved")
    def mark_approved(self, request, queryset):
        now = __import__("django.utils.timezone", fromlist=["now"]).now()
        count = queryset.update(status="approved", reviewer=str(request.user), reviewed_at=now)
        self.message_user(request, f"Marked {count} item(s) approved.")

    @admin.action(description="Mark selected as rejected")
    def mark_rejected(self, request, queryset):
        now = __import__("django.utils.timezone", fromlist=["now"]).now()
        count = queryset.update(status="rejected", reviewer=str(request.user), reviewed_at=now)
        self.message_user(request, f"Marked {count} item(s) rejected.")

    @admin.action(description="Mark selected as resolved")
    def mark_resolved(self, request, queryset):
        now = __import__("django.utils.timezone", fromlist=["now"]).now()
        count = queryset.update(status="resolved", resolved_at=now)
        self.message_user(request, f"Marked {count} item(s) resolved.")
