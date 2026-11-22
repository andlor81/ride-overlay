"""Listen-only ANT+ reader: prints trainer power/cadence and heart rate."""

import threading
import time
from collections import deque
from dataclasses import dataclass

import usb.core  # type: ignore
from openant.base.driver import DriverNotFound  # type: ignore
from openant.devices import ANTPLUS_NETWORK_KEY  # type: ignore
from openant.devices.fitness_equipment import FitnessEquipment  # type: ignore
from openant.devices.heart_rate import HeartRate  # type: ignore
from openant.easy.exception import AntException
from openant.easy.node import Node  # type: ignore

POWER_WINDOW = 3.0  # seconds averaged for the power display
STALE_AFTER = 3.0  # seconds without new data before a value counts as missing
STARTUP_ATTEMPTS = 3

# USB IDs of the ANT+ sticks openant supports: ANT USB2 and ANT USB-m
STICK_USB_IDS = ((0x0FCF, 0x1008), (0x0FCF, 0x1009))

class StickError(Exception):
    """The ANT+ stick is missing, busy or not answering."""


def stick_present() -> bool:
    """True if an ANT+ USB stick is plugged in (looks at the USB bus only)."""
    return any(
        usb.core.find(idVendor=vendor, idProduct=product) is not None
        for vendor, product in STICK_USB_IDS
    )


class TrackingFitnessEquipment(FitnessEquipment):
    """FE-C channel opened as a normal (tracking) channel.

    openant opens every channel with ext_assign=0x01 (background scanning).
    Such a channel keeps searching instead of locking onto the device and
    receives only about every 13th message. ext_assign=None fixes that.
    """

    def open_channel(self, extended=True, channel_type=None, ext_assign=None):
        super().open_channel(extended=extended, channel_type=channel_type, ext_assign=None)


class TrackingHeartRate(HeartRate):
    """Heart rate channel opened as a normal (tracking) channel (see above)."""

    def open_channel(self, extended=True, channel_type=None, ext_assign=None):
        super().open_channel(extended=extended, channel_type=channel_type, ext_assign=None)


@dataclass
class Snapshot:
    """A consistent copy of the latest values. None means no recent data."""

    power: int | None
    cadence: int | None
    hr: int | None


class AntReader:
    def __init__(self, trainer_id: int, hr_id: int) -> None:
        self._trainer_id = trainer_id
        self._hr_id = hr_id
        self._lock = threading.Lock()
        self._power_samples: deque[tuple[float, int]] = deque()  # (time, watts)
        self._cadence = 0
        self._hr = 0
        self._trainer_time = 0.0  # when trainer data last arrived
        self._hr_time = 0.0  # when heart rate data last arrived
        self._node: Node | None = None
        self._devices: tuple = ()

    # --- Called on the ANT+ thread ---------------------------------------

    def _on_trainer_data(self, page: int, page_name: str, data) -> None:
        if page_name != "standard_power":  # FE-C data page 0x19
            return
        now = time.monotonic()
        with self._lock:
            self._power_samples.append((now, data.instantaneous_power))
            self._cadence = data.cadence
            self._trainer_time = now

    def _on_hr_data(self, page: int, page_name: str, data) -> None:
        with self._lock:
            self._hr = data.heart_rate
            self._hr_time = time.monotonic()

    # --- Called on the main thread ---------------------------------------

    def start(self) -> None:
        """Open the stick, retrying if it doesn't answer. Raises StickError on failure."""
        for attempt in range(1, STARTUP_ATTEMPTS + 1):
            try:
                self._open()
                return
            except DriverNotFound:
                raise StickError("No ANT+ USB stick found.\nPlug it in and try again.") from None
            except usb.core.USBError as error:
                raise StickError(
                    f"The ANT+ stick can't be opened ({error}).\n"
                    "Is Garmin Express or another training app using it? Quit it and try again."
                ) from None
            except AntException:
                print(f"ANT+ stick did not answer (attempt {attempt} of {STARTUP_ATTEMPTS})")
                self.stop()
        raise StickError("The ANT+ stick does not answer.\nUnplug it, plug it back in, and try again.")
    
    def _open(self) -> None:
        self._node = Node()  # opens the ANT+ USB stick
        self._node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)

        trainer = TrackingFitnessEquipment(self._node, device_id=self._trainer_id)
        hr = TrackingHeartRate(self._node, device_id=self._hr_id)
        trainer.on_device_data = self._on_trainer_data
        hr.on_device_data = self._on_hr_data
        self._devices = (trainer, hr)  # keep references so the channels stay alive

        # node.start() blocks forever, so it gets its own thread
        thread = threading.Thread(target=self._node.start, name="ant-reader", daemon=True)
        thread.start()

    def stop(self) -> None:
        if self._node is None:
            return
        try:
            # A reset closes all channels at once, so the stick stops streaming
            # data that could confuse the next start
            self._node.ant.reset_system()
        except Exception:
            pass  # the stick may not be responding; we are shutting down anyway
        try:
            self._node.stop()  # ends openant's threads and releases the USB device
        except Exception:
            pass  # the stick may have been unplugged; nothing left to release
        self._node = None

    def snapshot(self) -> Snapshot:
        now = time.monotonic()
        with self._lock:
            # Drop power samples older than the averaging window
            while self._power_samples and now - self._power_samples[0][0] > POWER_WINDOW:
                self._power_samples.popleft()

            trainer_ok = now - self._trainer_time < STALE_AFTER
            hr_ok = now - self._hr_time < STALE_AFTER

            power = None
            if trainer_ok and self._power_samples:
                watts = [w for _, w in self._power_samples]
                power = round(sum(watts) / len(watts))

            return Snapshot(
                power=power,
                cadence=self._cadence if trainer_ok else None,
                hr=self._hr if hr_ok else None,
            )