from ..models import AuditLog


def log(account, actor, action, target="", ip=""):
    try:
        AuditLog.objects.create(account=account, actor=actor, action=action, target=target, ip=ip)
    except Exception:
        pass
