"""Menu bar icon with the overlay's menu."""

from collections.abc import Callable

import AppKit

from ride_overlay.overlay import Overlay

CLICK_THROUGH_KEY = "ClickThrough"  # saved in the user defaults


class MenuHandler(AppKit.NSObject):
    """Receives the menu clicks (Cocoa's target-action pattern).

    Each method name ending in "_" becomes an Objective-C selector ending in ":",
    e.g. quit_ -> "quit:". The menu items call them by that name.
    """

    def toggleClickThrough_(self, sender) -> None:
        enabled = sender.state() != AppKit.NSControlStateValueOn
        sender.setState_(AppKit.NSControlStateValueOn if enabled else AppKit.NSControlStateValueOff)
        self.overlay.set_click_through(enabled)
        AppKit.NSUserDefaults.standardUserDefaults().setBool_forKey_(enabled, CLICK_THROUGH_KEY)

    def resetPosition_(self, sender) -> None:
        self.overlay.reset_position()

    def quit_(self, sender) -> None:
        self.on_quit()


def _menu_item(title: str, action: str, target: MenuHandler) -> AppKit.NSMenuItem:
    item = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
    item.setTarget_(target)
    return item


def install(overlay: Overlay, on_quit: Callable[[], None]) -> tuple:
    """Add the menu bar icon. Keep the returned objects alive, or the icon disappears."""
    handler = MenuHandler.new()
    handler.overlay = overlay
    handler.on_quit = on_quit

    click_through = _menu_item("Click-through (locks position)", "toggleClickThrough:", handler)
    menu = AppKit.NSMenu.alloc().init()
    menu.addItem_(click_through)
    menu.addItem_(_menu_item("Reset position", "resetPosition:", handler))
    menu.addItem_(AppKit.NSMenuItem.separatorItem())
    menu.addItem_(_menu_item("Quit Ride Overlay", "quit:", handler))

    status_item = AppKit.NSStatusBar.systemStatusBar().statusItemWithLength_(
        AppKit.NSVariableStatusItemLength
    )
    image = AppKit.NSImage.imageWithSystemSymbolName_accessibilityDescription_(
        "bicycle", "Ride Overlay"
    )
    if image is not None:
        status_item.button().setImage_(image)
    else:
        status_item.button().setTitle_("Ride")  # older macOS without SF Symbols
    status_item.setMenu_(menu)

    # Restore click-through from last time
    if AppKit.NSUserDefaults.standardUserDefaults().boolForKey_(CLICK_THROUGH_KEY):
        click_through.setState_(AppKit.NSControlStateValueOn)
        overlay.set_click_through(True)

    return status_item, handler