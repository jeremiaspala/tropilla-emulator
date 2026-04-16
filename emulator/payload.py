"""
payload.py — LoRaWAN payload encoder / decoder for Tropilla cattle collars.

Payload layout (16 bytes, big-endian):
  Bytes  0– 3  latitude  as int32 = round((lat  +  90) * 1e5)
  Bytes  4– 7  longitude as int32 = round((lon  + 180) * 1e5)
  Byte   8     battery 0–100 (uint8)
  Byte   9     flags: bit0=moving, bit1=outside_area, bit2=low_battery, bit3=alarm
  Bytes 10–11  speed in cm/s (uint16)
  Bytes 12–13  heading in tenths of a degree, 0–3599 (uint16)
  Byte  14     RSSI (int8, dBm, range -120 to -60)
  Byte  15     SNR * 10 (int8, range -200 to 100 → -20.0 to 10.0 dB)
"""

import base64
import json
import struct
import math
import random
from datetime import datetime, timezone
from typing import Dict, Any


# Spreading Factor → Data Rate index (LoRaWAN EU868 / US915 convention)
SF_TO_DR = {
    "SF7":  5,
    "SF8":  4,
    "SF9":  3,
    "SF10": 2,
    "SF11": 1,
    "SF12": 0,
}

PAYLOAD_FORMAT = ">iiBBHHbb"   # 4+4+1+1+2+2+1+1 = 16 bytes
PAYLOAD_SIZE = struct.calcsize(PAYLOAD_FORMAT)  # should be 16


def _simulated_rssi(sf: str) -> int:
    """Return a plausible RSSI value (dBm) for the given spreading factor."""
    base = {
        "SF7": -75, "SF8": -85, "SF9": -95,
        "SF10": -100, "SF11": -110, "SF12": -115,
    }.get(sf, -90)
    return int(base + random.uniform(-5, 5))


def _simulated_snr(sf: str) -> int:
    """Return SNR * 10 as int8 (stored in tenths of dB)."""
    base = {
        "SF7": 50, "SF8": 30, "SF9": 10,
        "SF10": -30, "SF11": -70, "SF12": -100,
    }.get(sf, 0)
    value = base + int(random.uniform(-20, 20))
    return max(-128, min(127, value))


class PayloadEncoder:
    """Encode/decode Tropilla cattle collar payloads."""

    def __init__(self, fport: int = 2, sf: str = "SF7"):
        self.fport = fport
        self.sf = sf

    # ------------------------------------------------------------------ #
    #  Binary payload                                                      #
    # ------------------------------------------------------------------ #

    def encode_binary(self, lat: float, lon: float, battery: float,
                      flags: int, speed_ms: float, heading_deg: float) -> bytes:
        """
        Pack cow telemetry into the 16-byte binary payload.

        Parameters
        ----------
        lat, lon    : decimal degrees
        battery     : 0.0–100.0 %
        flags       : status byte (bit0=moving, bit1=outside, bit2=lowbat, bit3=alarm)
        speed_ms    : speed in m/s
        heading_deg : heading 0–360 degrees
        """
        lat_enc = int(round((lat + 90.0) * 1e5))
        lon_enc = int(round((lon + 180.0) * 1e5))
        bat_enc = max(0, min(100, int(round(battery))))
        speed_cms = max(0, min(65535, int(round(speed_ms * 100))))
        heading_tenths = max(0, min(3599, int(round(heading_deg * 10)) % 3600))
        rssi = _simulated_rssi(self.sf)
        snr = _simulated_snr(self.sf)

        return struct.pack(
            PAYLOAD_FORMAT,
            lat_enc,
            lon_enc,
            bat_enc,
            flags,
            speed_cms,
            heading_tenths,
            rssi,
            snr,
        )

    def decode_binary(self, data: bytes) -> Dict[str, Any]:
        """
        Unpack a 16-byte payload back into a human-readable dict.
        """
        if len(data) < PAYLOAD_SIZE:
            raise ValueError(f"Payload too short: {len(data)} < {PAYLOAD_SIZE}")

        lat_enc, lon_enc, bat, flags, speed_cms, heading_tenths, rssi, snr_raw = \
            struct.unpack(PAYLOAD_FORMAT, data[:PAYLOAD_SIZE])

        return {
            "lat": lat_enc / 1e5 - 90.0,
            "lon": lon_enc / 1e5 - 180.0,
            "battery": bat,
            "flags": {
                "moving": bool(flags & 0x01),
                "outside_area": bool(flags & 0x02),
                "low_battery": bool(flags & 0x04),
                "alarm": bool(flags & 0x08),
            },
            "speed_ms": speed_cms / 100.0,
            "heading_deg": heading_tenths / 10.0,
            "rssi": rssi,
            "snr": snr_raw / 10.0,
        }

    # ------------------------------------------------------------------ #
    #  ChirpStack JSON wrapper                                             #
    # ------------------------------------------------------------------ #

    def encode_chirpstack(self, deveui: str, lat: float, lon: float,
                          battery: float, flags: int,
                          speed_ms: float, heading_deg: float) -> Dict[str, Any]:
        """
        Build the full ChirpStack-style JSON envelope containing the
        base64-encoded binary payload.
        """
        raw = self.encode_binary(lat, lon, battery, flags, speed_ms, heading_deg)
        rssi = _simulated_rssi(self.sf)
        snr_int = _simulated_snr(self.sf)
        snr_float = round(snr_int / 10.0, 1)
        dr = SF_TO_DR.get(self.sf, 5)

        return {
            "devEUI": deveui,
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "fPort": self.fport,
            "adr": True,
            "dr": dr,
            "spreadingFactor": int(self.sf.replace("SF", "")),
            "rssi": rssi,
            "snr": snr_float,
            "data": base64.b64encode(raw).decode("ascii"),
        }

    def encode_chirpstack_json(self, deveui: str, lat: float, lon: float,
                               battery: float, flags: int,
                               speed_ms: float, heading_deg: float) -> str:
        """Return the JSON string of the ChirpStack envelope."""
        return json.dumps(
            self.encode_chirpstack(deveui, lat, lon, battery, flags, speed_ms, heading_deg),
            ensure_ascii=False,
        )

    # ------------------------------------------------------------------ #
    #  Semtech PUSH_DATA rxpk body                                         #
    # ------------------------------------------------------------------ #

    def encode_semtech_rxpk(self, deveui: str, lat: float, lon: float,
                            battery: float, flags: int,
                            speed_ms: float, heading_deg: float,
                            freq_mhz: float) -> Dict[str, Any]:
        """
        Build the 'rxpk' entry for the Semtech UDP protocol PUSH_DATA body.
        """
        raw = self.encode_binary(lat, lon, battery, flags, speed_ms, heading_deg)
        rssi = _simulated_rssi(self.sf)
        snr_int = _simulated_snr(self.sf)
        dr = SF_TO_DR.get(self.sf, 5)

        return {
            "tmst": 0,
            "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "chan": 0,
            "rfch": 0,
            "freq": round(freq_mhz, 6),
            "stat": 1,
            "modu": "LORA",
            "datr": self.sf + "BW125",
            "codr": "4/5",
            "rssi": rssi,
            "lsnr": snr_int / 10.0,
            "size": len(raw),
            "data": base64.b64encode(raw).decode("ascii"),
        }
