"""
cattle.py — Cow model with realistic Ornstein-Uhlenbeck grazing movement.

Each Cow has:
  - A unique DevEUI derived from "TROPILLA" + index.
  - Current geographic position (lat, lon).
  - Current velocity vector (vx, vy) in m/s on a local Cartesian plane.
  - Battery level (0–100 %).
  - Behavioural state: pastando / caminando / descansando / fuera_de_area.

Movement is based on the Ornstein-Uhlenbeck (OU) process, which produces
correlated noise: the cow tends to keep moving in a similar direction but
eventually changes, giving realistic "area-stay" behaviour rather than a
pure random walk.
"""

import math
import numpy as np
from dataclasses import dataclass, field as dc_field
from typing import Tuple

from .field import Field, EARTH_RADIUS_M


# ------------------------------------------------------------------ #
#  OU process parameters                                               #
# ------------------------------------------------------------------ #
THETA = 0.15        # mean-reversion speed  (higher = more diffusive)
SIGMA_GRAZING = 0.05  # volatility when grazing  (m/s per sqrt-s)
SIGMA_WALKING = 0.15  # volatility when walking
MU_GRAZING = 0.0    # mean velocity (we use zero → attracted to current pos)
MU_WALKING = 0.0

MAX_SPEED_MS = {
    "pastando": 1.5 / 3.6,    # ~0.42 m/s
    "caminando": 4.0 / 3.6,   # ~1.11 m/s
    "descansando": 0.0,
    "fuera_de_area": 4.0 / 3.6,
}

# Battery drain per transmission (% points)
BATTERY_DRAIN_PER_TX = 0.001
# Probability of spontaneous state transitions per update step
STATE_TRANSITION_PROB = 0.02


def _make_deveui(index: int) -> str:
    """
    Generate a DevEUI as "TROPILLA" ASCII hex + 2-byte index.
    'TROPILLA' in hex = 54 52 4F 50 49 4C 4C 41  (8 bytes)
    We append 2 bytes for the index (up to 65535 devices).
    Total: 10 bytes → represented as 20-char hex string.
    ChirpStack / LoRaWAN DevEUI is 8 bytes (16 hex chars), so we fold:
    we use the last 8 bytes = "4C4C41" + 3-byte padding + 2-byte index.
    Actually let's just do: "TROPILLA" bytes as prefix, truncate to 8 bytes
    by using bytes 0-5 of "TROPILLA" + 2 index bytes.
    TROPILLA = 54 52 4F 50 49 4C 4C 41
    We use bytes 0-5 (54 52 4F 50 49 4C) + index as uint16 big-endian.
    """
    prefix = b'\x54\x52\x4F\x50\x49\x4C\x4C\x41'  # "TROPILLA"
    # Use first 6 bytes of prefix + 2 bytes of index
    idx_bytes = index.to_bytes(2, byteorder='big')
    deveui_bytes = prefix[:6] + idx_bytes
    return deveui_bytes.hex().upper()


@dataclass
class Cow:
    """Single cattle device with OU-based movement."""

    index: int
    field: Field
    rng: np.random.Generator

    # Position
    lat: float = dc_field(init=False)
    lon: float = dc_field(init=False)

    # Velocity in m/s on local Cartesian axes (East, North)
    vx: float = dc_field(init=False)   # East component
    vy: float = dc_field(init=False)   # North component

    # Battery
    battery: float = dc_field(init=False)

    # State
    state: str = dc_field(init=False)

    # DevEUI
    deveui: str = dc_field(init=False)

    # Heading in degrees (0 = North, clockwise)
    heading_deg: float = dc_field(init=False)

    # Speed in m/s (magnitude of velocity vector)
    speed_ms: float = dc_field(init=False)

    # Alarm flag (e.g. the cow has been outside for too long)
    alarm: bool = dc_field(init=False)

    # Seconds outside the field boundary
    _seconds_outside: float = dc_field(init=False)

    def __post_init__(self):
        self.deveui = _make_deveui(self.index)
        self.lat, self.lon = self.field.random_point_inside(self.rng)
        self.vx = self.rng.normal(0, 0.1)
        self.vy = self.rng.normal(0, 0.1)
        self.battery = float(self.rng.uniform(75, 100))
        self.state = self.rng.choice(
            ["pastando", "caminando", "descansando"],
            p=[0.6, 0.3, 0.1]
        )
        self.heading_deg = 0.0
        self.speed_ms = 0.0
        self.alarm = False
        self._seconds_outside = 0.0

    # ------------------------------------------------------------------ #
    #  Movement update                                                     #
    # ------------------------------------------------------------------ #

    def update(self, dt: float) -> None:
        """
        Advance the cow's state by *dt* seconds.

        1. Possibly transition to a new behavioural state.
        2. Apply the OU process to velocity.
        3. Move the cow.
        4. Clamp to field boundary if needed.
        5. Update alarm / outside-area state.
        """
        self._maybe_transition_state()
        self._apply_ou(dt)
        self._move(dt)
        self._handle_boundary()

    def _maybe_transition_state(self) -> None:
        """Random state machine transitions."""
        if self.state == "fuera_de_area":
            return  # handled by boundary logic
        if self.rng.random() < STATE_TRANSITION_PROB:
            weights = {
                "pastando":    [0.00, 0.25, 0.75],
                "caminando":   [0.60, 0.00, 0.40],
                "descansando": [0.70, 0.30, 0.00],
            }
            choices = ["pastando", "caminando", "descansando"]
            w = weights.get(self.state, [0.33, 0.33, 0.34])
            self.state = self.rng.choice(choices, p=w)

    def _apply_ou(self, dt: float) -> None:
        """
        Ornstein-Uhlenbeck velocity update:
          dv = theta*(mu - v)*dt + sigma*sqrt(dt)*N(0,1)

        For resting cows, velocity decays toward zero quickly.
        """
        if self.state == "descansando":
            # Strong mean-reversion toward 0
            self.vx += 5 * THETA * (0 - self.vx) * dt
            self.vy += 5 * THETA * (0 - self.vy) * dt
            return

        sigma = SIGMA_GRAZING if self.state == "pastando" else SIGMA_WALKING
        sqrt_dt = math.sqrt(dt)

        self.vx += THETA * (MU_GRAZING - self.vx) * dt + sigma * sqrt_dt * self.rng.standard_normal()
        self.vy += THETA * (MU_WALKING - self.vy) * dt + sigma * sqrt_dt * self.rng.standard_normal()

        # Clamp speed to state maximum
        max_v = MAX_SPEED_MS.get(self.state, 1.5 / 3.6)
        speed = math.hypot(self.vx, self.vy)
        if speed > max_v and speed > 0:
            scale = max_v / speed
            self.vx *= scale
            self.vy *= scale

    def _move(self, dt: float) -> None:
        """Convert velocity (m/s Cartesian) to new (lat, lon)."""
        # distance moved in each axis
        dx = self.vx * dt   # metres East
        dy = self.vy * dt   # metres North

        # Convert to degree offsets
        d_lat = dy / 111_319.0
        metres_per_deg_lon = 111_319.0 * math.cos(math.radians(self.lat))
        d_lon = dx / metres_per_deg_lon if metres_per_deg_lon > 0 else 0.0

        self.lat += d_lat
        self.lon += d_lon

        # Update heading and speed
        self.speed_ms = math.hypot(self.vx, self.vy)
        if self.speed_ms > 0.01:
            # atan2(east, north) gives bearing from North, clockwise
            angle = math.degrees(math.atan2(self.vx, self.vy))
            self.heading_deg = (angle + 360) % 360

    def _handle_boundary(self) -> None:
        """
        If the cow is outside the field, nudge it back toward the centre
        with an OU drift toward the field interior.  Mark as fuera_de_area.
        """
        dist = self.field.distance_from_centre(self.lat, self.lon)
        if dist > self.field.radius_m:
            self._seconds_outside += 5  # assume ~5 s steps
            self.state = "fuera_de_area"
            if self._seconds_outside >= 300:  # 5 minutes outside → alarm
                self.alarm = True

            # Apply a corrective drift: add velocity toward centre
            bearing = self.field.bearing_to_centre(self.lat, self.lon)
            bearing_rad = math.radians(bearing)
            # Strength proportional to how far outside
            strength = 0.5 + (dist - self.field.radius_m) / self.field.radius_m
            self.vx += strength * math.sin(bearing_rad)
            self.vy += strength * math.cos(bearing_rad)

            # Hard clamp: never let the cow drift more than 500 m outside
            if dist > self.field.radius_m + 500:
                new_lat, new_lon, _ = self.field.clamp_to_field(
                    self.lat, self.lon, margin_m=100
                )
                self.lat, self.lon = new_lat, new_lon
        else:
            self._seconds_outside = 0.0
            if self.state == "fuera_de_area":
                self.state = "pastando"
            if self.alarm and dist < self.field.radius_m * 0.9:
                self.alarm = False  # reset alarm once clearly inside

    # ------------------------------------------------------------------ #
    #  Battery                                                             #
    # ------------------------------------------------------------------ #

    def drain_battery(self) -> None:
        """Drain battery slightly each transmission."""
        temp_factor = 1.0 + self.rng.uniform(-0.2, 0.2)
        drain = BATTERY_DRAIN_PER_TX * temp_factor
        self.battery = max(0.0, self.battery - drain)

    # ------------------------------------------------------------------ #
    #  Derived flags                                                       #
    # ------------------------------------------------------------------ #

    @property
    def is_moving(self) -> bool:
        return self.speed_ms > 0.1 and self.state in ("caminando", "fuera_de_area")

    @property
    def is_outside_area(self) -> bool:
        return self.state == "fuera_de_area"

    @property
    def is_low_battery(self) -> bool:
        return self.battery < 20.0

    def flags_byte(self) -> int:
        """Pack status flags into a single byte."""
        flags = 0
        if self.is_moving:
            flags |= 0x01
        if self.is_outside_area:
            flags |= 0x02
        if self.is_low_battery:
            flags |= 0x04
        if self.alarm:
            flags |= 0x08
        return flags

    def state_label(self) -> str:
        """Human-readable state for the GUI log."""
        labels = {
            "pastando": "grazing",
            "caminando": "walking",
            "descansando": "resting",
            "fuera_de_area": "OUTSIDE",
        }
        return labels.get(self.state, self.state)
