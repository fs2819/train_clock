"""Fetches and parses MTA GTFS-Realtime data.

Translated from SubwayTimeService/handler/main.go (refreshTimes + translateEntities).
"""

import logging
import time
from dataclasses import dataclass, field

import requests
from google.transit import gtfs_realtime_pb2

from config import FEED_URL, STATION_ID, STATION_NAME, ROUTE_ID

logger = logging.getLogger(__name__)

# GTFS-Realtime StopTimeUpdate.ScheduleRelationship value for a stop the trip
# will not serve (== 1). Resolved from the protobuf enum rather than hardcoded.
_SKIPPED = gtfs_realtime_pb2.TripUpdate.StopTimeUpdate.ScheduleRelationship.SKIPPED


@dataclass
class PredictedArrival:
    unix_time: int
    human_time: str
    minutes_to_arrival: float


@dataclass
class StationTimes:
    route: str
    station: str
    arrivals: list[PredictedArrival] = field(default_factory=list)
    fetch_timestamp: int = 0


def fetch_feed() -> gtfs_realtime_pb2.FeedMessage:
    """Fetch the GTFS-Realtime protobuf feed from the MTA."""
    logger.info("Fetching MTA feed from %s", FEED_URL)
    response = requests.get(FEED_URL, timeout=10)
    response.raise_for_status()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)
    return feed


def parse_feed(feed: gtfs_realtime_pb2.FeedMessage) -> StationTimes:
    """Parse the feed and extract arrival times for our station/route.

    Mirrors translateEntities() from the Go code — filters entities by
    route ID and stop ID prefix, then builds a sorted list of upcoming arrivals.
    """
    arrivals: list[PredictedArrival] = []
    now = time.time()

    for entity in feed.entity:
        trip_update = entity.trip_update
        if not trip_update:
            continue

        route_id = trip_update.trip.route_id
        if route_id != ROUTE_ID:
            continue

        for stop_time_update in trip_update.stop_time_update:
            stop_id = stop_time_update.stop_id
            if not stop_id.startswith(STATION_ID):
                continue

            # Skip stops the trip explicitly won't serve (e.g. downtown service
            # routed express past 125th). SKIPPED == 1 in GTFS-Realtime's
            # StopTimeUpdate.ScheduleRelationship enum.
            if stop_time_update.schedule_relationship == _SKIPPED:
                logger.info(
                    "%s train SKIPPING %s — not counted",
                    ROUTE_ID,
                    STATION_NAME,
                )
                continue

            arrival_time = stop_time_update.arrival.time
            if arrival_time <= 0:
                continue

            minutes = (arrival_time - now) / 60.0
            if minutes < 0:
                continue

            human_time = time.strftime(
                "%a %b %d %H:%M:%S %Z", time.localtime(arrival_time)
            )
            arrivals.append(
                PredictedArrival(
                    unix_time=arrival_time,
                    human_time=human_time,
                    minutes_to_arrival=round(minutes, 1),
                )
            )
            logger.info(
                "%s train at %s arriving %s (%.1f min)",
                ROUTE_ID,
                STATION_NAME,
                human_time,
                minutes,
            )

    arrivals.sort(key=lambda a: a.minutes_to_arrival)
    return StationTimes(
        route=ROUTE_ID,
        station=STATION_ID,
        arrivals=arrivals,
        fetch_timestamp=int(now),
    )


def get_next_arrivals() -> StationTimes:
    """Convenience: fetch + parse in one call."""
    feed = fetch_feed()
    return parse_feed(feed)
