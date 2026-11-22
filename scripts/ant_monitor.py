"""Diagnostics: log every ANT+ data page from the trainer and HR strap, with timing.

Run from the project folder:  python scripts/ant_monitor.py
Stop with Ctrl+C.
"""

import time

from openant.base.message import Message
from openant.devices import ANTPLUS_NETWORK_KEY
from openant.devices.fitness_equipment import FitnessEquipment
from openant.devices.heart_rate import HeartRate
from openant.easy.node import Node

from ride_overlay import config as config_file

GAP_WARNING = 1.0  # seconds; longer pauses between pages get marked
TRACKING_CHANNELS = True  # False = openant default (background scanning channels)
LOW_PRIORITY_SEARCH = False  # False = openant default (high-priority search)

config = config_file.load()
start = time.monotonic()
last_seen = {"trainer": start, "hr": start}


def log(device: str, text: str) -> None:
    now = time.monotonic()
    gap = now - last_seen[device]
    last_seen[device] = now
    mark = "   <-- GAP" if gap > GAP_WARNING else ""
    print(f"{now - start:8.2f}s  {device:7}  +{gap:5.2f}s  {text}{mark}")


def on_trainer(page: int, page_name: str, data) -> None:
    if page_name == "standard_power":
        log("trainer", f"0x{page:02X} power  {data.instantaneous_power:4d} W  {data.cadence:3d} rpm")
    elif page_name == "general_fe":
        log("trainer", f"0x{page:02X} general  speed={data.speed} m/s")
    else:
        log("trainer", f"0x{page:02X} {page_name}")


def on_hr(page: int, page_name: str, data) -> None:
    log("hr", f"0x{page:02X} {data.heart_rate} bpm")


class TrackingFitnessEquipment(FitnessEquipment):
    """FE-C channel opened as a normal (tracking) channel, without background scanning."""

    def open_channel(self, extended=True, channel_type=None, ext_assign=None):
        super().open_channel(extended=extended, channel_type=channel_type, ext_assign=None)


class TrackingHeartRate(HeartRate):
    """Heart rate channel opened as a normal (tracking) channel, without background scanning."""

    def open_channel(self, extended=True, channel_type=None, ext_assign=None):
        super().open_channel(extended=extended, channel_type=channel_type, ext_assign=None)


node = Node()
node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)
if TRACKING_CHANNELS:
    trainer = TrackingFitnessEquipment(node, device_id=config.trainer_id)
    hr = TrackingHeartRate(node, device_id=config.hr_id)
else:
    trainer = FitnessEquipment(node, device_id=config.trainer_id)
    hr = HeartRate(node, device_id=config.hr_id)
trainer.on_device_data = on_trainer
hr.on_device_data = on_hr


def use_low_priority_search(device) -> None:
    """Let the channel search without blocking the other channels."""
    channel = device.channel
    channel.set_search_timeout(0)  # high-priority search: off
    node.ant.write_message(  # low-priority search: forever (0xFF)
        Message(Message.ID.LOW_PRIORITY_CHANNEL_SEARCH_TIMEOUT, [channel.id, 0xFF])
    )
    channel.wait_for_response(Message.ID.LOW_PRIORITY_CHANNEL_SEARCH_TIMEOUT)


if LOW_PRIORITY_SEARCH:
    use_low_priority_search(trainer)
    use_low_priority_search(hr)

print("Listening... pedal for a minute, then press Ctrl+C")
try:
    node.start()
except KeyboardInterrupt:
    pass
finally:
    try:
        node.ant.reset_system()
    except Exception:
        pass
    node.stop()