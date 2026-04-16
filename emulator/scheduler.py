"""
scheduler.py — Orchestrates transmission cycles for all simulated cows.

Design:
  - Runs in a dedicated daemon thread so it never blocks the GUI.
  - Each cow gets its own next-TX timestamp with ±10 % jitter to avoid
    simultaneous transmissions ("thundering herd").
  - The movement update loop runs every MOVEMENT_DT seconds (5 s default)
    and is independent of the TX interval.
  - All GUI callbacks are dispatched via root.after() to stay thread-safe.
"""

import logging
import random
import threading
import time
from typing import Callable, Dict, List, Optional

import numpy as np

from .cattle import Cow
from .field import Field
from .gateway import Gateway, GatewayConfig, SendResult
from .payload import PayloadEncoder

log = logging.getLogger(__name__)

MOVEMENT_DT = 5.0   # seconds between position updates


class Scheduler:
    """
    Manages the simulation loop for a list of cows.

    Parameters
    ----------
    root            : tkinter root widget (needed for thread-safe callbacks)
    cows            : list of Cow instances
    field           : Field instance
    gateway         : Gateway instance
    encoder         : PayloadEncoder instance
    interval_s      : TX interval in seconds (same for all cows, with jitter)
    freq_mhz        : LoRa frequency, passed to gateway
    on_tx           : callback(cow, result: SendResult) — called after each TX
    on_movement     : callback(cows) — called after every movement update
    on_stop         : callback() — called when the scheduler stops
    """

    def __init__(
        self,
        root,
        cows: List[Cow],
        field: Field,
        gateway: Gateway,
        encoder: PayloadEncoder,
        interval_s: float,
        freq_mhz: float,
        on_tx: Callable,
        on_movement: Callable,
        on_stop: Callable,
    ):
        self.root = root
        self.cows = cows
        self.field = field
        self.gateway = gateway
        self.encoder = encoder
        self.interval_s = interval_s
        self.freq_mhz = freq_mhz
        self.on_tx = on_tx
        self.on_movement = on_movement
        self.on_stop = on_stop

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Per-cow next-TX timestamps (monotonic)
        self._next_tx: Dict[str, float] = {}
        self._next_movement: float = 0.0

        # TX counters
        self.tx_total: int = 0
        self.tx_ok: int = 0
        self.tx_err: int = 0

    # ------------------------------------------------------------------ #
    #  Start / Stop                                                        #
    # ------------------------------------------------------------------ #

    def start(self) -> None:
        """Start the simulation in a background thread."""
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self.tx_total = 0
        self.tx_ok = 0
        self.tx_err = 0

        now = time.monotonic()
        self._next_movement = now + MOVEMENT_DT

        # Stagger initial TX times so cows don't all transmit at t=0
        for cow in self.cows:
            jitter = random.uniform(0, self.interval_s)
            self._next_tx[cow.deveui] = now + jitter

        self._thread = threading.Thread(
            target=self._run_loop,
            name="scheduler",
            daemon=True,
        )
        self._thread.start()
        log.info("Scheduler started with %d cows, interval=%.1f s", len(self.cows), self.interval_s)

    def stop(self) -> None:
        """Signal the scheduler to stop and wait for the thread to exit."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        self.gateway.close()
        log.info("Scheduler stopped. TX total=%d ok=%d err=%d",
                  self.tx_total, self.tx_ok, self.tx_err)

    # ------------------------------------------------------------------ #
    #  Main loop                                                           #
    # ------------------------------------------------------------------ #

    def _run_loop(self) -> None:
        """Background thread: movement updates + per-cow TX scheduling."""
        try:
            while not self._stop_event.is_set():
                now = time.monotonic()

                # — Movement update —
                if now >= self._next_movement:
                    for cow in self.cows:
                        cow.update(MOVEMENT_DT)
                    self._next_movement = now + MOVEMENT_DT
                    self._safe_callback(self.on_movement, self.cows)

                # — Per-cow TX —
                for cow in self.cows:
                    if now >= self._next_tx[cow.deveui]:
                        self._transmit(cow)
                        jitter_factor = random.uniform(0.9, 1.1)
                        self._next_tx[cow.deveui] = (
                            now + self.interval_s * jitter_factor
                        )

                # Sleep until the next event (either movement or earliest TX)
                next_event = min(
                    self._next_movement,
                    min(self._next_tx.values(), default=now + 1),
                )
                sleep_s = max(0.05, next_event - time.monotonic())
                self._stop_event.wait(timeout=min(sleep_s, 0.5))

        except Exception:
            log.exception("Unhandled exception in scheduler loop")
        finally:
            self._safe_callback(self.on_stop)

    # ------------------------------------------------------------------ #
    #  Transmit one cow                                                    #
    # ------------------------------------------------------------------ #

    def _transmit(self, cow: Cow) -> None:
        """Encode payload and send via gateway, then notify the GUI."""
        payload_dict = self.encoder.encode_chirpstack(
            deveui=cow.deveui,
            lat=cow.lat,
            lon=cow.lon,
            battery=cow.battery,
            flags=cow.flags_byte(),
            speed_ms=cow.speed_ms,
            heading_deg=cow.heading_deg,
        )
        result = self.gateway.send(cow.deveui, payload_dict, self.freq_mhz)

        self.tx_total += 1
        if result.success:
            self.tx_ok += 1
            cow.drain_battery()
        else:
            self.tx_err += 1

        self._safe_callback(self.on_tx, cow, result)

    # ------------------------------------------------------------------ #
    #  Thread-safe GUI callback                                            #
    # ------------------------------------------------------------------ #

    def _safe_callback(self, fn: Callable, *args) -> None:
        """Schedule *fn(*args)* on the Tk main thread via root.after()."""
        try:
            self.root.after(0, fn, *args)
        except Exception:
            pass   # root may already be destroyed
