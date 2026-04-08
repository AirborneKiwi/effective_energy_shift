from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List

from decorator_registry import register_after, register_before

from efes_core.domain.enums import PacketType
from mefes.application.use_cases import MefesImplementation

from mefes.domain.models import EnergyPacketLane, MefesState, PhaseGroup, PhasePair, EnergyPacket
from mefes.domain.services import PhaseGroupService, PhasePairService

ENABLED: bool = False
decorator_group = __file__
targets = [EnergyPacketLane, PhasePairService, MefesImplementation, PhaseGroupService, PhaseGroup]

def _enabled() -> bool:
    return ENABLED


class EventType(Enum):
    APPEND_EXCESS = auto()
    APPEND_DEFICIT = auto()
    APPEND_BALANCED = auto()

    APPEND_LEFT_EXCESS = auto()
    APPEND_LEFT_DEFICIT = auto()
    APPEND_LEFT_BALANCED = auto()

    POP_EXCESS = auto()
    POP_DEFICIT = auto()
    POP_BALANCED = auto()

    POP_LEFT_EXCESS = auto()
    POP_LEFT_DEFICIT = auto()
    POP_LEFT_BALANCED = auto()

    NEXT_ITERATION = auto()

    BALANCE_STEP = auto()

    BALANCE_GROUP = auto()
    BALANCE_OBSOLETE = auto()

    EXCESS_BELOW_DEFICIT = auto()
    DEFICIT_BELOW_EXCESS = auto()

    EXCESS_REMAINING = auto()
    DEFICIT_REMAINING = auto()
    BALANCED_PHASE = auto()

    BALANCED_ABSORBED_AT_TOP = auto()
    BALANCED_ABSORBED_AT_FRONT = auto()
    BALANCED_HOVERS_AT_TOP = auto()
    BALANCED_HOVERS_AT_BOTTOM = auto()

    EXCESS_ABSORBED_AT_TOP = auto()
    EXCESS_ABSORBED_AT_FRONT = auto()
    EXCESS_HOVERS_AT_TOP = auto()
    EXCESS_HOVERS_AT_BOTTOM = auto()

    DEFICIT_ABSORBED_AT_TOP = auto()
    DEFICIT_ABSORBED_AT_FRONT = auto()
    DEFICIT_HOVERS_AT_TOP = auto()
    DEFICIT_HOVERS_AT_BOTTOM = auto()

    EXCESS_RAISED_TO_BALANCED_TOP = auto()
    DEFICIT_RAISED_TO_BALANCED_TOP = auto()
    BALANCED_RAISED_TO_BALANCED_TOP = auto()

    BALANCE_CREATES_HURDLE = auto()

    SHIFT_STEP = auto()

    SHIFT_GROUP = auto()
    SHIFT_GROUP_OBSOLETE = auto()

    SHIFT_PACKET_EXCESS = auto()
    SHIFT_PACKET_DEFICIT = auto()
    HURDLE_JUMP_BY_EXCESS = auto()
    HURDLE_JUMP_BY_DEFICIT = auto()

    MERGE_STEP = auto()

    MERGE_EXC_EXC = auto()
    MERGE_DEF_DEF = auto()
    MERGE_BAL_BAL = auto()
    MERGE_BAL_DEF = auto()
    MERGE_EXC_BAL = auto()

    MERGE_REJECTED_UND = auto()
    MERGE_REJECTED_EXC_DEF = auto()
    MERGE_REJECTED_DEF_EXC = auto()

    MERGE_REJECTED_BAL_EXC = auto()
    MERGE_REJECTED_DEF_BAL = auto()


@dataclass
class Event:
    evt_type: str | EventType
    triggered_by: str
    id: int | None = None


class EventRecorder:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.observed_events: Dict[str, List[Event]] = {evt_type.name: [] for evt_type in EventType}
        self.observed_events_in_order: List[Event] = []
        self.n_observed_events: int = 0

    def reset(self):
        self.observed_events = {evt_type.name: [] for evt_type in EventType}
        self.observed_events_in_order = []
        self.n_observed_events = 0

    def record(self, event: Event):
        if isinstance(event.evt_type, EventType):
            event.evt_type = event.evt_type.name

        if event.evt_type not in self.observed_events:
            self.observed_events[event.evt_type] = []

        event.id = self.n_observed_events
        self.observed_events[event.evt_type].append(event)
        self.observed_events_in_order.append(event)
        self.n_observed_events += 1

    def print_events(self, group_by_type: bool = True, show_all: bool = False, print_trace: bool = False):
        return self.__str__(group_by_type=group_by_type, show_all=show_all, print_trace=print_trace)

    def __str__(self, group_by_type: bool = True, show_all: bool = False, print_trace: bool = False):
        s = ""
        if group_by_type:
            for event_type, events in self.observed_events.items():
                if len(events) > 0 or show_all:
                    s += f"{len(events)} x {event_type} by {[event.triggered_by for event in events]} \n"
            s += "\n---------------------------\n"

        if print_trace:
            for event in self.observed_events_in_order:
                s += f"{event.evt_type} by {event.triggered_by} \n"
            s += "\n---------------------------\n"
        return s


# ------------------------------------------------------------
# small helpers
# ------------------------------------------------------------

def _lane_id(lane: EnergyPacketLane) -> str:
    return lane.id


def _pair_id(pair: PhasePair) -> str:
    return pair.id


def _group_id(group: PhaseGroup) -> str:
    return group.id


# ------------------------------------------------------------
# EnergyPacketLane.pop_left
# ------------------------------------------------------------

@register_before(EnergyPacketLane.pop_left, group=decorator_group, enabled=_enabled)
def rec_evt_pop_left_before(self: EnergyPacketLane):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.POP_LEFT_EXCESS,
        PacketType.DEFICIT: EventType.POP_LEFT_DEFICIT,
        PacketType.BALANCED: EventType.POP_LEFT_BALANCED,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=_lane_id(self)))


@register_after(EnergyPacketLane.pop_left, group=decorator_group, enabled=_enabled)
def rec_evt_pop_left_after(res, self: EnergyPacketLane):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.POP_LEFT_EXCESS,
        PacketType.DEFICIT: EventType.POP_LEFT_DEFICIT,
        PacketType.BALANCED: EventType.POP_LEFT_BALANCED,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=_lane_id(self)))


# ------------------------------------------------------------
# EnergyPacketLane.pop_right
# ------------------------------------------------------------

@register_after(EnergyPacketLane.pop_right, group=decorator_group, enabled=_enabled)
def rec_evt_pop_right_after(res, self: EnergyPacketLane):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.POP_EXCESS,
        PacketType.DEFICIT: EventType.POP_DEFICIT,
        PacketType.BALANCED: EventType.POP_BALANCED,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=_lane_id(self)))


# ------------------------------------------------------------
# EnergyPacketLane.append_packet
# ------------------------------------------------------------

@register_before(EnergyPacketLane.append_packet, group=decorator_group, enabled=_enabled)
def rec_evt_append_packet_before(self: EnergyPacketLane, energy_packet):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.APPEND_EXCESS,
        PacketType.DEFICIT: EventType.APPEND_DEFICIT,
        PacketType.BALANCED: EventType.APPEND_BALANCED,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=_lane_id(self)))


@register_after(EnergyPacketLane.append_packet, group=decorator_group, enabled=_enabled)
def rec_evt_append_packet_after(res, self: EnergyPacketLane, energy_packet: EnergyPacket):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.EXCESS_HOVERS_AT_TOP,
        PacketType.DEFICIT: EventType.DEFICIT_HOVERS_AT_TOP,
        PacketType.BALANCED: EventType.BALANCED_HOVERS_AT_TOP,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=_lane_id(self)))


# ------------------------------------------------------------
# EnergyPacketLane.append_packet_left
# ------------------------------------------------------------

@register_before(EnergyPacketLane.append_packet_left, group=decorator_group, enabled=_enabled)
def rec_evt_append_packet_left_before(self: EnergyPacketLane, energy_packet: EnergyPacket):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.APPEND_LEFT_EXCESS,
        PacketType.DEFICIT: EventType.APPEND_LEFT_DEFICIT,
        PacketType.BALANCED: EventType.APPEND_LEFT_BALANCED,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=_lane_id(self)))


@register_after(EnergyPacketLane.append_packet_left, group=decorator_group, enabled=_enabled)
def rec_evt_append_packet_left_after(res, self: EnergyPacketLane, energy_packet: EnergyPacket):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.EXCESS_HOVERS_AT_BOTTOM,
        PacketType.DEFICIT: EventType.DEFICIT_HOVERS_AT_BOTTOM,
        PacketType.BALANCED: EventType.BALANCED_HOVERS_AT_BOTTOM,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=_lane_id(self)))


# ------------------------------------------------------------
# PhasePairService.balance
# ------------------------------------------------------------

@register_before(PhasePairService.balance, group=decorator_group, enabled=_enabled)
def rec_evt_balance_packets_before(phase_pair: PhasePair):
    EventRecorder().record(Event(evt_type=EventType.BALANCED_PHASE, triggered_by=_pair_id(phase_pair)))


# ------------------------------------------------------------
# MefesImplementation._balance / _merge / _shift
# ------------------------------------------------------------

@register_before(MefesImplementation._balance, group=decorator_group, enabled=_enabled)
def rec_evt_balance_before(self: MefesImplementation):
    EventRecorder().record(Event(evt_type=EventType.BALANCE_STEP, triggered_by=self.state.id))


@register_before(MefesImplementation._merge, group=decorator_group, enabled=_enabled)
def rec_evt_merge_groups_before(self: MefesImplementation):
    EventRecorder().record(Event(evt_type=EventType.MERGE_STEP, triggered_by=self.state.id))


@register_before(MefesImplementation._shift, group=decorator_group, enabled=_enabled)
def rec_evt_shift_groups_before(self: MefesImplementation):
    EventRecorder().record(Event(evt_type=EventType.SHIFT_STEP, triggered_by=self.state.id))


@register_before(MefesImplementation.execute, group=decorator_group, enabled=_enabled)
def rec_evt_next_iteration_before(self: MefesImplementation):
    EventRecorder().reset()


# ------------------------------------------------------------
# PhaseGroupService.balance_group
# ------------------------------------------------------------

@register_before(PhaseGroupService.balance_group, group=decorator_group, enabled=_enabled)
def rec_evt_balance_group_before(group: PhaseGroup, state: MefesState):
    already_balanced = group.group_type == PacketType.BALANCED
    setattr(group, "__dec_already_balanced", already_balanced)

    if already_balanced:
        EventRecorder().record(Event(evt_type=EventType.BALANCE_OBSOLETE, triggered_by=_group_id(group)))
    else:
        EventRecorder().record(Event(evt_type=EventType.BALANCE_GROUP, triggered_by=_group_id(group)))


@register_after(PhaseGroupService.balance_group, group=decorator_group, enabled=_enabled)
def rec_evt_balance_group_after(_res, group: PhaseGroup, state: MefesState):
    already_balanced = bool(getattr(group, "__dec_already_balanced", False))
    if (not already_balanced) and group.group_type == PacketType.BALANCED:
        EventRecorder().record(Event(evt_type=EventType.BALANCE_CREATES_HURDLE, triggered_by=_group_id(group)))


# ------------------------------------------------------------
# PhaseGroup.merge_with
# ------------------------------------------------------------

@register_after(PhaseGroup.merge_with, group=decorator_group, enabled=_enabled)
def rec_evt_merge_with_after(res, self: PhaseGroup, other: PhaseGroup):
    merged, reason = res

    if not merged:
        evt_mapping = {
            (PacketType.UNDEFINED, PacketType.UNDEFINED): EventType.MERGE_REJECTED_UND,
            (PacketType.UNDEFINED, PacketType.BALANCED): EventType.MERGE_REJECTED_UND,
            (PacketType.UNDEFINED, PacketType.EXCESS): EventType.MERGE_REJECTED_UND,
            (PacketType.UNDEFINED, PacketType.DEFICIT): EventType.MERGE_REJECTED_UND,
            (PacketType.BALANCED, PacketType.UNDEFINED): EventType.MERGE_REJECTED_UND,
            (PacketType.EXCESS, PacketType.UNDEFINED): EventType.MERGE_REJECTED_UND,
            (PacketType.DEFICIT, PacketType.UNDEFINED): EventType.MERGE_REJECTED_UND,
            (PacketType.BALANCED, PacketType.EXCESS): EventType.MERGE_REJECTED_BAL_EXC,
            (PacketType.DEFICIT, PacketType.BALANCED): EventType.MERGE_REJECTED_DEF_BAL,
            (PacketType.EXCESS, PacketType.DEFICIT): EventType.MERGE_REJECTED_EXC_DEF,
            (PacketType.DEFICIT, PacketType.EXCESS): EventType.MERGE_REJECTED_DEF_EXC,
        }
        key = (self.group_type, other.group_type)
        if key in evt_mapping:
            EventRecorder().record(Event(evt_type=evt_mapping[key], triggered_by=_group_id(self)))
    else:
        evt_mapping = {
            (PacketType.BALANCED, PacketType.BALANCED): EventType.MERGE_BAL_BAL,
            (PacketType.EXCESS, PacketType.EXCESS): EventType.MERGE_EXC_EXC,
            (PacketType.DEFICIT, PacketType.DEFICIT): EventType.MERGE_DEF_DEF,
            (PacketType.BALANCED, PacketType.DEFICIT): EventType.MERGE_BAL_DEF,
            (PacketType.EXCESS, PacketType.BALANCED): EventType.MERGE_EXC_BAL,
        }
        key = (self.group_type, other.group_type)
        if key in evt_mapping:
            EventRecorder().record(Event(evt_type=evt_mapping[key], triggered_by=_group_id(self)))


# ------------------------------------------------------------
# PhaseGroupService.shift_group
# ------------------------------------------------------------

@register_before(PhaseGroupService.shift_group, group=decorator_group, enabled=_enabled)
def rec_evt_shift_before(group: PhaseGroup, state: MefesState):
    if group.group_type == PacketType.BALANCED or (
        group.group_type == PacketType.DEFICIT and group.index_start == group.index_end
    ):
        EventRecorder().record(Event(evt_type=EventType.SHIFT_GROUP_OBSOLETE, triggered_by=_group_id(group)))
    else:
        EventRecorder().record(Event(evt_type=EventType.SHIFT_GROUP, triggered_by=_group_id(group)))


# ------------------------------------------------------------
# PhaseGroupService._shift_one_from_to
# ------------------------------------------------------------

@register_before(PhaseGroupService._shift_one_from_to, group=decorator_group, enabled=_enabled)
def rec_evt_shift_one_from_to_before(
    packet_type: PacketType,
    phase_pair_source: PhasePair,
    phase_pair_target: PhasePair,
    capacity_hurdle: float,
):
    evt_mapping = {
        PacketType.EXCESS: EventType.SHIFT_PACKET_EXCESS,
        PacketType.DEFICIT: EventType.SHIFT_PACKET_DEFICIT,
    }
    if packet_type in evt_mapping:
        EventRecorder().record(
            Event(
                evt_type=evt_mapping[packet_type],
                triggered_by=f"{_pair_id(phase_pair_source)}->{_pair_id(phase_pair_target)}",
            )
        )

    energy_packet = phase_pair_source.energy_packets[packet_type].peek_left()
    if energy_packet is not None and energy_packet.starts_below_level(capacity_hurdle):
        evt_mapping2 = {
            PacketType.EXCESS: EventType.HURDLE_JUMP_BY_EXCESS,
            PacketType.DEFICIT: EventType.HURDLE_JUMP_BY_DEFICIT,
        }
        if packet_type in evt_mapping2:
            EventRecorder().record(
                Event(
                    evt_type=evt_mapping2[packet_type],
                    triggered_by=f"{_pair_id(phase_pair_source)}->{_pair_id(phase_pair_target)}",
                )
            )