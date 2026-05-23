"""Общие флаги Chrome для ускорения холодного старта и навигации."""
from __future__ import annotations

from selenium_driverless import webdriver

FAST_STARTUP_ARGS = (
    "--disable-background-networking",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-breakpad",
    "--disable-client-side-phishing-detection",
    "--disable-component-update",
    "--disable-default-apps",
    "--disable-domain-reliability",
    "--disable-hang-monitor",
    "--disable-popup-blocking",
    "--disable-renderer-backgrounding",
    "--disable-sync",
    "--metrics-recording-only",
    "--mute-audio",
    "--no-first-run",
    "--no-default-browser-check",
)


def apply_fast_chrome_args(options: webdriver.ChromeOptions) -> None:
    options.add_arguments(*FAST_STARTUP_ARGS)
