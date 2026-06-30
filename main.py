"""Entry point for the analog subway clock.

Polls MTA data and updates the clock hands on a loop.
"""

import logging
import signal
import sys
import time

from config import POLL_INTERVAL_SECONDS, LOG_LEVEL
from subway_times import get_next_train_minutes
from clock_controller import update_clock_hands, shutdown as shutdown_clock

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

running = True


def handle_shutdown(signum, frame):
    global running
    logger.info("Shutting down...")
    running = False


signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def main():
    logger.info("Analog subway clock starting")
    logger.info("Polling every %d seconds", POLL_INTERVAL_SECONDS)

    while running:
        try:
            trains = get_next_train_minutes()
            display = [
                f"{m:.1f}" if m is not None else "—" for m in trains
            ]
            logger.info("Next 3 trains (min): %s", display)

            update_clock_hands(trains)

        except Exception:
            logger.exception("Error in main loop")

        time.sleep(POLL_INTERVAL_SECONDS)

    shutdown_clock()
    logger.info("Goodbye")


if __name__ == "__main__":
    main()
