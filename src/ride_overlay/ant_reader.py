"""Listen-only ANT+ reader: prints trainer power/cadence and heart rate."""

import threading
import time
from collections import deque
from dataclasses import dataclass

from openant.devices import ANTPLUS_NETWORK_KEY  # type: ignore
from openant.devices.fitness_equipment import FitnessEquipment  # type: ignore
from openant.devices.heart_rate import HeartRate  # type: ignore
from openant.easy.exception import AntException
from openant.easy.node import Node  # type: ignore

# Device numbers from `openant scan` (0 would mean "first one found")
TRAINER_ID = 20412
HR_ID = 37413

POWER_WINDOW = 3.0  # seconds averaged for the power display
STALE_AFTER = 3.0  # seconds without new data before a value counts as missing
STARTUP_ATTEMPTS = 3

@dataclass
class Snapshot:
    """A consistent copy of the latest values. None means no recent data."""

    power: int | None
    cadence: int | None
    hr: int | None


class AntReader:
    def __init__(self) -> None:
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
        """Open the stick, retrying if it doesn't answer."""
        for attempt in range(1, STARTUP_ATTEMPTS + 1):
            try:
                self._open()
                return
            except AntException:
                print(f"ANT+ stick did not answer (attempt {attempt} of {STARTUP_ATTEMPTS})")
                self.stop()
        raise RuntimeError("ANT+ stick did not answer. Unplug it, plug it back in, and try again.")

    def _open(self) -> None:
        self._node = Node()  # opens the ANT+ USB stick
        self._node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)

        trainer = FitnessEquipment(self._node, device_id=TRAINER_ID)
        hr = HeartRate(self._node, device_id=HR_ID)
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
        self._node.stop()
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