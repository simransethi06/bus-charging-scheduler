"""
models.py — Pure data structures for the bus charging scheduler.
All domain objects live here. No logic, no I/O.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum


class Direction(str, Enum):
    BLR_KCH = "BLR->KCH"
    KCH_BLR = "KCH->BLR"


@dataclass
class Segment:
    """One road segment between two stops."""
    from_stop: str
    to_stop: str
    distance_km: float

    def travel_time_min(self, speed_kmph: float) -> float:
        return (self.distance_km / speed_kmph) * 60


@dataclass
class Station:
    """A charging station along the route."""
    id: str
    name: str
    num_chargers: int = 1
    charger_power: str = "fast"  # future: slow | fast | ultra


@dataclass
class Terminal:
    id: str
    name: str
    slow_charger: bool = True


@dataclass
class Route:
    """Full route definition — direction-agnostic, reversed when needed."""
    id: str
    name: str
    origin: Terminal
    destination: Terminal
    segments: List[Segment]           # ordered BLR→KCH

    def stops_forward(self) -> List[str]:
        """All stops in BLR→KCH order."""
        stops = [self.segments[0].from_stop]
        for seg in self.segments:
            stops.append(seg.to_stop)
        return stops

    def stops_for_direction(self, direction: Direction) -> List[str]:
        stops = self.stops_forward()
        return stops if direction == Direction.BLR_KCH else list(reversed(stops))

    def stations_for_direction(self, direction: Direction, station_ids: List[str]) -> List[str]:
        """Intermediate station IDs in travel order."""
        all_stops = self.stops_for_direction(direction)
        return [s for s in all_stops if s in station_ids]

    def distance_between(self, from_stop: str, to_stop: str) -> float:
        """Distance between two consecutive stops (in either direction)."""
        stops_fwd = self.stops_forward()
        if stops_fwd.index(from_stop) < stops_fwd.index(to_stop):
            segs = self.segments
        else:
            segs = list(reversed(self.segments))
            segs = [Segment(s.to_stop, s.from_stop, s.distance_km) for s in segs]
        
        total = 0.0
        collecting = False
        for seg in segs:
            if seg.from_stop == from_stop:
                collecting = True
            if collecting:
                total += seg.distance_km
            if collecting and seg.to_stop == to_stop:
                break
        return total


@dataclass
class Physics:
    battery_range_km: float = 240.0
    charge_duration_min: float = 25.0
    speed_kmph: float = 60.0
    initial_charge_km: float = 240.0


@dataclass
class Operator:
    id: str
    name: str
    priority_tier: int = 1     # future: higher tier = more priority


@dataclass
class Weights:
    """
    Tunable soft-rule weights.
    Changing a weight = change these values. Nothing else changes.
    """
    individual: float = 1.0   # penalize long waits for a single bus
    operator: float = 1.0     # penalize operator-level variance
    overall: float = 1.0      # penalize total network delay


@dataclass
class Bus:
    id: str
    operator_id: str
    direction: Direction
    departure_time_min: float   # minutes from midnight


@dataclass
class ChargeEvent:
    """A scheduled charge for one bus at one station."""
    bus_id: str
    station_id: str
    arrive_time_min: float      # when bus arrives at station
    queue_start_min: float      # when bus joins queue (= arrive)
    charge_start_min: float     # when charging actually begins
    charge_end_min: float       # when charging finishes (charge_start + 25)

    @property
    def wait_min(self) -> float:
        return self.charge_start_min - self.arrive_time_min


@dataclass
class BusTimeline:
    """Full resolved timeline for one bus."""
    bus: Bus
    charge_events: List[ChargeEvent]
    departure_time_min: float
    arrival_time_min: float     # final arrival at destination

    @property
    def total_wait_min(self) -> float:
        return sum(e.wait_min for e in self.charge_events)

    @property
    def total_trip_min(self) -> float:
        return self.arrival_time_min - self.departure_time_min

    @property
    def stations_used(self) -> List[str]:
        return [e.station_id for e in self.charge_events]


@dataclass
class StationLog:
    """Ordered log of buses that used a station."""
    station_id: str
    events: List[ChargeEvent] = field(default_factory=list)


@dataclass
class ScheduleResult:
    """The full output of one scheduler run."""
    scenario_id: str
    weights: Weights
    bus_timelines: List[BusTimeline]
    station_logs: Dict[str, StationLog]
    is_valid: bool
    violations: List[str] = field(default_factory=list)

    def get_timeline(self, bus_id: str) -> Optional[BusTimeline]:
        for tl in self.bus_timelines:
            if tl.bus.id == bus_id:
                return tl
        return None