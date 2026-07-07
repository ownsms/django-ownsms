from datetime import timedelta

from django.db import models

from . import conf


class Account(models.Model):
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(blank=True)  # optional (no verification in v1)
    status = models.CharField(max_length=20, default="active")  # active|suspended
    created_at = models.DateTimeField(auto_now_add=True)


class Device(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="devices")
    name = models.CharField(max_length=200)
    device_token = models.CharField(max_length=64, unique=True)  # sha256 hex
    app_version = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=20, default="active")  # active|inactive
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_online(self, now):
        if not self.last_seen_at:
            return False
        return (now - self.last_seen_at) < timedelta(seconds=conf.get("DEVICE_ONLINE_SECONDS"))


class Sim(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="sims")
    subscription_id = models.IntegerField()
    number = models.CharField(max_length=20)
    operator = models.CharField(max_length=40, blank=True)
    is_default = models.BooleanField(default=False)
    rate_per_min = models.IntegerField(default=15)
    rate_per_hour = models.IntegerField(default=200)
    rate_per_day = models.IntegerField(default=500)
    jitter_min = models.IntegerField(default=2)  # seconds
    jitter_max = models.IntegerField(default=5)
    work_hours_start = models.TimeField(null=True, blank=True)
    work_hours_end = models.TimeField(null=True, blank=True)
    daily_quota = models.IntegerField(null=True, blank=True)


class ApiKey(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="api_keys")
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="api_keys")
    key_hash = models.CharField(max_length=64, unique=True)
    prefix = models.CharField(max_length=16)
    name = models.CharField(max_length=200, blank=True)
    scopes = models.JSONField(default=list)  # ["send","read"]
    ip_allowlist = models.JSONField(default=list)  # [] = unrestricted; ["10.0.0.0/8", "1.2.3.4"]
    is_test = models.BooleanField(default=False)
    revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)


class Campaign(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="campaigns")
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="campaigns")
    sim = models.ForeignKey(Sim, on_delete=models.SET_NULL, null=True, related_name="campaigns")
    text = models.TextField()
    from_number = models.CharField(max_length=20, blank=True)
    rotate_sims = models.BooleanField(default=False)
    send_at = models.DateTimeField(null=True, blank=True)
    queued = models.BooleanField(default=True)
    callback_url = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, default="running")  # scheduled|running|paused|completed|canceled
    total = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class Message(models.Model):
    STATUS = ["queued", "dispatched", "sent", "delivered", "failed", "expired", "canceled"]
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="messages")
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="messages")
    sim = models.ForeignKey(Sim, on_delete=models.SET_NULL, null=True, related_name="messages")
    to = models.CharField(max_length=20)
    text = models.TextField()
    status = models.CharField(max_length=20, default="queued")
    queued = models.BooleanField(default=False)  # True = send when online
    ttl = models.IntegerField(null=True, blank=True)
    segments = models.IntegerField(default=1)
    idempotency_key = models.CharField(max_length=120, blank=True, default="")
    error_code = models.CharField(max_length=60, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    campaign = models.ForeignKey("Campaign", on_delete=models.CASCADE, null=True, related_name="messages")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    callback_url = models.CharField(max_length=500, blank=True, default="")
    is_test = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["account", "idempotency_key"],
                condition=models.Q(idempotency_key__gt=""),
                name="uniq_account_idempotency",
            )
        ]


class PairingCode(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="pairing_codes")
    code = models.CharField(max_length=32, unique=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Webhook(models.Model):
    account = models.OneToOneField(Account, on_delete=models.CASCADE, related_name="webhook")
    url = models.CharField(max_length=500, blank=True)
    secret = models.CharField(max_length=64)
    events = models.JSONField(default=list)  # ["message.sent","message.delivered","message.failed","message.expired"]
    enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class WebhookDelivery(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="webhook_deliveries")
    event_id = models.CharField(max_length=64, unique=True)
    event = models.CharField(max_length=40)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, null=True)
    url = models.CharField(max_length=500)
    payload = models.JSONField()
    attempts = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default="pending")  # pending|delivered|failed
    next_retry_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AuditLog(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="audit_logs", null=True)
    actor = models.CharField(max_length=40)  # system|device|key|user|admin
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=120, blank=True)
    ip = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
