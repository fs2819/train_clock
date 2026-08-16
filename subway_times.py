"""Subway time service with caching.

Translated from SubwayTimeService/handler/main.go (HandleRequest + prepareResponse).
Instead of DynamoDB, we cache in memory since this runs locally on the Pi.
"""

import logging
import time
from dataclasses import dataclass

from config import CACHE_TTL_SECONDS, NUM_HANDS
from mta_feed import StationTimes, get_next_arrivals

logger = logging.getLogger(__name__)

_cached_times: StationTimes | None = None


@dataclass
class UpcomingTrain:
    """One train a clock hand can follow: a stable ID plus live minutes-away."""

    trip_id: str
    minutes: float


def _refresh_if_stale() -> None:
    """Re-fetch the feed if the cache has aged out. Keeps stale data on error."""
    global _cached_times

    now = time.time()
    cache_expired = (
        _cached_times is None
        or (now - _cached_times.fetch_timestamp) > CACHE_TTL_SECONDS
    )
    if not cache_expired:
        return

    logger.info("Cache expired, refreshing from MTA feed")
    try:
        _cached_times = get_next_arrivals()
    except Exception:
        logger.exception("Failed to fetch MTA data")
        if _cached_times is not None:
            logger.warning("Using stale cached data")


def get_upcoming_trains() -> list[UpcomingTrain]:
    """Every upcoming arrival, soonest first, with minutes recomputed from now.

    Deliberately NOT truncated to NUM_HANDS. The controller assigns hands to
    individual trains and needs to see further down the queue than it has
    hands: when a hand's train arrives, that hand picks up the soonest train
    no other hand is already showing, which lies beyond the NUM_HANDS window.

    Arrival times are absolute, so minutes stay accurate between feed fetches.
    """
    _refresh_if_stale()
    if _cached_times is None:
        return []

    now = time.time()
    trains = [
        UpcomingTrain(trip_id=a.trip_id, minutes=round((a.unix_time - now) / 60.0, 1))
        for a in _cached_times.arrivals
        if (a.unix_time - now) > 0
    ]
    trains.sort(key=lambda t: t.minutes)
    return trains


def get_minutes_to_next_trains() -> list[float]:
    """Minutes until the next NUM_HANDS arrivals, soonest first."""
    return [t.minutes for t in get_upcoming_trains()[:NUM_HANDS]]


def get_next_train_minutes() -> list[float | None]:
    """Minutes for the closest NUM_HANDS trains, padded with None.

    Always returns a list of length NUM_HANDS. Positions without a known
    train are filled with None.
    """
    upcoming = get_minutes_to_next_trains()
    result: list[float | None] = list(upcoming[:NUM_HANDS])
    while len(result) < NUM_HANDS:
        result.append(None)
    return result
