"""Floating overlay window for macOS (AppKit via PyObjC)."""

import random
import signal
import time

import AppKit
import Quartz  # noqa: F401  (teaches PyObjC the CGColorRef type)
from Foundation import NSTimer
from PyObjCTools import AppHelper

COLUMS = 4  # power, cadence, heart rate, time
WIDTH, HEIGHT = 520, 60
MARGIN = 20 # distance from the screen's top-righ corner
POSITION_KEY = "OverlayOrigin"  # where the position is saved in the user defaults


def _make_label(x: float) -> AppKit.NSTextField:
    """A white, centered, read-only text label at horizontal position x."""
    label = AppKit.NSTextField.labelWithString_("--")
    label.setFont_(
        AppKit.NSFont.monospacedDigitSystemFontOfSize_weight_(26, AppKit.NSFontWeightSemibold)
    )
    label.setTextColor_(AppKit.NSColor.whiteColor())
    label.setAlignment_(AppKit.NSTextAlignmentCenter)
    label.setFrame_(AppKit.NSMakeRect(x, 12, WIDTH / COLUMS, 36))
    return label

def _fmt(value: int | None, unit: str) -> str:
    """'152 W', or '--' when there is no value."""
    return "--" if value is None else f"{value} {unit}"

class Overlay:
    def __init__(self) -> None:
        # Top-right corner of the main screen (macOS y-axis points UP)
        screen = AppKit.NSScreen.mainScreen().visibleFrame()
        x = screen.origin.x + screen.size.width - WIDTH - MARGIN
        y = screen.origin.y + screen.size.height - HEIGHT - MARGIN

        self._default_origin = (x, y)

        # Use the position saved last time, if there is one
        saved = AppKit.NSUserDefaults.standardUserDefaults().arrayForKey_(POSITION_KEY)
        if saved is not None and len(saved) == 2:
            x, y = float(saved[0]), float(saved[1])

        # A borderless panel that never takes focus away from Apple TV
        self.panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(x, y, WIDTH, HEIGHT),
            AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel,
            AppKit.NSBackingStoreBuffered,
            False
        )
        # Float above normal windows, on every Space, including full-screen ones
        self.panel.setLevel_(AppKit.NSStatusWindowLevel)
        self.panel.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        self.panel.setHidesOnDeactivate_(False)  # panels hide by default when the app loses focus
        self.panel.setMovableByWindowBackground_(True)
        # Transparent window, with a rounded semi-transparent black background
        self.panel.setOpaque_(False)
        self.panel.setBackgroundColor_(AppKit.NSColor.clearColor())
        self.panel.setHasShadow_(False)
        content = self.panel.contentView()
        content.setWantsLayer_(True)
        content.layer().setBackgroundColor_(
            AppKit.NSColor.colorWithWhite_alpha_(0.0, 0.55).CGColor()
        )
        content.layer().setCornerRadius_(14)

        # Three labels side by side: power, cadence, heart rate
        column = WIDTH / COLUMS
        self.power = _make_label(0 * column)
        self.cadence = _make_label(1 * column)
        self.hr = _make_label(2 * column)
        self.time = _make_label(3 * column)
        for label in (self.power, self.cadence, self.hr, self.time):
            content.addSubview_(label)

    def show(self) -> None:
        self.panel.orderFrontRegardless()

    def set_click_through(self, enabled: bool) -> None:
        """When enabled, mouse clicks go to the window below (e.g. the video)."""
        self.panel.setIgnoresMouseEvents_(enabled)

    def reset_position(self) -> None:
        self.panel.setFrameOrigin_(self._default_origin)

    def save_position(self) -> None:
        origin = self.panel.frame().origin
        AppKit.NSUserDefaults.standardUserDefaults().setObject_forKey_(
            [origin.x, origin.y], POSITION_KEY
        )

    def update(
        self,
        power: int | None,
        cadence: int | None,
        hr: int | None,
        seconds: int,
        power_color: AppKit.NSColor,
        hr_color: AppKit.NSColor,    
    ) -> None:
        self.power.setStringValue_(_fmt(power, "W"))
        self.power.setTextColor_(power_color)
        self.cadence.setStringValue_(_fmt(cadence, "rpm"))
        self.hr.setStringValue_(_fmt(hr, "bpm"))
        self.hr.setTextColor_(hr_color)

        minutes, secs = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        self.time.setStringValue_(f"{hours}:{minutes:02d}:{secs:02d}")

def demo() -> None:
    """Show the overlay with random numbers, updated every second."""
    app = AppKit.NSApplication.sharedApplication()
    # Accessory app: no Dock icon, no menu bar, never steals focus
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    overlay = Overlay()
    overlay.show()
    start = time.monotonic()

    def tick(timer) -> None:
        overlay.update(
            random.randint(140, 260),
            random.randint(80, 95),
            random.randint(120, 150),
            int(time.monotonic() - start),
            AppKit.NSColor.whiteColor(),
            AppKit.NSColor.whiteColor(),
        )

    signal.signal(signal.SIGINT, lambda signum, frame: AppHelper.stopEventLoop())

    NSTimer.scheduledTimerWithTimeInterval_repeats_block_(1.0, True, tick)
    AppHelper.runEventLoop(installInterrupt=False)

    
if __name__ == "__main__":
    demo()