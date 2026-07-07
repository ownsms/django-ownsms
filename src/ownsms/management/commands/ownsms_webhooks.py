from django.core.management.base import BaseCommand

from ownsms.services import webhooks


class Command(BaseCommand):
    help = "Deliver pending webhooks (run periodically)."

    def handle(self, *args, **opts):
        self.stdout.write(f"delivered={webhooks.send_pending()}")
