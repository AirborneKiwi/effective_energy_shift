from enum import IntEnum

class PacketType(IntEnum):
    EXCESS = 0
    DEFICIT = 1
    BALANCED = 2
    UNDEFINED = 3