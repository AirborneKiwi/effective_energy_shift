from decorator_registry import register_before, register_after
from typing import Dict, List, Any
from dataclasses import dataclass
from enum import Enum, auto

ENABLED: bool = False
decorator_group = __file__
def _enabled() -> bool:
    return ENABLED

from mefes_dataclasses import Context, PhasePair, PhaseGroup, PacketType, EnergyPacket, EnergyPacketLane

class EventType(Enum):
    APPEND_EXCESS = auto(),
    APPEND_DEFICIT = auto(),
    APPEND_BALANCED = auto(),

    APPEND_LEFT_EXCESS = auto(),
    APPEND_LEFT_DEFICIT = auto(),
    APPEND_LEFT_BALANCED = auto(),

    POP_EXCESS = auto(),
    POP_DEFICIT = auto(),
    POP_BALANCED = auto(),

    POP_LEFT_EXCESS = auto(),
    POP_LEFT_DEFICIT = auto(),
    POP_LEFT_BALANCED = auto(),

    NEXT_ITERATION = auto(),

    BALANCE_STEP = auto(),

    BALANCE_GROUP = auto(),
    BALANCE_OBSOLETE = auto(),

    EXCESS_BELOW_DEFICIT = auto(),
    DEFICIT_BELOW_EXCESS = auto(),

    EXCESS_REMAINING = auto(),
    DEFICIT_REMAINING = auto(),
    BALANCED_PHASE = auto(),

    BALANCED_ABSORBED_AT_TOP = auto(),
    BALANCED_ABSORBED_AT_FRONT = auto(),
    BALANCED_HOVERS_AT_TOP = auto(),
    BALANCED_HOVERS_AT_BOTTOM = auto(),

    EXCESS_ABSORBED_AT_TOP = auto(),
    EXCESS_ABSORBED_AT_FONT = auto(),
    EXCESS_HOVERS_AT_TOP = auto(),
    EXCESS_HOVERS_AT_BOTTOM = auto(),

    DEFICIT_ABSORBED_AT_TOP = auto(),
    DEFICIT_ABSORBED_AT_FRONT = auto(),
    DEFICIT_HOVERS_AT_TOP = auto(),
    DEFICIT_HOVERS_AT_BOTTOM = auto(),

    EXCESS_RAISED_TO_BALANCED_TOP = auto(),
    DEFICIT_RAISED_TO_BALANCED_TOP = auto(),
    BALANCED_RAISED_TO_BALANCED_TOP = auto(),

    BALANCE_CREATES_HURDLE = auto(),

    SHIFT_STEP = auto(),

    SHIFT_GROUP = auto(),
    SHIFT_GROUP_OBSOLETE = auto(),

    SHIFT_PACKET_EXCESS = auto(),
    SHIFT_PACKET_DEFICIT = auto(),
    HURDLE_JUMP_BY_EXCESS = auto(),
    HURDLE_JUMP_BY_DEFICIT = auto(),

    MERGE_STEP = auto(),

    MERGE_EXC_EXC = auto(),
    MERGE_DEF_DEF = auto(),
    MERGE_BAL_BAL = auto(),
    MERGE_BAL_DEF = auto(),
    MERGE_EXC_BAL = auto(),

    MERGE_REJECTED_UND = auto(),
    MERGE_REJECTED_EXC_DEF = auto(),
    MERGE_REJECTED_DEF_EXC = auto(),

    MERGE_REJECTED_BAL_EXC = auto(),
    MERGE_REJECTED_DEF_BAL = auto(),


@dataclass
class Event:
    evt_type: str | EventType
    triggered_by:str
    id:int = None


class EventRecorder:
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is  None:
            cls._instance = cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # IMPORTANT: __init__ will run on every call unless guarded
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.observed_events: Dict[str, List[Event]] = {evt_type.name: [] for evt_type in EventType}
        self.observed_events_in_order: List[Event] = []
        self.n_observed_events: int = 0


    def reset(self):
        self.observed_events: Dict[str, List[Event]] = {evt_type.name: [] for evt_type in EventType}
        self.observed_events_in_order: List[Event] = []
        self.n_observed_events: int = 0


    def record(self, event: Event):
        if isinstance(event.evt_type, EventType):
            event.evt_type = event.evt_type.name

        if event.evt_type not in self.observed_events:
            self.observed_events[event.evt_type] = []

        event.id = self.n_observed_events
        self.observed_events[event.evt_type].append(event)
        self.n_observed_events += 1

        self.observed_events_in_order.append(event)
        #print(f'Event {event.evt_type} triggered by {event.triggered_by}')


    def print_events(self, group_by_type:bool=True, show_all=False, print_trace:bool=False):
        return self.__str__(group_by_type=group_by_type, show_all=show_all, print_trace=print_trace)


    def __str__(self, group_by_type:bool=True, show_all=False, print_trace:bool=False):
        s = ''
        if group_by_type:
            for event_type, events in self.observed_events.items():
                if len(events) > 0 or show_all:
                    s += f'{len(events)} x {event_type} by {[event.triggered_by for event in events]} \n'
            s += '\n---------------------------\n'

        # print in id order
        if print_trace:
            for event in self.observed_events_in_order:
                s += f'{event.evt_type} by {event.triggered_by} \n'

            s += '\n---------------------------\n'
        return s


# ------------------------------------------------------------
# EnergyPacketLane.pop_left: record BEFORE and AFTER
# ------------------------------------------------------------

@register_before(EnergyPacketLane.pop_left, group=decorator_group, enabled=_enabled)
def rec_evt_pop_left__before(self, *a, **k):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.POP_LEFT_EXCESS,
        PacketType.DEFICIT: EventType.POP_LEFT_DEFICIT,
        PacketType.BALANCED: EventType.POP_LEFT_BALANCED,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=self.ID))

@register_after(EnergyPacketLane.pop_left, group=decorator_group, enabled=_enabled)
def rec_evt_pop_left__after(self, _res, *a, **k):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.POP_LEFT_EXCESS,
        PacketType.DEFICIT: EventType.POP_LEFT_DEFICIT,
        PacketType.BALANCED: EventType.POP_LEFT_BALANCED,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=self.ID))


# ------------------------------------------------------------
# EnergyPacketLane.pop_right: record AFTER only
# ------------------------------------------------------------

@register_after(EnergyPacketLane.pop_right, group=decorator_group, enabled=_enabled)
def rec_evt_pop_right__after(self, _res, *a, **k):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.POP_EXCESS,
        PacketType.DEFICIT: EventType.POP_DEFICIT,
        PacketType.BALANCED: EventType.POP_BALANCED,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=self.ID))


# ------------------------------------------------------------
# EnergyPacketLane.append_packet: record BEFORE and AFTER
# ------------------------------------------------------------

@register_before(EnergyPacketLane.append_packet, group=decorator_group, enabled=_enabled)
def rec_evt_append_packet__before(self, energy_packet, *a, **k):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.APPEND_EXCESS,
        PacketType.DEFICIT: EventType.APPEND_DEFICIT,
        PacketType.BALANCED: EventType.APPEND_BALANCED,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=self.ID))

@register_after(EnergyPacketLane.append_packet, group=decorator_group, enabled=_enabled)
def rec_evt_append_packet__after(self, _res, energy_packet, *a, **k):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.EXCESS_HOVERS_AT_TOP,
        PacketType.DEFICIT: EventType.DEFICIT_HOVERS_AT_TOP,
        PacketType.BALANCED: EventType.BALANCED_HOVERS_AT_TOP,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=self.ID))


# ------------------------------------------------------------
# EnergyPacketLane.append_packet_left: record BEFORE and AFTER
# ------------------------------------------------------------

@register_before(EnergyPacketLane.append_packet_left, group=decorator_group, enabled=_enabled)
def rec_evt_append_packet_left__before(self, energy_packet, *a, **k):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.APPEND_LEFT_EXCESS,
        PacketType.DEFICIT: EventType.APPEND_LEFT_DEFICIT,
        PacketType.BALANCED: EventType.APPEND_LEFT_BALANCED,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=self.ID))

@register_after(EnergyPacketLane.append_packet_left, group=decorator_group, enabled=_enabled)
def rec_evt_append_packet_left__after(self, _res, energy_packet, *a, **k):
    evt_type_mapping = {
        PacketType.EXCESS: EventType.EXCESS_HOVERS_AT_BOTTOM,
        PacketType.DEFICIT: EventType.DEFICIT_HOVERS_AT_BOTTOM,
        PacketType.BALANCED: EventType.BALANCED_HOVERS_AT_BOTTOM,
    }
    EventRecorder().record(Event(evt_type=evt_type_mapping[self.lane_type], triggered_by=self.ID))


# ------------------------------------------------------------
# PhasePair.balance: BEFORE only
# ------------------------------------------------------------

@register_before(PhasePair.balance, group=decorator_group, enabled=_enabled)
def rec_evt_balance_packets__before(self, *a, **k):
    EventRecorder().record(Event(evt_type=EventType.BALANCED_PHASE, triggered_by=self.ID))


# ------------------------------------------------------------
# Context.balance / merge / shift: BEFORE only
# ------------------------------------------------------------

@register_before(Context.balance, group=decorator_group, enabled=_enabled)
def rec_evt_balance__before(self, *a, **k):
    EventRecorder().record(Event(evt_type=EventType.BALANCE_STEP, triggered_by=self.ID))

@register_before(Context.merge, group=decorator_group, enabled=_enabled)
def rec_evt_merge_groups__before(self, *a, **k):
    EventRecorder().record(Event(evt_type=EventType.MERGE_STEP, triggered_by=self.ID))

@register_before(Context.shift, group=decorator_group, enabled=_enabled)
def rec_evt_shift_groups__before(self, *a, **k):
    EventRecorder().record(Event(evt_type=EventType.SHIFT_STEP, triggered_by=self.ID))


# ------------------------------------------------------------
# PhaseGroup.balance: BEFORE and AFTER, needs per-call state
#   Use an attribute on the instance to avoid shared dict state across calls.
# ------------------------------------------------------------

@register_before(PhaseGroup.balance, group=decorator_group, enabled=_enabled)
def rec_evt_balance_group__before(self, ctx, *a, **k):
    already_balanced = (self.group_type == PacketType.BALANCED)
    setattr(self, "__dec_already_balanced", already_balanced)

    if already_balanced:
        EventRecorder().record(Event(evt_type=EventType.BALANCE_OBSOLETE, triggered_by=self.ID))
    else:
        EventRecorder().record(Event(evt_type=EventType.BALANCE_GROUP, triggered_by=self.ID))

@register_after(PhaseGroup.balance, group=decorator_group, enabled=_enabled)
def rec_evt_balance_group__after(self, _res, ctx, *a, **k):
    already_balanced = bool(getattr(self, "__dec_already_balanced", False))
    if (not already_balanced) and self.group_type == PacketType.BALANCED:
        EventRecorder().record(Event(evt_type=EventType.BALANCE_CREATES_HURDLE, triggered_by=self.ID))


# ------------------------------------------------------------
# PhaseGroup.merge_with: AFTER only (depends on return value)
# ------------------------------------------------------------

@register_after(PhaseGroup.merge_with, group=decorator_group, enabled=_enabled)
def rec_evt_merge_with__after(self, res, other, *a, **k):
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
        EventRecorder().record(Event(evt_type=evt_mapping[(self.group_type, other.group_type)], triggered_by=self.ID))
    else:
        evt_mapping = {
            (PacketType.BALANCED, PacketType.BALANCED): EventType.MERGE_BAL_BAL,
            (PacketType.EXCESS, PacketType.EXCESS): EventType.MERGE_EXC_EXC,
            (PacketType.DEFICIT, PacketType.DEFICIT): EventType.MERGE_DEF_DEF,
            (PacketType.BALANCED, PacketType.DEFICIT): EventType.MERGE_BAL_DEF,
            (PacketType.EXCESS, PacketType.BALANCED): EventType.MERGE_EXC_BAL,
        }
        EventRecorder().record(Event(evt_type=evt_mapping[(self.group_type, other.group_type)], triggered_by=self.ID))


# ------------------------------------------------------------
# PhaseGroup.shift: BEFORE only
# ------------------------------------------------------------

@register_before(PhaseGroup.shift, group=decorator_group, enabled=_enabled)
def rec_evt_shift__before(self, ctx, *a, **k):
    if self.group_type == PacketType.BALANCED or (
        self.group_type == PacketType.DEFICIT and self.index_start == self.index_end
    ):
        EventRecorder().record(Event(evt_type=EventType.SHIFT_GROUP_OBSOLETE, triggered_by=self.ID))
    else:
        EventRecorder().record(Event(evt_type=EventType.SHIFT_GROUP, triggered_by=self.ID))


# ------------------------------------------------------------
# PhaseGroup._shift_one_from_to: BEFORE only (may emit 2 events)
# ------------------------------------------------------------

@register_before(PhaseGroup._shift_one_from_to, group=decorator_group, enabled=_enabled)
def rec_evt_shift_one_from_to__before(self, phase_pair_source: PhasePair, phase_pair_target: PhasePair, capacity_hurdle: float, *a, **k):
    evt_mapping = {
        PacketType.EXCESS: EventType.SHIFT_PACKET_EXCESS,
        PacketType.DEFICIT: EventType.SHIFT_PACKET_DEFICIT,
    }
    EventRecorder().record(Event(evt_type=evt_mapping[self.group_type], triggered_by=self.ID))

    energy_packet = phase_pair_source.energy_packets[self.group_type].peek_left()
    if energy_packet.starts_below_level(capacity_hurdle):
        evt_mapping2 = {
            PacketType.EXCESS: EventType.HURDLE_JUMP_BY_EXCESS,
            PacketType.DEFICIT: EventType.HURDLE_JUMP_BY_DEFICIT,
        }
        EventRecorder().record(Event(evt_type=evt_mapping2[self.group_type], triggered_by=self.ID))