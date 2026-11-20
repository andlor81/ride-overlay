"""Ride overlay: live ANT+ data in a floating window."""

import signal
import time

import AppKit
from Foundation import NSTimer
from PyObjCTools import AppHelper

from ride_overlay.ant_reader import AntReader
from ride_overlay.overlay import Overlay

REFRESH = 0.25  # seconds between window updates

# Placeholder values: replace them with your own.
FTP = 200  # watts

# Lower limit of each power zone in % of FTP (classic 7-zone model), and its color
POWER_ZONES = [
    (0, AppKit.NSColor.systemGrayColor()),  # zone 1: active recovery
    (56, AppKit.NSColor.systemBlueColor()),  # zone 2: endurance
    (76, AppKit.NSColor.systemGreenColor()),  # zone 3: tempo
    (91, AppKit.NSColor.systemYellowColor()),  # zone 4: threshold
    (106, AppKit.NSColor.systemOrangeColor()),  # zone 5: VO2max
    (121, AppKit.NSColor.systemRedColor()),  # zone 6: anaerobic
    (151, AppKit.NSColor.systemPurpleColor()),  # zone 7: neuromuscular
]

# Lower limit (bpm) of each heart rate zone, and its color.
HR_ZONES = [
    (0, AppKit.NSColor.whiteColor()),  # below zone 1
    (110, AppKit.NSColor.systemGrayColor()),  # zone 1
    (130, AppKit.NSColor.systemBlueColor()),  # zone 2
    (145, AppKit.NSColor.systemGreenColor()),  # zone 3
    (160, AppKit.NSColor.systemOrangeColor()),  # zone 4
    (172, AppKit.NSColor.systemRedColor()),  # zone 5
]



def zone_color(value: float | None, zones: list) -> AppKit.NSColor:
    """Color of the zone that hr falls into (white if unknown)."""
    color = AppKit.NSColor.whiteColor()
    if value is not None:
        for lower, zone_color in HR_ZONES:
            if value >= lower:
                color = zone_color
    return color

def run() -> None:
    app = AppKit.NSApplication.sharedApplication()
    # Accessory app: no Dock icon, no menu bar, never steals focus
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    overlay = Overlay()
    overlay.show()

    reader = AntReader()
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

        power_percent = None if snap.power is None else snap.power * 100 / FTP
        overlay.update(
            snap.power,
            snap.cadence,
            snap.hr,
            int(moving_time),
            power_color=zone_color(power_percent, POWER_ZONES),
            hr_color=zone_color(snap.hr, HR_ZONES)    
        )

    def quit_app(signum, frame) -> None:
        reader.stop()  # release the ANT+ stick cleanly
        AppHelper.stopEventLoop()  # end the app

    # Our own Ctrl+C handler: runs at the next timer tick (within 250 ms)
    signal.signal(signal.SIGINT, quit_app)

    NSTimer.scheduledTimerWithTimeInterval_repeats_block_(REFRESH, True, tick)
    AppHelper.runEventLoop(installInterrupt=False)