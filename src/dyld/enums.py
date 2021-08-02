from enum import Enum


class PlatformType(Enum):
    MACOS = 1
    IOS = 2
    TVOS = 3
    WATCHOS = 4
    BRIDGEOS = 5
    MACCATALYST = 6
    IOSSIMULATOR = 7
    TVOSSIMULATOR = 8
    WATCHOSSIMULATOR = 9
    DRIVERKIT = 10


class ToolType(Enum):
    CLANG = 1
    SWIFT = 2
    LD = 3
