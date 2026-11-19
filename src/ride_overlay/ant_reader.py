"""Listen-only ANT+ reader: prints trainer power/cadence and heart rate."""

from openant.devices import ANTPLUS_NETWORK_KEY  # type: ignore
from openant.devices.fitness_equipment import FitnessEquipment  # type: ignore
from openant.devices.heart_rate import HeartRate  # type: ignore
from openant.easy.node import Node  # type: ignore

# Device numbers from `openant scan` (0 would mean "first one found")
TRAINER_ID = 20412
HR_ID = 37413


def run() -> None:
    # Latest values, updated by the callbacks below 
    state = {"power": 0, "cadence": 0, "hr": 0}

    def show() -> None:
        # \r jumps back to the start of the line, so the line updates in place
        print(
            f"\r{state['power']:4d} W   {state['cadence']:3d} rpm   {state['hr']:3d} bpm",
            end="",
            flush=True,
        )

    def on_trainer_data(page: int, page_name: str, data) -> None: # type: ignore
        if page_name == "standard_power":   # FE-C data page 0x19
                state["power"] = data.instantaneous_power # type: ignore
                state["cadence"] = data.cadence # type: ignore
                show()

    def on_hr_data(page: int, page_name: str, data) -> None: # type: ignore
        state["hr"] = data.heart_rate # type: ignore
        show()

    node = Node()   # opens the ANT+ USB stick
    node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)

    trainer = FitnessEquipment(node, device_id=TRAINER_ID)
    hr = HeartRate(node, device_id=HR_ID)

    trainer.on_device_data = on_trainer_data
    hr.on_device_data = on_hr_data

    print("Listening... press Ctrl+C to stop")
    try:
         node.start()   #blocks here; callbacks are called from inside
    except KeyboardInterrupt:
         print("\nStopping")
    finally:
        # No per-channel close: openant unassigns before the stick has
        # finished closing (error 21). The stick is reset on every start anyway.
        node.stop()