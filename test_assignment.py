"""Simulate arrivals and check the hand->train assignment behaves as intended.

Pure logic — no GPIO. Run from the repo root:
    .venv/bin/python test_assignment.py
"""

import sys


import clock_controller as cc
from subway_times import UpcomingTrain

failures = []


def check(label, got, want):
    ok = got == want
    print(f"  {'PASS' if ok else 'FAIL'}  {label}: got {got}, want {want}")
    if not ok:
        failures.append(label)


def assign(trains):
    """trains: list of (trip_id, minutes). Returns list of trip_id per hand."""
    out = cc._assign_trains([UpcomingTrain(t, m) for t, m in trains])
    return [t.trip_id if t else None for t in out]


cc._hand_trip_ids = [None, None, None]

print("\n--- poll 1: fresh start, five trains in the feed ---")
r = assign([("A", 2.0), ("B", 9.0), ("C", 18.0), ("D", 26.0), ("E", 34.0)])
check("hands take the three soonest", r, ["A", "B", "C"])

print("\n--- poll 2: no arrivals, everything just ticks closer ---")
r = assign([("A", 1.0), ("B", 8.0), ("C", 17.0), ("D", 25.0), ("E", 33.0)])
check("hands keep their own trains", r, ["A", "B", "C"])

print("\n--- poll 3: A arrives (drops out of feed) ---")
r = assign([("B", 7.0), ("C", 16.0), ("D", 24.0), ("E", 32.0)])
check("hand1 recycles to furthest shown (D), others undisturbed", r, ["D", "B", "C"])

print("\n--- poll 4: B arrives ---")
r = assign([("C", 15.0), ("D", 23.0), ("E", 31.0), ("F", 39.0)])
check("hand2 recycles to E; hand1 keeps D, hand3 keeps C", r, ["D", "E", "C"])

print("\n--- poll 5: C arrives ---")
r = assign([("D", 22.0), ("E", 30.0), ("F", 38.0), ("G", 46.0)])
check("hand3 recycles to F", r, ["D", "E", "F"])

print("\n--- poll 6: D arrives (hand1 again) — full cycle ---")
r = assign([("E", 29.0), ("F", 37.0), ("G", 45.0)])
check("hand1 recycles to G", r, ["G", "E", "F"])

print("\n--- edge: only two trains left in the whole feed ---")
cc._hand_trip_ids = [None, None, None]
r = assign([("X", 5.0), ("Y", 20.0)])
check("third hand gets nothing", r, ["X", "Y", None])

print("\n--- edge: feed empty (no downtown service) ---")
r = assign([])
check("all hands park", r, [None, None, None])

print("\n--- edge: service returns ---")
r = assign([("Z", 4.0), ("W", 12.0), ("V", 21.0)])
check("hands re-populate soonest-first", r, ["Z", "W", "V"])

print("\n--- edge: two hands freed at once (missed poll) ---")
cc._hand_trip_ids = ["P", "Q", "R"]
r = assign([("R", 3.0), ("S", 11.0), ("T", 19.0), ("U", 28.0)])
check("freed hands take S and T in order, hand3 keeps R", r, ["S", "T", "R"])

print("\n--- edge: a train is delayed past the others (no hand free) ---")
cc._hand_trip_ids = ["A", "B", "C"]
r = assign([("N", 1.0), ("A", 6.0), ("B", 14.0), ("C", 22.0)])
check("hands stay on their trains; new sooner train waits", r, ["A", "B", "C"])

print()
if failures:
    print(f"{len(failures)} FAILURE(S): {failures}")
    sys.exit(1)
print("All assignment checks passed.")
