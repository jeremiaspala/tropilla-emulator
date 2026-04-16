"""
gateway.py — Simulates a LoRaWAN gateway.

Supports three transport modes:
  1. MQTT        — publishes JSON to a broker using paho-mqtt.
  2. HTTP Webhook — POSTs JSON (ChirpStack format) using requests.
  3. UDP Semtech  — sends a real Semtech PUSH_DATA packet over UDP.
"""

import json
import logging
import os
import socket
import struct
import time
import random
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Callable

import requests

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
#  Gateway configuration                                              #
# ------------------------------------------------------------------ #

@dataclass
class GatewayConfig:
    protocol: str = "HTTP Webhook"      # "MQTT" | "HTTP Webhook" | "UDP Semtech"
    host: str = "localhost"
    port: int = 80
    webhook_path: str = "/tropillatrack/api/lns/uplink"
    mqtt_topic_template: str = "application/1/device/{devEUI}/event/up"
    bearer_token: str = ""
    timeout_s: float = 5.0
    # Derived gateway EUI (8 random bytes, fixed per session)
    gw_eui: bytes = field(default_factory=lambda: os.urandom(8))

    # MQTT-specific (populated lazily)
    _mqtt_client: Any = field(default=None, init=False, repr=False)
    _mqtt_connected: bool = field(default=False, init=False, repr=False)


# ------------------------------------------------------------------ #
#  Result                                                             #
# ------------------------------------------------------------------ #

@dataclass
class SendResult:
    success: bool
    protocol: str
    detail: str = ""
    latency_ms: float = 0.0


# ------------------------------------------------------------------ #
#  Gateway                                                            #
# ------------------------------------------------------------------ #

class Gateway:
    """
    Abstracts the three transport modes behind a single `send()` call.

    Parameters
    ----------
    config : GatewayConfig
    on_log : optional callback(msg: str, level: str) for GUI log updates
    """

    def __init__(self, config: GatewayConfig,
                 on_log: Optional[Callable[[str, str], None]] = None):
        self.config = config
        self.on_log = on_log
        self._udp_socket: Optional[socket.socket] = None

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def send(self, deveui: str, payload_json: Dict[str, Any],
             freq_mhz: float = 915.2) -> SendResult:
        """
        Send a telemetry packet via the configured transport.

        Parameters
        ----------
        deveui      : device EUI string (16 hex chars)
        payload_json: ChirpStack-style dict (from PayloadEncoder)
        freq_mhz    : centre frequency for Semtech packets
        """
        t0 = time.monotonic()
        proto = self.config.protocol

        try:
            if proto == "MQTT":
                result = self._send_mqtt(deveui, payload_json)
            elif proto == "HTTP Webhook":
                result = self._send_http(deveui, payload_json)
            elif proto == "UDP Semtech":
                result = self._send_udp(deveui, payload_json, freq_mhz)
            else:
                result = SendResult(False, proto, f"Unknown protocol: {proto}")
        except Exception as exc:
            result = SendResult(False, proto, str(exc))

        result.latency_ms = (time.monotonic() - t0) * 1000
        return result

    def close(self) -> None:
        """Release resources (MQTT connection, UDP socket)."""
        self._disconnect_mqtt()
        if self._udp_socket:
            try:
                self._udp_socket.close()
            except Exception:
                pass
            self._udp_socket = None

    # ------------------------------------------------------------------ #
    #  MQTT transport                                                      #
    # ------------------------------------------------------------------ #

    def _ensure_mqtt_connected(self) -> None:
        """Lazily connect / reconnect to the MQTT broker."""
        cfg = self.config
        if cfg._mqtt_client is not None and cfg._mqtt_connected:
            return

        try:
            import paho.mqtt.client as mqtt  # type: ignore
        except ImportError:
            raise RuntimeError("paho-mqtt is not installed. Run: pip install paho-mqtt")

        client = mqtt.Client(client_id=f"tropilla-gw-{random.randint(0, 0xFFFF):04X}")

        def on_connect(c, userdata, flags, rc):
            cfg._mqtt_connected = (rc == 0)
            if rc != 0:
                log.warning("MQTT connect failed, rc=%d", rc)

        def on_disconnect(c, userdata, rc):
            cfg._mqtt_connected = False
            log.info("MQTT disconnected, rc=%d", rc)

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect

        if cfg.bearer_token:
            # Use token as password with empty username
            client.username_pw_set("", cfg.bearer_token)

        client.connect_async(cfg.host, cfg.port, keepalive=60)
        client.loop_start()

        # Wait up to timeout_s for connection
        deadline = time.monotonic() + cfg.timeout_s
        while not cfg._mqtt_connected and time.monotonic() < deadline:
            time.sleep(0.05)

        if not cfg._mqtt_connected:
            client.loop_stop()
            raise ConnectionError(
                f"Could not connect to MQTT broker at {cfg.host}:{cfg.port}"
            )

        cfg._mqtt_client = client

    def _disconnect_mqtt(self) -> None:
        cfg = self.config
        if cfg._mqtt_client is not None:
            try:
                cfg._mqtt_client.loop_stop()
                cfg._mqtt_client.disconnect()
            except Exception:
                pass
            cfg._mqtt_client = None
            cfg._mqtt_connected = False

    def _send_mqtt(self, deveui: str, payload_json: Dict[str, Any]) -> SendResult:
        self._ensure_mqtt_connected()
        cfg = self.config
        topic = cfg.mqtt_topic_template.format(devEUI=deveui)
        body = json.dumps(payload_json, ensure_ascii=False)

        info = cfg._mqtt_client.publish(topic, body, qos=0)
        info.wait_for_publish(timeout=cfg.timeout_s)

        if info.rc != 0:
            return SendResult(False, "MQTT", f"Publish failed rc={info.rc}")
        return SendResult(True, "MQTT", f"topic={topic}")

    # ------------------------------------------------------------------ #
    #  HTTP Webhook transport                                              #
    # ------------------------------------------------------------------ #

    def _send_http(self, deveui: str, payload_json: Dict[str, Any]) -> SendResult:
        cfg = self.config
        path = getattr(cfg, 'webhook_path', '/').lstrip('/')
        port_str = f":{cfg.port}" if cfg.port not in (80, 443) else ""
        scheme = "https" if cfg.port == 443 else "http"
        url = f"{scheme}://{cfg.host}{port_str}/{path}"
        headers = {"Content-Type": "application/json"}
        if cfg.bearer_token:
            headers["Authorization"] = f"Bearer {cfg.bearer_token}"

        body = json.dumps(payload_json, ensure_ascii=False)

        last_exc: Optional[Exception] = None
        for attempt in range(3):
            try:
                resp = requests.post(
                    url, data=body, headers=headers,
                    timeout=cfg.timeout_s
                )
                if resp.status_code < 300:
                    return SendResult(True, "HTTP", f"HTTP {resp.status_code}")
                return SendResult(
                    False, "HTTP",
                    f"HTTP {resp.status_code}: {resp.text[:80]}"
                )
            except requests.exceptions.ConnectionError as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(0.5 * (2 ** attempt))   # 0.5 s, 1 s
            except requests.exceptions.Timeout as exc:
                last_exc = exc
                break
            except Exception as exc:
                last_exc = exc
                break

        return SendResult(False, "HTTP", f"Connection refused: {last_exc}")

    # ------------------------------------------------------------------ #
    #  UDP Semtech transport                                               #
    # ------------------------------------------------------------------ #

    def _get_udp_socket(self) -> socket.socket:
        if self._udp_socket is None:
            self._udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._udp_socket.settimeout(self.config.timeout_s)
        return self._udp_socket

    def _build_push_data(self, payload_json: Dict[str, Any],
                         freq_mhz: float) -> bytes:
        """
        Assemble a Semtech PUSH_DATA UDP packet.

        Header (12 bytes):
          1 byte  version   = 0x02
          2 bytes token     = random uint16
          1 byte  identifier= 0x00 (PUSH_DATA)
          8 bytes gwEUI     = gateway identifier

        Body: UTF-8 JSON with {"rxpk": [...]}
        """
        version = 0x02
        token = random.randint(0, 0xFFFF)
        identifier = 0x00   # PUSH_DATA

        header = struct.pack(
            ">BHB8s",
            version,
            token,
            identifier,
            self.config.gw_eui,
        )

        # Build rxpk entry from the ChirpStack payload_json
        rxpk = {
            "tmst": int(time.time() * 1_000_000) & 0xFFFFFFFF,
            "time": payload_json.get("time", ""),
            "chan": 0,
            "rfch": 0,
            "freq": freq_mhz,
            "stat": 1,
            "modu": "LORA",
            "datr": f"SF{payload_json.get('spreadingFactor', 7)}BW125",
            "codr": "4/5",
            "rssi": payload_json.get("rssi", -90),
            "lsnr": payload_json.get("snr", 5.0),
            "size": 16,
            "data": payload_json.get("data", ""),
        }
        body_json = json.dumps({"rxpk": [rxpk]}, ensure_ascii=False).encode("utf-8")
        return header + body_json

    def _send_udp(self, deveui: str, payload_json: Dict[str, Any],
                  freq_mhz: float) -> SendResult:
        cfg = self.config
        packet = self._build_push_data(payload_json, freq_mhz)
        sock = self._get_udp_socket()

        try:
            sock.sendto(packet, (cfg.host, cfg.port))
            # Try to read PUSH_ACK (optional, non-fatal if absent)
            try:
                ack, _ = sock.recvfrom(256)
                # ACK header: version(1) token(2) identifier(1=PUSH_ACK=0x01)
                if len(ack) >= 4 and ack[3] == 0x01:
                    return SendResult(True, "UDP", f"{len(packet)} bytes + ACK")
                return SendResult(True, "UDP", f"{len(packet)} bytes (no ACK)")
            except socket.timeout:
                # No ACK is normal for Semtech; packet was still sent
                return SendResult(True, "UDP", f"{len(packet)} bytes sent (no ACK)")
        except OSError as exc:
            return SendResult(False, "UDP", str(exc))
