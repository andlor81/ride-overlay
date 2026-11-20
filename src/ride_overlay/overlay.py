"""Floating overlay window for macOS (AppKit via PyObjC)."""

import random

import AppKit
from Foundation import NSTimer
from PyObjCTools import AppHelper

WIDTH, HEIGHT = 380, 60
MARGIN = 20 # distance from the screen's top-righ corner


def _make_label(x: float) -> AppKit.NSTextField:
    """A white, centered, read-only text label at horizontal position x."""
    label = AppKit.NSTextField.labelWithString_("--")
    label.setFont_(
        AppKit.NSFont.monospacedDigitSystemFontOfSize_weight_(28, AppKit.NSFontWeightSemibold)
    )
    label.setTextColor_(AppKit.NSColor.whiteColor())
    label.setAlignment_(AppKit.NSTextAlignmentCenter)
    label.setFrame_(AppKit.NSMakeRect(x, 12, WIDTH / 3, 36))
    return label

class Overlay:
    def __init__(self) -> None:
        # Top-right corner of the main screen (macOS y-axis points UP)
        screen = AppKit.NSScreen.mainScreen().visibleFrame()
        x = screen.origin.x + screen.size.width - WIDTH - MARGIN
        y = screen.origin.y + screen.size.height - HEIGHT - MARGIN

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
        third = WIDTH / 3
        self.power = _make_label(0)
        self.cadence = _make_label(third)
        self.hr = _make_label(2 * third)
        for label in (self.power, self.cadence, self.hr):
            content.addSubview_(label)

    def show(self) -> None:
        self.panel.orderFrontRegardless()

    def update(self, power: int, cadence: int, hr: int) -> None:
        self.power.setStringValue_(f"{power} W")
        self.cadence.setStringValue_(f"{cadence} rpm")
        self.hr.setStringValue_(f"{hr} bpm")

def demo() -> None:
    """Show the overlay with random numbers, updated every second."""
    app = AppKit.NSApplication.sharedApplication()
    # Accessory app: no Dock icon, no menu bar, never steals focus
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

    overlay = Overlay()
    overlay.show()

    def tick(timer) -> None:
        overlay.update(
            random.randint(140, 260), random.randint(80, 95), random.randint(120, 150)
        )

    NSTimer.scheduledTimerWithTimeInterval_repeats_block_(1.0, True, tick)
    AppHelper.runEventLoop(installInterrupt=True)  # installInterrupt: Ctrl+C quits

if __name__ == "__main__":
    demo()