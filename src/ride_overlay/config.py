"""Load and check the user's configuration file."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "ride-overlay" / "config.toml"

# Color names allowed in the config; the app maps them to macOS system colors
COLORS = ("white", "gray", "blue", "green", "yellow", "orange", "red", "purple", "pink", "teal")


class ConfigError(Exception):
    """The config file is missing or contains an invalid value."""


@dataclass
class Zone:
    lower: float  # the zone starts at this value
    color: str


@dataclass
class Config:
    trainer_id: int
    hr_id: int
    ftp: int
    power_zones: list[Zone]  # lower limits in % of FTP
    hr_zones: list[Zone]  # lower limits in bpm


def _zones(raw: list, where: str) -> list[Zone]:
    """Turn the zone entries from the file into checked Zone objects."""
    zones: list[Zone] = []
    for number, entry in enumerate(raw, start=1):
        try:
            zone = Zone(lower=float(entry["from"]), color=str(entry["color"]))
        except (KeyError, TypeError, ValueError):
            raise ConfigError(f"{where}, zone {number}: needs 'from' (a number) and 'color'") from None
        if zone.color not in COLORS:
            raise ConfigError(
                f"{where}, zone {number}: unknown color '{zone.color}'. "
                f"Choose from: {', '.join(COLORS)}"
            )
        if zones and zone.lower <= zones[-1].lower:
            raise ConfigError(f"{where}, zone {number}: 'from' must be higher than in the zone before")
        zones.append(zone)
    if not zones:
        raise ConfigError(f"{where}: at least one zone is needed")
    return zones


def load(path: Path = CONFIG_PATH) -> Config:
    """Read the config file, or raise ConfigError with a message for the user."""
    try:
        with path.open("rb") as file:
            raw = tomllib.load(file)
    except FileNotFoundError:
        raise ConfigError(
            f"No config file at {path}\n"
            "Copy config.example.toml from the project there, rename to config.toml, and fill in your values."
        ) from None
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"{path} is not valid TOML: {error}") from None

    try:
        config = Config(
            trainer_id=int(raw["devices"]["trainer_id"]),
            hr_id=int(raw["devices"]["hr_id"]),
            ftp=int(raw["power"]["ftp"]),
            power_zones=_zones(raw["power"]["zones"], "[power] zones"),
            hr_zones=_zones(raw["heart_rate"]["zones"], "[heart_rate] zones"),
        )
    except KeyError as error:
        raise ConfigError(f"{path}: missing setting {error}") from None
    except (TypeError, ValueError):
        raise ConfigError(f"{path}: device numbers and ftp must be whole numbers") from None

    if config.ftp <= 0:
        raise ConfigError(f"{path}: ftp must be greater than 0")
    return config