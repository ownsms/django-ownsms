from datetime import timedelta

from django.db import models

from . import conf


class Account(models.Model):
    name = models.CharField("Nom", max_length=200, blank=True)
    email = models.EmailField("Email", blank=True)  # optional (no verification in v1)
    status = models.CharField("Holat", max_length=20, default="active")  # active|suspended
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)

    class Meta:
        verbose_name = "Akkaunt"
        verbose_name_plural = "Akkauntlar"

    def __str__(self):
        return self.name or self.email or f"Akkaunt #{self.pk}"


class Device(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="devices", verbose_name="Akkaunt")
    name = models.CharField("Nom", max_length=200)
    device_token = models.CharField("Qurilma tokeni", max_length=64, unique=True)  # sha256 hex
    app_version = models.CharField("Ilova versiyasi", max_length=40, blank=True)
    status = models.CharField("Holat", max_length=20, default="active")  # active|inactive
    last_seen_at = models.DateTimeField("Oxirgi ko'rinish", null=True, blank=True)
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)

    class Meta:
        verbose_name = "Qurilma"
        verbose_name_plural = "Qurilmalar"

    def __str__(self):
        return f"{self.name} (#{self.pk})"

    def is_online(self, now):
        if not self.last_seen_at:
            return False
        return (now - self.last_seen_at) < timedelta(seconds=conf.get("DEVICE_ONLINE_SECONDS"))


class Sim(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="sims", verbose_name="Qurilma")
    subscription_id = models.IntegerField("Subscription ID")
    number = models.CharField("Raqam", max_length=20)
    operator = models.CharField("Operator", max_length=40, blank=True)
    is_default = models.BooleanField("Standart", default=False)
    rate_per_min = models.IntegerField("Daqiqada", default=15)
    rate_per_hour = models.IntegerField("Soatda", default=200)
    rate_per_day = models.IntegerField("Kunda", default=500)
    jitter_min = models.IntegerField("Tanaffus min (soniya)", default=2)
    jitter_max = models.IntegerField("Tanaffus max (soniya)", default=5)
    work_hours_start = models.TimeField("Ish boshi", null=True, blank=True)
    work_hours_end = models.TimeField("Ish oxiri", null=True, blank=True)
    daily_quota = models.IntegerField("Kunlik kvota", null=True, blank=True)

    class Meta:
        verbose_name = "SIM karta"
        verbose_name_plural = "SIM kartalar"

    def __str__(self):
        label = self.number or f"SIM {self.subscription_id}"
        return f"{label} — {self.operator}" if self.operator else label


class ApiKey(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="api_keys", verbose_name="Akkaunt")
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="api_keys", verbose_name="Qurilma")
    key_hash = models.CharField("Kalit hash", max_length=64, unique=True)
    prefix = models.CharField("Prefiks", max_length=16)
    name = models.CharField("Nom", max_length=200, blank=True)
    scopes = models.JSONField("Ruxsatlar", default=list)  # ["send","read"]
    ip_allowlist = models.JSONField("IP allowlist", default=list)  # [] = unrestricted; ["10.0.0.0/8", "1.2.3.4"]
    is_test = models.BooleanField("Test rejimi", default=False)
    revoked = models.BooleanField("Bekor qilingan", default=False)
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)
    last_used_at = models.DateTimeField("Oxirgi ishlatilgan", null=True, blank=True)

    class Meta:
        verbose_name = "API kalit"
        verbose_name_plural = "API kalitlar"

    def __str__(self):
        label = self.name or self.prefix
        return f"{label} (bekor qilingan)" if self.revoked else label


class Campaign(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="campaigns", verbose_name="Akkaunt")
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="campaigns", verbose_name="Qurilma")
    sim = models.ForeignKey(
        Sim, on_delete=models.SET_NULL, null=True, related_name="campaigns", verbose_name="SIM karta"
    )
    text = models.TextField("Matn")
    from_number = models.CharField("Yuboruvchi raqam", max_length=20, blank=True)
    rotate_sims = models.BooleanField("SIM almashtirish", default=False)
    send_at = models.DateTimeField("Yuborish vaqti", null=True, blank=True)
    queued = models.BooleanField("Navbatga qo'yilgan", default=True)
    callback_url = models.CharField("Callback URL", max_length=500, blank=True)
    # scheduled|running|paused|completed|canceled
    status = models.CharField("Holat", max_length=20, default="running")
    total = models.IntegerField("Jami", default=0)
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)

    class Meta:
        verbose_name = "Rassilka"
        verbose_name_plural = "Rassilkalar"

    def __str__(self):
        return f"Rassilka #{self.pk} ({self.total} ta)"


class Message(models.Model):
    STATUS = ["queued", "dispatched", "sent", "delivered", "failed", "expired", "canceled"]
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="messages", verbose_name="Akkaunt")
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="messages", verbose_name="Qurilma")
    sim = models.ForeignKey(
        Sim, on_delete=models.SET_NULL, null=True, related_name="messages", verbose_name="SIM karta"
    )
    to = models.CharField("Qabul qiluvchi", max_length=20)
    text = models.TextField("Matn")
    status = models.CharField("Holat", max_length=20, default="queued")
    queued = models.BooleanField("Navbatga qo'yilgan", default=False)  # True = send when online
    ttl = models.IntegerField("TTL (soniya)", null=True, blank=True)
    segments = models.IntegerField("Segmentlar", default=1)
    idempotency_key = models.CharField("Idempotency kaliti", max_length=120, blank=True, default="")
    error_code = models.CharField("Xato kodi", max_length=60, blank=True, default="")
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)
    dispatched_at = models.DateTimeField("Jo'natilgan", null=True, blank=True)
    sent_at = models.DateTimeField("Yuborilgan", null=True, blank=True)
    delivered_at = models.DateTimeField("Yetkazilgan", null=True, blank=True)
    lease_expires_at = models.DateTimeField("Lease tugashi", null=True, blank=True)
    campaign = models.ForeignKey(
        "Campaign", on_delete=models.CASCADE, null=True, related_name="messages", verbose_name="Rassilka"
    )
    scheduled_at = models.DateTimeField("Rejalashtirilgan vaqt", null=True, blank=True)
    callback_url = models.CharField("Callback URL", max_length=500, blank=True, default="")
    is_test = models.BooleanField("Test", default=False)

    class Meta:
        verbose_name = "Xabar"
        verbose_name_plural = "Xabarlar"
        constraints = [
            models.UniqueConstraint(
                fields=["account", "idempotency_key"],
                condition=models.Q(idempotency_key__gt=""),
                name="uniq_account_idempotency",
            )
        ]

    def __str__(self):
        return f"→ {self.to} ({self.status})"


class PairingCode(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="pairing_codes", verbose_name="Akkaunt")
    code = models.CharField("Kod", max_length=32, unique=True)
    expires_at = models.DateTimeField("Tugash vaqti")
    used = models.BooleanField("Ishlatilgan", default=False)
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)

    class Meta:
        verbose_name = "Pairing kod"
        verbose_name_plural = "Pairing kodlar"

    def __str__(self):
        return self.code


class Webhook(models.Model):
    account = models.OneToOneField(Account, on_delete=models.CASCADE, related_name="webhook", verbose_name="Akkaunt")
    url = models.CharField("URL", max_length=500, blank=True)
    secret = models.CharField("Secret", max_length=64)
    # ["message.sent","message.delivered","message.failed","message.expired"]
    events = models.JSONField("Hodisalar", default=list)
    enabled = models.BooleanField("Yoqilgan", default=False)
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)

    class Meta:
        verbose_name = "Webhook"
        verbose_name_plural = "Webhooklar"

    def __str__(self):
        return f"Webhook — {self.account}"


class WebhookDelivery(models.Model):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="webhook_deliveries", verbose_name="Akkaunt"
    )
    event_id = models.CharField("Hodisa ID", max_length=64, unique=True)
    event = models.CharField("Hodisa", max_length=40)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, null=True, verbose_name="Xabar")
    url = models.CharField("URL", max_length=500)
    payload = models.JSONField("Payload")
    attempts = models.IntegerField("Urinishlar", default=0)
    status = models.CharField("Holat", max_length=20, default="pending")  # pending|delivered|failed
    next_retry_at = models.DateTimeField("Keyingi urinish", null=True, blank=True)
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)

    class Meta:
        verbose_name = "Webhook yetkazish"
        verbose_name_plural = "Webhook yetkazishlar"

    def __str__(self):
        return f"{self.event} → {self.status}"


class AuditLog(models.Model):
    account = models.ForeignKey(
        Account, on_delete=models.CASCADE, related_name="audit_logs", null=True, verbose_name="Akkaunt"
    )
    actor = models.CharField("Bajaruvchi", max_length=40)  # system|device|key|user|admin
    action = models.CharField("Amal", max_length=60)
    target = models.CharField("Obyekt", max_length=120, blank=True)
    ip = models.CharField("IP", max_length=64, blank=True)
    created_at = models.DateTimeField("Vaqt", auto_now_add=True)

    class Meta:
        verbose_name = "Audit yozuvi"
        verbose_name_plural = "Audit jurnali"

    def __str__(self):
        return f"{self.action} — {self.actor}"
