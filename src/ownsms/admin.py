from django.contrib import admin
from django.db.models import Count
from django.utils import timezone
from django.utils.html import format_html

from . import models

_STATUS_COLORS = {
    "queued": "#F5A623",
    "dispatched": "#2952E3",
    "sent": "#2952E3",
    "delivered": "#16C784",
    "failed": "#E5484D",
    "expired": "#64748B",
    "canceled": "#64748B",
    "running": "#2952E3",
    "scheduled": "#F5A623",
    "paused": "#64748B",
    "completed": "#16C784",
    "pending": "#F5A623",
}


def _badge(status):
    return format_html('<b style="color:{}">{}</b>', _STATUS_COLORS.get(status, "#64748B"), status)


@admin.register(models.Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "status", "device_count", "message_count", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "email")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(_dev=Count("devices", distinct=True), _msg=Count("messages", distinct=True))
        )

    @admin.display(description="Devices", ordering="_dev")
    def device_count(self, obj):
        return obj._dev

    @admin.display(description="Messages", ordering="_msg")
    def message_count(self, obj):
        return obj._msg


class SimInline(admin.TabularInline):
    model = models.Sim
    extra = 0
    fields = ("subscription_id", "number", "operator", "is_default", "rate_per_min", "rate_per_day", "daily_quota")


@admin.register(models.Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "name", "status", "online", "last_seen_at", "app_version", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "account__email")
    date_hierarchy = "created_at"
    readonly_fields = ("device_token", "last_seen_at", "created_at")
    list_select_related = ("account",)
    inlines = [SimInline]
    actions = ["activate", "deactivate"]

    @admin.display(description="Online", boolean=True)
    def online(self, obj):
        return obj.is_online(timezone.now())

    @admin.action(description="Faollashtirish (activate)")
    def activate(self, request, queryset):
        n = queryset.update(status="active")
        self.message_user(request, f"{n} ta qurilma faollashtirildi.")

    @admin.action(description="O'chirish (deactivate)")
    def deactivate(self, request, queryset):
        n = queryset.update(status="inactive")
        self.message_user(request, f"{n} ta qurilma o'chirildi.")


@admin.register(models.Sim)
class SimAdmin(admin.ModelAdmin):
    list_display = ("id", "device", "number", "operator", "is_default", "rate_per_min", "rate_per_day", "daily_quota")
    list_filter = ("is_default", "operator")
    search_fields = ("number", "operator")
    list_select_related = ("device",)


@admin.register(models.ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "device", "prefix", "scopes", "is_test", "revoked", "last_used_at", "created_at")
    list_filter = ("revoked", "is_test")
    search_fields = ("prefix", "account__email")
    readonly_fields = ("key_hash", "prefix", "created_at", "last_used_at")
    list_select_related = ("account", "device")
    actions = ["revoke"]

    @admin.action(description="Bekor qilish (revoke)")
    def revoke(self, request, queryset):
        n = queryset.update(revoked=True)
        self.message_user(request, f"{n} ta API kalit bekor qilindi.")


@admin.register(models.Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "to", "status_badge", "segments", "is_test", "created_at", "sent_at")
    list_filter = ("status", "is_test", "queued")
    search_fields = ("to", "text", "idempotency_key")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "dispatched_at", "sent_at", "delivered_at", "lease_expires_at")
    list_select_related = ("account", "sim")
    actions = ["cancel_queued"]

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return _badge(obj.status)

    @admin.action(description="Bekor qilish (faqat queued)")
    def cancel_queued(self, request, queryset):
        n = queryset.filter(status="queued").update(status="canceled")
        self.message_user(request, f"{n} ta navbatdagi xabar bekor qilindi.")


@admin.register(models.Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "status_badge", "total", "sent_count", "created_at")
    list_filter = ("status",)
    search_fields = ("account__email",)
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)
    list_select_related = ("account",)

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return _badge(obj.status)

    @admin.display(description="Sent")
    def sent_count(self, obj):
        return obj.messages.filter(status__in=["sent", "delivered"]).count()


@admin.register(models.Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ("account", "url", "enabled", "events", "created_at")
    list_filter = ("enabled",)
    search_fields = ("account__email", "url")
    readonly_fields = ("secret", "created_at")  # secret is sensitive — never editable here


@admin.register(models.WebhookDelivery)
class WebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "status_badge", "attempts", "account", "created_at", "next_retry_at")
    list_filter = ("status", "event")
    search_fields = ("event_id", "event")
    date_hierarchy = "created_at"
    readonly_fields = ("payload", "created_at")
    list_select_related = ("account",)

    @admin.display(description="Status", ordering="status")
    def status_badge(self, obj):
        return _badge(obj.status)


@admin.register(models.PairingCode)
class PairingCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "account", "used", "expires_at", "created_at")
    list_filter = ("used",)
    search_fields = ("code", "account__email")
    readonly_fields = ("created_at",)


@admin.register(models.AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target", "account", "ip")
    list_filter = ("actor", "action")
    search_fields = ("action", "target", "ip")
    date_hierarchy = "created_at"
    list_select_related = ("account",)

    # An audit trail is append-only — read-only in the admin.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
