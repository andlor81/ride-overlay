# ride-overlay

A small floating macOS overlay that shows live indoor-ride data (power, cadence, heart rate) on top of whatever you're watching, such as Apple TV, YouTube or Netflix.

It **only listens** to ANT+ broadcasts from your trainer and heart rate sensor, so it runs alongside whatever is controlling the trainer (for example a Garmin watch or bike computer) without interfering.

> 🚧 Work in progress, built step by step as a learning project.

## Requirements

- macOS
- Python 3.10+
- An ANT+ USB stick (tested with Garmin ANT USBStick2)

```bash
git clone https://github.com/andlor81/ride-overlay.git
cd ride-overlay
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
ride-overlay
```

## Tested with

- Tacx Flux S (ANT+ FE-C), controlled by a Garmin Forerunner 970
- Garmin watch heart rate broadcast

## License

MIT