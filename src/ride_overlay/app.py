"""Ride overlay: live ANT+ data in a floating window."""

import signal
import time

import AppKit
from Foundation import NSTimer
from PyObjCTools import AppHelper

from ride_overlay import config as config_file
from ride_overlay.ant_reader import AntReader
from ride_overlay.config import ConfigError, Zone
from ride_overlay.overlay import Overlay

REFRESH = 0.25  # seconds between window updates

# Color names used in the config file -> macOS system colors
NS_COLORS = {
    "white": AppKit.NSColor.whiteColor(),
    "gray": AppKit.NSColor.systemGrayColor(),
    "blue": AppKit.NSColor.systemBlueColor(),
    "green": AppKit.NSColor.systemGreenColor(),
    "yellow": AppKit.NSColor.systemYellowColor(),
    "orange": AppKit.NSColor.systemOrangeColor(),
    "red": AppKit.NSColor.systemRedColor(),
    "purple": AppKit.NSColor.systemPurpleColor(),
    "pink": AppKit.NSColor.systemPinkColor(),
    "teal": AppKit.NSColor.systemTealColor(),
}


def zone_color(value: float | None, zones: list[Zone]) -> AppKit.NSColor:
    """Color of the zone that value falls into (white if unknown)."""
    color_name = "white"
    if value is not None:
        for zone in zones:
            if value >= zone.lower:
                color_name = zone.color
    return NS_COLORS[color_name]


def run() -> None:
    try:
        config = config_file.load()
    except ConfigError as error:
        print(f"Config error: {error}")
        raise SystemExit(1) from None

    app = AppKit.NSApplication.sharedApplication()
    # Accessory app: no Dock icon, no menu bar, never steals focus
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    overlay = Overlay()
    overlay.show()

    reader = AntReader(config.trainer_id, config.hr_id)
    reader.start()

    moving_time = 0.0
    last_tick = time.monotonic()

    def tick(timer) -> None:
        nonlocal moving_time, last_tick
        now = time.monotonic()
        snap = reader.snapshot()
        if snap.cadence:  # pedaling (not None and not 0): the clock runs
            moving_time += now - last_tick
        last_tick = now

        power_percent = None if snap.power is None else snap.power * 100 / config.ftp
        overlay.update(
            snap.power,
            snap.cadence,
            snap.hr,
            int(moving_time),
            power_color=zone_color(power_percent, config.power_zones),
            hr_color=zone_color(snap.hr, config.hr_zones),
        )

    def quit_app(signum, frame) -> None:
        reader.stop()  # release the ANT+ stick cleanly
        AppHelper.stopEventLoop()  # end the app

    # Our own Ctrl+C handler: runs at the next timer tick (within 250 ms)
    signal.signal(signal.SIGINT, quit_app)

    NSTimer.scheduledTimerWithTimeInterval_repeats_block_(REFRESH, True, tick)
    AppHelper.runEventLoop(installInterrupt=False)