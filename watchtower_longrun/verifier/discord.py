"""Discord webhook notifier. URL only from env WTL_DISCORD_WEBHOOK (never in repo)."""
import logging
import os

import requests

LOG = logging.getLogger("wtl.discord")


class Notifier:
    def __init__(self, url=None):
        self.url = url or os.environ.get("WTL_DISCORD_WEBHOOK", "")

    def send(self, content):
        if not self.url:
            LOG.info("[discord disabled] %s", content)
            return False
        for chunk in [content[k:k + 1900] for k in range(0, len(content), 1900)]:
            try:
                requests.post(self.url, json={"content": chunk}, timeout=15).raise_for_status()
            except Exception as e:  # noqa
                LOG.warning("discord post failed: %s", e)
                return False
        return True
