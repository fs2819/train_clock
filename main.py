"""Entry point for the analog subway clock.

Polls MTA data and updates the clock hands on a loop.
"""

import logging
import signal
import sys
import time

from config import NUM_HANDS, POLL_INTERVAL_SECONDS, LOG_LEVEL
from subway_times import get_upcoming_trains
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
            # Pass the whole queue, not just NUM_HANDS of it: the controller
            # assigns hands to individual trains and a hand whose train has
            # just arrived picks up one from further down the list.
            upcoming = get_upcoming_trains()
            display = [f"{t.minutes:.1f}" for t in upcoming[:NUM_HANDS]]
            logger.info("Next %d trains (min): %s", NUM_HANDS, display)

            update_clock_hands(upcoming)

        except Exception:
            logger.exception("Error in main loop")

        time.sleep(POLL_INTERVAL_SECONDS)

    shutdown_clock()
    logger.info("Goodbye")


if __name__ == "__main__":
    main()
