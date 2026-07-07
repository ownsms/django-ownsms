from django.urls import path

from .views import account as acc_views
from .views import campaigns as camp_views
from .views import device as dev_views
from .views import devices as dev_mgmt_views
from .views import docs as docs_views
from .views import keys as key_views
from .views import messages as msg_views
from .views import registration as reg_views
from .views import webhooks as wh_views

app_name = "ownsms"
urlpatterns = [
    path("api/v1/messages", msg_views.messages),
    path("api/v1/messages/<str:mid>/cancel", msg_views.message_cancel),
    path("api/v1/messages/<str:mid>", msg_views.message_detail),
    path("api/v1/device", dev_views.device_status),
    path("api/v1/device/config", dev_views.device_config),
    path("api/v1/device/register", dev_views.register),
    path("api/v1/device/poll", dev_views.poll),
    path("api/v1/device/heartbeat", dev_views.heartbeat),
    path("api/v1/device/jobs/<str:mid>/status", dev_views.job_status),
    path("api/v1/register", reg_views.register),
    path("api/v1/register/pair", reg_views.pair),
    path("api/v1/devices/pairing-code", reg_views.pairing_code),
    path("api/v1/keys", key_views.keys),
    path("api/v1/keys/<str:kid>/revoke", key_views.key_revoke),
    path("api/v1/devices", dev_mgmt_views.devices),
    path("api/v1/devices/<str:did>/<str:act>", dev_mgmt_views.device_action),
    path("api/v1/campaigns", camp_views.create),
    path("api/v1/campaigns/<str:cid>/messages", camp_views.messages),
    path("api/v1/campaigns/<str:cid>", camp_views.detail),
    path("api/v1/campaigns/<str:cid>/<str:act>", camp_views.action),
    path("api/v1/webhook/deliveries", wh_views.deliveries),
    path("api/v1/webhook", wh_views.webhook),
    path("api/v1/audit", acc_views.audit),
    path("api/v1/openapi.yaml", docs_views.openapi_schema, name="openapi"),
    path("api/v1/docs", docs_views.swagger_ui, name="docs"),
]
