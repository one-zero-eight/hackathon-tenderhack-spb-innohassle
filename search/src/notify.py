from __future__ import annotations

import os
import subprocess
import sys

MACBOOK = os.getenv("MACBOOK", "false").lower() in {"1", "true", "yes"}


def notify_captcha() -> None:
    if not MACBOOK or sys.platform != "darwin":
        return

    subprocess.run(
        [
            "osascript",
            "-e",
            (
                'display notification "Solve captcha in the CloakBrowser window" '
                'with title "Yandex Search" sound name "Glass"'
            ),
        ],
        check=False,
    )
