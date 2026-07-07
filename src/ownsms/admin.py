from django.contrib import admin

from . import models


@admin.register(models.Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "status", "created_at")
    search_fields = ("email",)
    list_filter = ("status",)


@admin.register(models.Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "name", "status", "last_seen_at")
    list_filter = ("status",)


@admin.register(models.Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "to", "status", "is_test", "created_at")
    list_filter = ("status", "is_test")
    search_fields = ("to",)


@admin.register(models.Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("id", "account", "status", "total", "created_at")
    list_filter = ("status",)


for m in (models.Sim, models.ApiKey, models.PairingCode, models.Webhook, models.WebhookDelivery, models.AuditLog):
    admin.site.register(m)
