"""
gui.py — Main tkinter window for Tropilla Emulator.

Layout:
  ┌─────────────────────────────────────────────────────────┐
  │  Left panel: field + simulation params                  │
  │  Right panel: server + LoRa collar params               │
  ├─────────────────────────────────────────────────────────┤
  │  Bottom bar: Start / Stop / Export  │  Status label     │
  ├─────────────────────────────────────────────────────────┤
  │  Log area (scrollable Text widget)                      │
  └─────────────────────────────────────────────────────────┘
"""

import csv
import json
import logging
import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
from typing import List, Optional

import numpy as np

from .cattle import Cow
from .field import Field
from .gateway import Gateway, GatewayConfig, SendResult
from .payload import PayloadEncoder
from .scheduler import Scheduler

log = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  Colour palette                                                      #
# ------------------------------------------------------------------ #
COLOR_BG        = "#1E1E2E"   # dark background
COLOR_PANEL     = "#2A2A3E"   # panel background
COLOR_ACCENT    = "#7C3AED"   # purple accent
COLOR_TEXT      = "#E2E8F0"   # main text
COLOR_SUBTEXT   = "#94A3B8"   # secondary text
COLOR_GREEN     = "#22C55E"   # success / start button
COLOR_RED       = "#EF4444"   # error / stop button
COLOR_ORANGE    = "#F59E0B"   # warning
COLOR_BORDER    = "#3F3F5A"   # widget border

DEFAULT_CFG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "default.json")


def _load_defaults() -> dict:
    try:
        with open(DEFAULT_CFG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ------------------------------------------------------------------ #
#  Helper widgets                                                      #
# ------------------------------------------------------------------ #

class _LabeledEntry(tk.Frame):
    """A label + entry pair packed vertically inside a parent frame."""

    def __init__(self, parent, label: str, default: str = "", width: int = 22, **kw):
        super().__init__(parent, **kw)
        ttk.Label(self, text=label, foreground=COLOR_SUBTEXT,
                  background=COLOR_PANEL).pack(anchor="w")
        self.var = tk.StringVar(value=default)
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(fill="x", pady=(0, 6))

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, value: str) -> None:
        self.var.set(value)


class _LabeledCombo(tk.Frame):
    """A label + combobox pair."""

    def __init__(self, parent, label: str, values: list,
                 default: str = "", width: int = 20, **kw):
        super().__init__(parent, **kw)
        ttk.Label(self, text=label, foreground=COLOR_SUBTEXT,
                  background=COLOR_PANEL).pack(anchor="w")
        self.var = tk.StringVar(value=default or (values[0] if values else ""))
        self.combo = ttk.Combobox(self, textvariable=self.var,
                                  values=values, state="readonly", width=width)
        self.combo.pack(fill="x", pady=(0, 6))

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str) -> None:
        self.var.set(value)


# ------------------------------------------------------------------ #
#  Main application window                                            #
# ------------------------------------------------------------------ #

class EmulatorApp(tk.Tk):
    """Root window for Tropilla Emulator."""

    def __init__(self):
        super().__init__()
        self.title("Tropilla Emulator v1.0")
        self.geometry("960x720")
        self.minsize(860, 640)
        self.configure(bg=COLOR_BG)

        self._apply_theme()

        self._defaults = _load_defaults()
        self._scheduler: Optional[Scheduler] = None
        self._cows: List[Cow] = []
        self._log_entries: list = []   # list of dicts for CSV export

        self._build_ui()
        self._populate_defaults()

    # ------------------------------------------------------------------ #
    #  Theme                                                               #
    # ------------------------------------------------------------------ #

    def _apply_theme(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(".", background=COLOR_BG, foreground=COLOR_TEXT,
                        fieldbackground=COLOR_PANEL, bordercolor=COLOR_BORDER,
                        darkcolor=COLOR_PANEL, lightcolor=COLOR_PANEL,
                        troughcolor=COLOR_PANEL, selectbackground=COLOR_ACCENT,
                        selectforeground=COLOR_TEXT, font=("Segoe UI", 9))

        style.configure("TFrame", background=COLOR_BG)
        style.configure("Panel.TFrame", background=COLOR_PANEL,
                        relief="flat", borderwidth=1)
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT)
        style.configure("Panel.TLabel", background=COLOR_PANEL, foreground=COLOR_TEXT)
        style.configure("Sub.TLabel", background=COLOR_PANEL, foreground=COLOR_SUBTEXT,
                        font=("Segoe UI", 8))

        style.configure("TEntry", fieldbackground="#2D2D44",
                        foreground=COLOR_TEXT, bordercolor=COLOR_BORDER,
                        insertcolor=COLOR_TEXT)
        style.map("TEntry", fieldbackground=[("disabled", COLOR_PANEL)])

        style.configure("TCombobox", fieldbackground="#2D2D44",
                        foreground=COLOR_TEXT, bordercolor=COLOR_BORDER,
                        arrowcolor=COLOR_TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", "#2D2D44")])

        style.configure("Green.TButton", background=COLOR_GREEN,
                        foreground="white", font=("Segoe UI", 10, "bold"),
                        padding=6)
        style.map("Green.TButton",
                  background=[("active", "#16A34A"), ("disabled", "#374151")])

        style.configure("Red.TButton", background=COLOR_RED,
                        foreground="white", font=("Segoe UI", 10, "bold"),
                        padding=6)
        style.map("Red.TButton",
                  background=[("active", "#B91C1C"), ("disabled", "#374151")])

        style.configure("Export.TButton", background=COLOR_ACCENT,
                        foreground="white", font=("Segoe UI", 10, "bold"),
                        padding=6)
        style.map("Export.TButton",
                  background=[("active", "#5B21B6"), ("disabled", "#374151")])

        style.configure("TScrollbar", background=COLOR_PANEL,
                        troughcolor=COLOR_BG, arrowcolor=COLOR_SUBTEXT)

        style.configure("Title.TLabel", background=COLOR_BG,
                        foreground=COLOR_TEXT, font=("Segoe UI", 11, "bold"))
        style.configure("Status.TLabel", background=COLOR_BG,
                        foreground=COLOR_SUBTEXT, font=("Segoe UI", 9))

    # ------------------------------------------------------------------ #
    #  UI build                                                            #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        # ── top area (two side-by-side panels) ──────────────────────────
        top = ttk.Frame(self)
        top.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        top.columnconfigure(0, weight=1)
        top.columnconfigure(1, weight=1)
        top.rowconfigure(0, weight=1)

        self._build_left_panel(top)
        self._build_right_panel(top)

        # ── bottom bar ──────────────────────────────────────────────────
        self._build_bottom_bar()

        # ── log area ────────────────────────────────────────────────────
        self._build_log_area()

    # ── Left panel ──────────────────────────────────────────────────────

    def _build_left_panel(self, parent) -> None:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        ttk.Label(frame, text="Campo & Simulacion",
                  style="Title.TLabel",
                  background=COLOR_PANEL).pack(anchor="w", pady=(0, 10))

        self._lat   = _LabeledEntry(frame, "Latitud central",  background=COLOR_PANEL)
        self._lon   = _LabeledEntry(frame, "Longitud central", background=COLOR_PANEL)
        self._radius = _LabeledEntry(frame, "Radio del campo (m)", background=COLOR_PANEL)
        self._num_cows = _LabeledEntry(frame, "Cantidad de vacas (1–200)", background=COLOR_PANEL)
        self._interval = _LabeledEntry(frame, "Periodicidad de reportes (min)", background=COLOR_PANEL)
        self._seed  = _LabeledEntry(frame, "Semilla aleatoria (opcional)", background=COLOR_PANEL)

        for w in (self._lat, self._lon, self._radius,
                  self._num_cows, self._interval, self._seed):
            w.pack(fill="x")

    # ── Right panel ─────────────────────────────────────────────────────

    def _build_right_panel(self, parent) -> None:
        frame = ttk.Frame(parent, style="Panel.TFrame", padding=12)
        frame.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        # ── Server section ──
        ttk.Label(frame, text="Servidor destino",
                  style="Title.TLabel",
                  background=COLOR_PANEL).pack(anchor="w", pady=(0, 6))

        self._protocol = _LabeledCombo(
            frame, "Protocolo",
            ["MQTT", "HTTP Webhook", "UDP Semtech"],
            background=COLOR_PANEL,
        )
        self._protocol.pack(fill="x")
        self._protocol.combo.bind("<<ComboboxSelected>>", self._on_protocol_changed)

        self._host   = _LabeledEntry(frame, "URL / Host del servidor", background=COLOR_PANEL)
        self._port   = _LabeledEntry(frame, "Puerto", background=COLOR_PANEL)
        self._webhook_path = _LabeledEntry(frame, "Path del webhook (HTTP)", background=COLOR_PANEL)

        # MQTT topic (shown/hidden based on protocol)
        self._topic_frame = _LabeledEntry(frame, "Topic MQTT", background=COLOR_PANEL)

        self._token  = _LabeledEntry(frame, "Bearer token / API Key (opcional)", background=COLOR_PANEL)
        self._timeout = _LabeledEntry(frame, "Timeout conexion (s)", background=COLOR_PANEL)

        for w in (self._host, self._port, self._webhook_path, self._topic_frame, self._token, self._timeout):
            w.pack(fill="x")

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=8)

        # ── LoRa collar section ──
        ttk.Label(frame, text="Collar LoRa",
                  style="Title.TLabel",
                  background=COLOR_PANEL).pack(anchor="w", pady=(0, 6))

        self._deveui = _LabeledEntry(frame, "DevEUI (16 hex)", background=COLOR_PANEL)
        self._appeui = _LabeledEntry(frame, "AppEUI (16 hex)", background=COLOR_PANEL)
        self._appkey = _LabeledEntry(frame, "AppKey (32 hex)", background=COLOR_PANEL)

        self._sf = _LabeledCombo(
            frame, "Spreading Factor",
            ["SF7", "SF8", "SF9", "SF10", "SF11", "SF12"],
            background=COLOR_PANEL,
        )
        self._bw = _LabeledCombo(
            frame, "Bandwidth",
            ["125kHz", "250kHz", "500kHz"],
            background=COLOR_PANEL,
        )

        self._freq   = _LabeledEntry(frame, "Frecuencia (MHz)", background=COLOR_PANEL)
        self._fport  = _LabeledEntry(frame, "fPort (1–223)", background=COLOR_PANEL)

        for w in (self._deveui, self._appeui, self._appkey,
                  self._sf, self._bw, self._freq, self._fport):
            w.pack(fill="x")

    # ── Bottom bar ──────────────────────────────────────────────────────

    def _build_bottom_bar(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=10, pady=4)

        self._btn_start = ttk.Button(bar, text="Iniciar simulacion",
                                     style="Green.TButton",
                                     command=self._on_start)
        self._btn_start.pack(side="left", padx=(0, 6))

        self._btn_stop = ttk.Button(bar, text="Detener",
                                    style="Red.TButton",
                                    command=self._on_stop,
                                    state="disabled")
        self._btn_stop.pack(side="left", padx=(0, 6))

        self._btn_export = ttk.Button(bar, text="Exportar logs CSV",
                                      style="Export.TButton",
                                      command=self._on_export)
        self._btn_export.pack(side="left", padx=(0, 12))

        self._status_var = tk.StringVar(value="Detenido")
        ttk.Label(bar, textvariable=self._status_var,
                  style="Status.TLabel").pack(side="left")

        self._tx_var = tk.StringVar(value="TX: 0")
        ttk.Label(bar, textvariable=self._tx_var,
                  style="Status.TLabel").pack(side="right")

    # ── Log area ────────────────────────────────────────────────────────

    def _build_log_area(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        ttk.Label(frame, text="Log de transmisiones",
                  style="Title.TLabel").pack(anchor="w", pady=(0, 4))

        text_frame = ttk.Frame(frame)
        text_frame.pack(fill="both", expand=True)

        self._log_text = tk.Text(
            text_frame,
            bg="#0F0F1A",
            fg=COLOR_TEXT,
            font=("Consolas", 9),
            state="disabled",
            wrap="none",
            bd=0,
            padx=6,
            pady=4,
        )
        scroll_y = ttk.Scrollbar(text_frame, orient="vertical",
                                  command=self._log_text.yview)
        scroll_x = ttk.Scrollbar(frame, orient="horizontal",
                                  command=self._log_text.xview)
        self._log_text.configure(yscrollcommand=scroll_y.set,
                                  xscrollcommand=scroll_x.set)

        scroll_y.pack(side="right", fill="y")
        self._log_text.pack(side="left", fill="both", expand=True)
        scroll_x.pack(fill="x")

        self._log_text.tag_configure("ok",    foreground=COLOR_GREEN)
        self._log_text.tag_configure("error", foreground=COLOR_RED)
        self._log_text.tag_configure("warn",  foreground=COLOR_ORANGE)

    # ------------------------------------------------------------------ #
    #  Defaults population                                                 #
    # ------------------------------------------------------------------ #

    def _populate_defaults(self) -> None:
        d = self._defaults
        field_d  = d.get("field", {})
        server_d = d.get("server", {})
        lora_d   = d.get("lora", {})

        self._lat.set(str(field_d.get("lat", -32.9500)))
        self._lon.set(str(field_d.get("lon", -60.6600)))
        self._radius.set(str(field_d.get("radius_m", 2000)))
        self._num_cows.set(str(field_d.get("num_cows", 10)))
        self._interval.set(str(field_d.get("report_interval_min", 1.0)))
        self._seed.set(str(field_d.get("random_seed", "") or ""))

        self._protocol.set(server_d.get("protocol", "HTTP Webhook"))
        self._host.set(server_d.get("host", "localhost"))
        self._port.set(str(server_d.get("port", 80)))
        self._webhook_path.set(server_d.get("webhook_path", "/tropillatrack/api/lns/uplink"))
        self._topic_frame.set(server_d.get("mqtt_topic",
                                           "application/1/device/{devEUI}/event/up"))
        self._token.set(server_d.get("bearer_token", ""))
        self._timeout.set(str(server_d.get("timeout_s", 5)))

        self._deveui.set(lora_d.get("dev_eui", "54524F5000000001"))
        self._appeui.set(lora_d.get("app_eui", "54524F5041505000"))
        self._appkey.set(lora_d.get("app_key", "54524F504150500054524F5041505000"))
        self._sf.set(lora_d.get("spreading_factor", "SF7"))
        self._bw.set(lora_d.get("bandwidth", "125kHz"))
        self._freq.set(str(lora_d.get("frequency_mhz", 915.2)))
        self._fport.set(str(lora_d.get("fport", 2)))

        self._on_protocol_changed()

    # ------------------------------------------------------------------ #
    #  Protocol visibility toggle                                          #
    # ------------------------------------------------------------------ #

    def _on_protocol_changed(self, event=None) -> None:
        proto = self._protocol.get()
        if proto == "MQTT":
            self._topic_frame.pack(fill="x")
        else:
            self._topic_frame.pack_forget()

    # ------------------------------------------------------------------ #
    #  Input validation                                                    #
    # ------------------------------------------------------------------ #

    def _parse_inputs(self) -> dict:
        """Parse and validate all form inputs. Raises ValueError on bad input."""
        try:
            lat = float(self._lat.get())
            if not (-90 <= lat <= 90):
                raise ValueError("Latitud debe estar entre -90 y 90")
        except ValueError as e:
            raise ValueError(f"Latitud invalida: {e}")

        try:
            lon = float(self._lon.get())
            if not (-180 <= lon <= 180):
                raise ValueError("Longitud debe estar entre -180 y 180")
        except ValueError as e:
            raise ValueError(f"Longitud invalida: {e}")

        try:
            radius = int(self._radius.get())
            if radius <= 0:
                raise ValueError("El radio debe ser positivo")
        except ValueError as e:
            raise ValueError(f"Radio invalido: {e}")

        try:
            num_cows = int(self._num_cows.get())
            if not (1 <= num_cows <= 200):
                raise ValueError("Debe estar entre 1 y 200")
        except ValueError as e:
            raise ValueError(f"Cantidad de vacas invalida: {e}")

        try:
            interval_min = float(self._interval.get())
            if interval_min <= 0:
                raise ValueError("Debe ser positivo")
        except ValueError as e:
            raise ValueError(f"Periodicidad invalida: {e}")

        seed_str = self._seed.get()
        seed = int(seed_str) if seed_str else None

        proto = self._protocol.get()

        try:
            port = int(self._port.get())
        except ValueError:
            raise ValueError("Puerto invalido (debe ser entero)")

        try:
            timeout = float(self._timeout.get())
        except ValueError:
            raise ValueError("Timeout invalido")

        try:
            fport = int(self._fport.get())
            if not (1 <= fport <= 223):
                raise ValueError("fPort debe estar entre 1 y 223")
        except ValueError as e:
            raise ValueError(f"fPort invalido: {e}")

        try:
            freq = float(self._freq.get())
        except ValueError:
            raise ValueError("Frecuencia invalida")

        return {
            "lat": lat,
            "lon": lon,
            "radius": radius,
            "num_cows": num_cows,
            "interval_s": interval_min * 60,
            "seed": seed,
            "protocol": proto,
            "host": self._host.get(),
            "port": port,
            "webhook_path": self._webhook_path.get(),
            "mqtt_topic": self._topic_frame.get(),
            "token": self._token.get(),
            "timeout": timeout,
            "deveui": self._deveui.get(),
            "appeui": self._appeui.get(),
            "appkey": self._appkey.get(),
            "sf": self._sf.get(),
            "bw": self._bw.get(),
            "freq": freq,
            "fport": fport,
        }

    # ------------------------------------------------------------------ #
    #  Start / Stop handlers                                               #
    # ------------------------------------------------------------------ #

    def _on_start(self) -> None:
        try:
            cfg = self._parse_inputs()
        except ValueError as e:
            messagebox.showerror("Parametros invalidos", str(e))
            return

        self._log_entries.clear()
        self._clear_log()

        # Build field
        field = Field(lat=cfg["lat"], lon=cfg["lon"], radius_m=cfg["radius"])

        # RNG
        rng = np.random.default_rng(cfg["seed"])

        # Build cows (each gets its own RNG sub-stream)
        self._cows = [
            Cow(index=i, field=field,
                rng=np.random.default_rng(rng.integers(0, 2**32)))
            for i in range(cfg["num_cows"])
        ]

        # Gateway
        gw_cfg = GatewayConfig(
            protocol=cfg["protocol"],
            host=cfg["host"],
            port=cfg["port"],
            webhook_path=cfg.get("webhook_path", "/tropillatrack/api/lns/uplink"),
            mqtt_topic_template=cfg["mqtt_topic"],
            bearer_token=cfg["token"],
            timeout_s=cfg["timeout"],
        )
        gateway = Gateway(gw_cfg)

        # Encoder
        encoder = PayloadEncoder(fport=cfg["fport"], sf=cfg["sf"])

        # Scheduler
        self._scheduler = Scheduler(
            root=self,
            cows=self._cows,
            field=field,
            gateway=gateway,
            encoder=encoder,
            interval_s=cfg["interval_s"],
            freq_mhz=cfg["freq"],
            on_tx=self._on_tx_event,
            on_movement=self._on_movement_event,
            on_stop=self._on_scheduler_stopped,
        )
        self._scheduler.start()

        # Update UI state
        self._btn_start.configure(state="disabled")
        self._btn_stop.configure(state="normal")
        self._status_var.set(f"Simulando {cfg['num_cows']} vacas — TX: 0")
        self._tx_var.set("TX: 0")
        self._log_line(
            f"Simulacion iniciada: {cfg['num_cows']} vacas, "
            f"intervalo {cfg['interval_s']:.0f}s, "
            f"protocolo {cfg['protocol']}",
            tag="warn",
        )

    def _on_stop(self) -> None:
        if self._scheduler:
            self._scheduler.stop()
            self._scheduler = None
        self._btn_start.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        self._status_var.set("Detenido")
        self._log_line("Simulacion detenida.", tag="warn")

    def _on_scheduler_stopped(self) -> None:
        """Called from the scheduler thread via root.after() when it exits."""
        self._btn_start.configure(state="normal")
        self._btn_stop.configure(state="disabled")
        self._status_var.set("Detenido")

    # ------------------------------------------------------------------ #
    #  TX / movement callbacks (called on Tk main thread)                 #
    # ------------------------------------------------------------------ #

    def _on_tx_event(self, cow: Cow, result: SendResult) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        state_label = cow.state_label()

        if result.success:
            line = (
                f"[{ts}] {cow.deveui} | "
                f"lat={cow.lat:.5f} lon={cow.lon:.5f} | "
                f"bat={cow.battery:.0f}% | "
                f"{state_label} | "
                f"TX OK \u2192 {result.protocol}"
            )
            tag = "ok"
        else:
            line = (
                f"[{ts}] {cow.deveui} | "
                f"lat={cow.lat:.5f} lon={cow.lon:.5f} | "
                f"bat={cow.battery:.0f}% | "
                f"{state_label} | "
                f"TX ERROR: {result.detail}"
            )
            tag = "error"

        self._log_line(line, tag=tag)

        # Update status bar
        if self._scheduler:
            total = self._scheduler.tx_total
            num = len(self._cows)
            self._status_var.set(f"Simulando {num} vacas — TX: {total}")
            self._tx_var.set(f"TX: {total} (OK:{self._scheduler.tx_ok} ERR:{self._scheduler.tx_err})")

        # Save to CSV buffer
        self._log_entries.append({
            "timestamp": datetime.now().isoformat(),
            "deveui": cow.deveui,
            "lat": round(cow.lat, 7),
            "lon": round(cow.lon, 7),
            "battery": round(cow.battery, 2),
            "state": state_label,
            "speed_ms": round(cow.speed_ms, 3),
            "heading_deg": round(cow.heading_deg, 1),
            "success": result.success,
            "protocol": result.protocol,
            "detail": result.detail,
            "latency_ms": round(result.latency_ms, 1),
        })

    def _on_movement_event(self, cows: list) -> None:
        """Called after each movement update — no-op for now (could update a map)."""
        pass

    # ------------------------------------------------------------------ #
    #  CSV export                                                          #
    # ------------------------------------------------------------------ #

    def _on_export(self) -> None:
        if not self._log_entries:
            messagebox.showinfo("Sin datos", "No hay transmisiones registradas todavia.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="tropilla_export.csv",
        )
        if not path:
            return

        fields = list(self._log_entries[0].keys())
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader()
                writer.writerows(self._log_entries)
            messagebox.showinfo("Exportacion exitosa",
                                f"Se exportaron {len(self._log_entries)} registros a:\n{path}")
        except OSError as e:
            messagebox.showerror("Error al exportar", str(e))

    # ------------------------------------------------------------------ #
    #  Log helpers                                                         #
    # ------------------------------------------------------------------ #

    def _log_line(self, text: str, tag: str = "") -> None:
        self._log_text.configure(state="normal")
        self._log_text.insert("end", text + "\n", tag)
        self._log_text.see("end")
        self._log_text.configure(state="disabled")
        # Keep last 2000 lines to avoid memory bloat
        lines = int(self._log_text.index("end-1c").split(".")[0])
        if lines > 2000:
            self._log_text.configure(state="normal")
            self._log_text.delete("1.0", "200.0")
            self._log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    # ------------------------------------------------------------------ #
    #  Clean shutdown                                                      #
    # ------------------------------------------------------------------ #

    def on_close(self) -> None:
        if self._scheduler:
            self._scheduler.stop()
        self.destroy()
