"""Ride overlay: live ANT+ data in a floating window."""

import signal
import time

import AppKit
from Foundation import NSTimer
from PyObjCTools import AppHelper

from ride_overlay import config as config_file
from ride_overlay import menubar
from ride_overlay.ant_reader import AntReader, StickError, stick_present
from ride_overlay.config import ConfigError, Zone
from ride_overlay.overlay import Overlay

REFRESH = 0.25  # seconds between window updates
WATCHDOG_INTERVAL = 2.0  # seconds between checks for the ANT+ stick

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

def show_error(message: str) -> None:
    """Show a macOS alert and wait until the user clicks OK."""
    print(f"Error: {message}")  # still visible when started from the terminal
    AppKit.NSApplication.sharedApplication().activateIgnoringOtherApps_(True)  # alert in front
    alert = AppKit.NSAlert.alloc().init()
    alert.setMessageText_("Ride Overlay can't start")
    alert.setInformativeText_(message)
    alert.setAlertStyle_(AppKit.NSAlertStyleCritical)
    alert.runModal()

def run() -> None:
    app = AppKit.NSApplication.sharedApplication()
    # Accessory app: no Dock icon, no menu bar, never steals focus
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    try:
        config = config_file.load()
    except ConfigError as error:
        show_error(str(error))
        raise SystemExit(1) from None

    reader = AntReader(config.trainer_id, config.hr_id)
    try:
        reader.start()
    except StickError as error:
        show_error(str(error))
        raise SystemExit(1) from None

    overlay = Overlay()
    overlay.show()

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

    stick_ok = True
    seen_count = 0  # consecutive checks that found the stick again

    def watchdog(timer) -> None:
        nonlocal stick_ok, seen_count
        present = stick_present()

        if stick_ok:
            if not present:  # running -> stick lost
                stick_ok = False
                reader.stop()  # also ends openant's receive threads
                overlay.show_message("No ANT+ stick")
            return

        # Stick lost: reconnect once it has been back for two checks in a row
        seen_count = seen_count + 1 if present else 0
        if seen_count < 2:
            return
        try:
            reader.start()
        except StickError:
            seen_count = 0  # not ready yet; try again later
            return
        stick_ok = True  # stick lost -> running
        seen_count = 0
        overlay.clear_message()

    def shutdown() -> None:
        overlay.save_position()  # remembered for the next start
        reader.stop()  # release the ANT+ stick cleanly
        AppHelper.stopEventLoop()  # end the app

    # Menu bar icon; keep the returned objects in a variable so they stay alive
    menu_objects = menubar.install(overlay, shutdown)  # noqa: F841

    # Our own Ctrl+C handler: runs at the next timer tick (within 250 ms)
    signal.signal(signal.SIGINT, lambda signum, frame: shutdown())

    NSTimer.scheduledTimerWithTimeInterval_repeats_block_(REFRESH, True, tick)
    NSTimer.scheduledTimerWithTimeInterval_repeats_block_(WATCHDOG_INTERVAL, True, watchdog)
    AppHelper.runEventLoop(installInterrupt=False)