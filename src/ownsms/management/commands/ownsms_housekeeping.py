from django.core.management.base import BaseCommand
from django.utils import timezone

from ownsms.services.dispatch import expire_and_reclaim


class Command(BaseCommand):
    help = "Expire TTL-passed queued messages and reclaim leases (run periodically)."

    def handle(self, *args, **opts):
        res = expire_and_reclaim(timezone.now())
        self.stdout.write(f"expired={res['expired']} reclaimed={res['reclaimed']}")
