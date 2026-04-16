# Tropilla Emulator v1.0

Manual de instrucciones completo para el emulador de dispositivos LoRa de seguimiento de ganado vacuno.

---

## Tabla de contenidos

1. [¿Qué es Tropilla Emulator?](#1-qué-es-tropilla-emulator)
2. [Requisitos del sistema](#2-requisitos-del-sistema)
3. [Instalación](#3-instalación)
4. [Inicio rápido](#4-inicio-rápido)
5. [Descripción de la interfaz](#5-descripción-de-la-interfaz)
   - 5.1 [Panel izquierdo — Campo y simulación](#51-panel-izquierdo--campo-y-simulación)
   - 5.2 [Panel derecho — Servidor y collar LoRa](#52-panel-derecho--servidor-y-collar-lora)
   - 5.3 [Barra de control inferior](#53-barra-de-control-inferior)
   - 5.4 [Área de log](#54-área-de-log)
6. [Configuración por protocolo](#6-configuración-por-protocolo)
   - 6.1 [MQTT](#61-mqtt)
   - 6.2 [HTTP Webhook](#62-http-webhook)
   - 6.3 [UDP Semtech](#63-udp-semtech)
7. [Parámetros LoRa explicados](#7-parámetros-lora-explicados)
8. [Comportamiento de las vacas simuladas](#8-comportamiento-de-las-vacas-simuladas)
9. [Formato del payload LoRaWAN](#9-formato-del-payload-lorawan)
10. [Exportación de datos](#10-exportación-de-datos)
11. [Configuración por defecto (default.json)](#11-configuración-por-defecto-defaultjson)
12. [Casos de uso típicos](#12-casos-de-uso-típicos)
13. [Solución de problemas](#13-solución-de-problemas)
14. [Referencia técnica de módulos](#14-referencia-técnica-de-módulos)

---

## 1. ¿Qué es Tropilla Emulator?

Tropilla Emulator es una herramienta de escritorio que simula una tropilla de collares LoRa instalados en ganado vacuno. Su propósito es permitir a desarrolladores e integradores **probar servidores LoRaWAN, gateways y plataformas IoT** sin necesidad de hardware real ni animales.

**Qué hace:**
- Genera N vacas virtuales con posiciones GPS realistas dentro de un campo circular.
- Mueve a cada vaca mediante un modelo matemático de pastoreo (proceso Ornstein-Uhlenbeck).
- Empaqueta la telemetría de cada vaca en un payload binario de 16 bytes, compatible con LoRaWAN.
- Envía cada paquete al servidor de destino por MQTT, HTTP o UDP Semtech.
- Muestra cada transmisión en un log en tiempo real con código de color.
- Permite exportar la sesión completa a CSV para análisis posterior.

**Qué NO hace:**
- No es un stack LoRaWAN completo (no implementa OTAA/ABP, ni cifrado AES-128).
- No genera tráfico de radio real.
- No reemplaza a un network server como ChirpStack o TTN en producción.

---

## 2. Requisitos del sistema

| Requisito        | Mínimo                         | Recomendado            |
|------------------|-------------------------------|------------------------|
| Sistema operativo| Windows 10, macOS 11, Linux   | Linux / macOS          |
| Python           | 3.9                           | 3.11 o superior        |
| RAM              | 256 MB libres                 | 512 MB                 |
| Pantalla         | 1024 × 768                    | 1280 × 800 o superior  |
| Red              | No requerida para pruebas locales | Conexión al broker/servidor destino |

**Dependencias Python:**

| Paquete     | Versión mínima | Uso                                  |
|-------------|---------------|--------------------------------------|
| `numpy`     | 1.24          | Proceso Ornstein-Uhlenbeck           |
| `requests`  | 2.28          | Transporte HTTP Webhook              |
| `paho-mqtt` | 1.6           | Transporte MQTT                      |
| `tkinter`   | incluido      | Interfaz gráfica (viene con Python)  |

> **Nota Linux:** Si `tkinter` no está instalado, ejecutar:
> ```bash
> sudo apt install python3-tk      # Debian / Ubuntu
> sudo dnf install python3-tkinter # Fedora
> ```

---

## 3. Instalación

### Paso 1 — Obtener el código

```bash
git clone https://github.com/tu-usuario/tropilla-emulator.git
cd tropilla-emulator
```

O simplemente copiar la carpeta del proyecto en cualquier directorio.

### Paso 2 — Crear un entorno virtual (recomendado)

```bash
# Crear el entorno
python -m venv .venv

# Activarlo
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows (cmd)
.venv\Scripts\Activate.ps1       # Windows (PowerShell)
```

### Paso 3 — Instalar dependencias

```bash
pip install -r requirements.txt
```

Salida esperada:
```
Successfully installed numpy-1.26.x paho-mqtt-1.6.x requests-2.31.x
```

### Paso 4 — Verificar la instalación

```bash
python -c "from emulator.gui import EmulatorApp; print('OK')"
```

Si imprime `OK`, la instalación es correcta.

---

## 4. Inicio rápido

```bash
python main.py
```

Se abre la ventana principal. Para una prueba rápida sin servidor externo:

1. Dejar todos los valores por defecto.
2. Cambiar el protocolo a **HTTP Webhook**.
3. Poner como host `httpbin.org` y puerto `80`. *(httpbin refleja el POST y responde 200)*
4. Hacer clic en **Iniciar simulación**.
5. Observar el log: las líneas verdes confirman que el servidor responde.
6. Hacer clic en **Detener** y luego en **Exportar logs CSV**.

---

## 5. Descripción de la interfaz

La ventana está dividida en cuatro zonas:

```
┌──────────────────────────┬──────────────────────────────┐
│   Panel izquierdo        │   Panel derecho              │
│   Campo & Simulación     │   Servidor + Collar LoRa     │
├──────────────────────────┴──────────────────────────────┤
│   [Iniciar]  [Detener]  [Exportar CSV]   Estado  TX:N   │
├─────────────────────────────────────────────────────────┤
│   Área de log (scrollable, color por resultado)         │
└─────────────────────────────────────────────────────────┘
```

### 5.1 Panel izquierdo — Campo y simulación

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| **Latitud central** | float | Latitud del centro geográfico del campo | `-32.9500` |
| **Longitud central** | float | Longitud del centro del campo | `-60.6600` |
| **Radio del campo (m)** | int | Radio en metros del círculo de pastoreo | `2000` |
| **Cantidad de vacas** | int 1–200 | Número de dispositivos a simular | `10` |
| **Periodicidad de reportes (min)** | float | Cada cuántos minutos transmite cada vaca | `1.0` |
| **Semilla aleatoria** | int (opcional) | Fija la secuencia aleatoria para reproducibilidad | `42` (dejar vacío para aleatorio) |

**Notas:**
- El **radio** determina el área de pastoreo. 2 000 m es aproximadamente 1 257 hectáreas (12,6 km²), un campo grande para ganadería extensiva.
- La **semilla aleatoria** es útil para reproducir exactamente la misma sesión en pruebas automatizadas. Si se deja vacío, cada ejecución genera trayectorias diferentes.
- Con **200 vacas** y un intervalo de **1 minuto**, el emulador genera ~3,3 paquetes por segundo. Asegurarse de que el servidor destino pueda absorber esa tasa.

### 5.2 Panel derecho — Servidor y collar LoRa

#### Sección "Servidor destino"

| Campo | Tipo | Descripción |
|-------|------|-------------|
| **Protocolo** | dropdown | Modo de transporte: `MQTT`, `HTTP Webhook` o `UDP Semtech` |
| **URL / Host del servidor** | string | IP o hostname del broker/servidor destino |
| **Puerto** | int | Puerto TCP/UDP del servidor |
| **Topic MQTT** | string | Solo visible si el protocolo es MQTT. Admite `{devEUI}` como placeholder |
| **Bearer token / API Key** | string | Token de autenticación (opcional). Se envía como `Authorization: Bearer <token>` en HTTP, o como contraseña en MQTT |
| **Timeout conexión (s)** | float | Tiempo máximo de espera por respuesta antes de marcar el TX como error |

#### Sección "Collar LoRa"

| Campo | Tipo | Descripción |
|-------|------|-------------|
| **DevEUI** | 16 hex chars | Identificador único del dispositivo (se usa como base; cada vaca tiene el suyo generado automáticamente) |
| **AppEUI** | 16 hex chars | Identificador de la aplicación LoRaWAN |
| **AppKey** | 32 hex chars | Clave de derivación de sesión (referencial; no se usa en cifrado real) |
| **Spreading Factor** | dropdown | SF7 a SF12. A mayor SF, mayor alcance y menor velocidad de datos |
| **Bandwidth** | dropdown | 125 kHz, 250 kHz o 500 kHz |
| **Frecuencia (MHz)** | float | Frecuencia central del canal LoRa (ej: `915.2` para AU915, `868.1` para EU868) |
| **fPort** | int 1–223 | Puerto de aplicación LoRaWAN que identifica el tipo de mensaje |

### 5.3 Barra de control inferior

| Control | Descripción |
|---------|-------------|
| **Iniciar simulación** (verde) | Valida los parámetros, crea las vacas y arranca el scheduler en background |
| **Detener** (rojo) | Detiene el scheduler, cierra conexiones y vuelve al estado inicial. Se habilita solo durante la simulación |
| **Exportar logs CSV** | Abre un diálogo para guardar todos los eventos TX de la sesión actual en un archivo CSV |
| **Etiqueta de estado** | Muestra `Detenido` o `Simulando N vacas — TX: X` en tiempo real |
| **Contador TX** | Muestra `TX: total (OK:N ERR:N)` actualizado tras cada transmisión |

### 5.4 Área de log

Cada línea del log sigue el formato:

```
[HH:MM:SS] <DevEUI> | lat=<lat> lon=<lon> | bat=<N>% | <estado> | TX OK → <protocolo>
[HH:MM:SS] <DevEUI> | lat=<lat> lon=<lon> | bat=<N>% | <estado> | TX ERROR: <descripción>
```

**Código de colores:**
- **Verde** — TX exitoso (el servidor respondió correctamente).
- **Rojo** — TX fallido (conexión rechazada, timeout, HTTP 4xx/5xx).
- **Naranja** — Eventos de control (inicio, detención de la simulación).

El log mantiene las últimas **2 000 líneas** para no consumir memoria en sesiones largas.

---

## 6. Configuración por protocolo

### 6.1 MQTT

Conecta al broker usando `paho-mqtt` y publica el JSON ChirpStack en el topic configurado.

**Parámetros típicos:**

| Campo | Valor ejemplo |
|-------|--------------|
| Host | `localhost` o `broker.hivemq.com` |
| Puerto | `1883` (sin TLS) o `8883` (con TLS) |
| Topic | `application/1/device/{devEUI}/event/up` |
| Token | dejar vacío si el broker es público, o poner el password si requiere auth |

> El placeholder `{devEUI}` en el topic se reemplaza automáticamente con el DevEUI de cada vaca en cada transmisión.

**Comportamiento interno:**
- La conexión al broker se establece de forma lazy al primer TX.
- Si el broker se desconecta, se intenta reconectar automáticamente en el siguiente ciclo.
- Se usa QoS 0 (fire-and-forget) para maximizar la tasa de transmisión.

**Prueba rápida con Mosquitto local:**
```bash
# Terminal 1 — broker
mosquitto

# Terminal 2 — suscriptor
mosquitto_sub -t "application/1/device/#"

# Luego iniciar Tropilla Emulator con host=localhost, puerto=1883
```

### 6.2 HTTP Webhook

Realiza un `POST` al endpoint configurado con el JSON ChirpStack como body.

**Parámetros típicos:**

| Campo | Valor ejemplo |
|-------|--------------|
| Host | `192.168.1.100` o `mi-servidor.com` |
| Puerto | `8080` |
| Token | `eyJhbGciOiJIUzI1NiJ9...` (si el servidor requiere autenticación) |

**Headers enviados:**
```
Content-Type: application/json
Authorization: Bearer <token>   ← solo si se configuró un token
```

**Política de reintentos:** Si el servidor no responde o devuelve un error de red, el emulador reintenta hasta 3 veces con espera exponencial (0.5 s → 1 s). Errores HTTP 4xx/5xx se reportan como TX ERROR sin reintento.

**Prueba rápida con servidor de eco:**
```bash
# Usando httpbin (no requiere instalación):
# Host: httpbin.org  Puerto: 80

# O localmente con Python:
python -m http.server 8080
```

**Formato del JSON enviado (estilo ChirpStack v3):**
```json
{
  "devEUI": "54524F50494C0003",
  "time": "2024-01-15T14:32:01.123Z",
  "fPort": 2,
  "adr": true,
  "dr": 5,
  "spreadingFactor": 7,
  "rssi": -78,
  "snr": 8.5,
  "data": "AFML3AC2EmVVAAAcA1C2OA=="
}
```

### 6.3 UDP Semtech

Construye y envía paquetes `PUSH_DATA` del protocolo Semtech UDP Packet Forwarder, el mismo que usan los gateways LoRa físicos (RAK, Dragino, Multitech, etc.).

**Parámetros típicos:**

| Campo | Valor ejemplo |
|-------|--------------|
| Host | `localhost` o IP del network server |
| Puerto | `1700` (puerto estándar Semtech) |

**Estructura del paquete UDP:**
```
Byte  0    : version = 0x02
Bytes 1–2  : token random (uint16, big-endian)
Byte  3    : identifier = 0x00 (PUSH_DATA)
Bytes 4–11 : gwEUI (8 bytes, generado aleatoriamente al inicio de la sesión)
Bytes 12+  : JSON con array "rxpk"
```

**Prueba rápida con ChirpStack:**
```
Host: IP del servidor ChirpStack
Puerto: 1700
```
El network server responderá con `PUSH_ACK` (byte 3 = `0x01`). El emulador lo detecta y reporta `TX OK`.

> Si no llega ACK (servidor inactivo, firewall, etc.), el paquete se considera enviado igualmente (`TX OK — no ACK`), ya que UDP es no confirmado.

---

## 7. Parámetros LoRa explicados

### Spreading Factor (SF)

El SF controla el compromiso entre alcance y velocidad de datos:

| SF  | Velocidad aprox. | Alcance relativo | Time on Air (16 bytes) |
|-----|-----------------|-----------------|------------------------|
| SF7 | ~5 500 bps      | Corto           | ~56 ms                 |
| SF8 | ~3 125 bps      | Medio           | ~103 ms                |
| SF9 | ~1 758 bps      | Medio-largo     | ~185 ms                |
| SF10| ~977 bps        | Largo           | ~370 ms                |
| SF11| ~537 bps        | Muy largo       | ~741 ms                |
| SF12| ~293 bps        | Máximo          | ~1 482 ms              |

Para ganado en campo abierto se recomienda **SF9 a SF11**. El emulador ajusta el RSSI y SNR simulados acorde al SF seleccionado.

### Bandwidth (BW)

| BW      | Uso típico                           |
|---------|--------------------------------------|
| 125 kHz | Estándar LoRaWAN (recomendado)       |
| 250 kHz | Mayor velocidad, menor sensibilidad  |
| 500 kHz | Solo canales de subida en AU915/US915|

### Frecuencia

Usar la frecuencia correcta para la región:

| Región | Plan de frecuencias | Ejemplo de canal |
|--------|---------------------|-----------------|
| Argentina / AU | AU915 | 915.2 MHz |
| Europa | EU868 | 868.1 MHz |
| EE.UU. | US915 | 902.3 MHz |
| Asia | AS923 | 923.2 MHz |

### DevEUI, AppEUI, AppKey

En este emulador, el DevEUI del formulario se usa como **referencia de configuración**. Cada vaca recibe automáticamente un DevEUI único generado como:

```
Bytes 0–5 : "TROPIL"  →  54 52 4F 50 49 4C
Bytes 6–7 : índice de la vaca como uint16 big-endian
```

Ejemplos:
```
Vaca 0   →  54524F50494C0000
Vaca 1   →  54524F50494C0001
Vaca 255 →  54524F50494C00FF
```

El AppEUI y AppKey se incluyen como referencia en la configuración guardada, pero no se utilizan en el cifrado del payload (el emulador envía datos en claro como haría un gateway, no como haría un nodo).

---

## 8. Comportamiento de las vacas simuladas

### Estados de comportamiento

Cada vaca puede estar en uno de cuatro estados:

| Estado | Label en log | Velocidad típica | Descripción |
|--------|-------------|-----------------|-------------|
| `pastando` | `grazing` | 0.5–1.5 km/h | La vaca se mueve lentamente mientras come |
| `caminando` | `walking` | 2–4 km/h | Desplazamiento activo hacia agua, sombra, etc. |
| `descansando` | `resting` | ~0 km/h | La vaca está quieta, velocidad decae a cero |
| `fuera_de_area` | `OUTSIDE` | hasta 4 km/h | La vaca superó el perímetro del campo |

Las transiciones entre estados ocurren de forma aleatoria con probabilidades predefinidas:
- Desde `pastando`: 25 % camina, 75 % descansa (cuando decide cambiar).
- Desde `caminando`: 60 % vuelve a pastar, 40 % descansa.
- Desde `descansando`: 70 % va a pastar, 30 % camina.

La probabilidad de cambio de estado en cada paso es del **2 %** (es decir, en promedio el estado cambia cada 50 pasos × 5 s = ~4 minutos).

### Modelo de movimiento (Ornstein-Uhlenbeck)

A diferencia de un random walk puro (donde cada paso es completamente independiente), el proceso OU produce movimiento **correlacionado**: la vaca tiende a seguir moviéndose en la misma dirección general durante un rato, y gradualmente gira. Esto imita el comportamiento real de pastoreo donde el animal recorre una zona antes de desplazarse a otra.

La ecuación que se resuelve en cada paso de 5 segundos es:

```
dv = θ · (μ − v) · dt  +  σ · √dt · N(0,1)
```

Donde:
- `v` — velocidad actual (vector 2D en m/s)
- `θ = 0.15` — fuerza de reversión hacia la media (mayor = más difusivo)
- `μ = 0` — velocidad media (sin deriva neta)
- `σ = 0.05` en pastoreo, `0.15` caminando — volatilidad del movimiento
- `N(0,1)` — ruido gaussiano estándar

### Manejo del perímetro

Cuando una vaca se acerca al límite del campo, **no rebota bruscamente** sino que recibe un drift correctivo hacia el centro proporcional a cuánto se pasó:

```
fuerza_correctiva = 0.5 + distancia_sobrepase / radio_campo
```

Si la vaca está más de **500 m fuera** del campo, se aplica un clamp duro que la trae de vuelta al límite.

### Alarma

Si una vaca permanece **más de 5 minutos** fuera del campo, se activa el flag de alarma (`bit3` del byte de flags). La alarma se desactiva automáticamente cuando la vaca regresa al interior del campo (al menos al 90 % del radio).

### Batería

La batería drena **~0.001 %** por cada transmisión, con variación aleatoria de ±20 % para simular diferencias de temperatura. Una vaca que transmite cada minuto durante 24 horas perderá aproximadamente **1.44 %** de batería por día, lo que da una autonomía simulada de ~69 días — realista para collares LoRa comerciales.

---

## 9. Formato del payload LoRaWAN

El payload binario ocupa exactamente **16 bytes** en formato big-endian, diseñado para ser compacto incluso con SF12 (time on air < 1.5 s).

### Mapa de bytes

| Bytes | Campo | Tipo | Fórmula / Rango |
|-------|-------|------|----------------|
| 0–3 | Latitud | `int32` BE | `round((lat + 90) × 100 000)` |
| 4–7 | Longitud | `int32` BE | `round((lon + 180) × 100 000)` |
| 8 | Batería | `uint8` | 0–100 (%) |
| 9 | Flags | `uint8` bitmask | ver tabla de flags |
| 10–11 | Velocidad | `uint16` BE | en cm/s (máx 655 m/s) |
| 12–13 | Rumbo | `uint16` BE | décimas de grado, 0–3599 (0.0°–359.9°) |
| 14 | RSSI | `int8` | dBm, rango −128 a +127 |
| 15 | SNR × 10 | `int8` | SNR en décimas de dB |

### Byte de flags (byte 9)

| Bit | Máscara | Significado |
|-----|---------|-------------|
| 0 | `0x01` | `moving` — la vaca está en movimiento activo |
| 1 | `0x02` | `outside_area` — fuera del campo |
| 2 | `0x04` | `low_battery` — batería < 20 % |
| 3 | `0x08` | `alarm` — alarma activa (fuera del campo > 5 min) |
| 4–7 | — | reservados (siempre 0) |

### Ejemplo de decodificación

Payload hex: `00570B6C00B6126A5500001C0350B638`

```
Bytes 0–3 : 00 57 0B 6C  →  int32 = 5703532  →  lat = 5703532/1e5 − 90  = -32.96468
Bytes 4–7 : 00 B6 12 6A  →  int32 = 11931242 →  lon = 11931242/1e5 − 180 = -60.68758
Byte  8   : 55           →  uint8 = 85       →  bat = 85 %
Byte  9   : 00           →  flags = 0b00000000 → ninguna alarma, quieta
Bytes 10–11: 00 1C       →  uint16 = 28      →  speed = 0.28 m/s = 1.0 km/h
Bytes 12–13: 03 50       →  uint16 = 848     →  heading = 84.8°
Byte  14  : B6           →  int8 = -74       →  RSSI = -74 dBm
Byte  15  : 38           →  int8 = 56        →  SNR = 5.6 dB
```

### Precisión GPS

Con el factor de escala `× 100 000`:
- **Resolución:** 1 unidad = 0.00001° ≈ **1.11 m** en latitud
- **Rango latitud:** −90° a +90° → int32 de 0 a 18 000 000 (cabe en int32)
- **Rango longitud:** −180° a +180° → int32 de 0 a 36 000 000 (cabe en int32)

---

## 10. Exportación de datos

Al hacer clic en **Exportar logs CSV**, se abre un diálogo para elegir el destino. El archivo contiene una fila por cada transmisión de la sesión.

### Columnas del CSV

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `timestamp` | ISO 8601 | Fecha y hora exacta de la transmisión |
| `deveui` | string | DevEUI de la vaca |
| `lat` | float | Latitud en el momento de la TX |
| `lon` | float | Longitud en el momento de la TX |
| `battery` | float | Nivel de batería (%) |
| `state` | string | Estado conductual (grazing / walking / resting / OUTSIDE) |
| `speed_ms` | float | Velocidad en m/s |
| `heading_deg` | float | Rumbo en grados (0–359.9) |
| `success` | bool | True si el servidor respondió OK |
| `protocol` | string | Protocolo usado (MQTT / HTTP / UDP) |
| `detail` | string | Detalle adicional (topic MQTT, código HTTP, etc.) |
| `latency_ms` | float | Tiempo de respuesta del servidor en milisegundos |

### Ejemplo de análisis en Python

```python
import pandas as pd

df = pd.read_csv("tropilla_export.csv", parse_dates=["timestamp"])

# Trayectoria de una vaca
vaca = df[df["deveui"] == "54524F50494C0000"]
print(vaca[["timestamp", "lat", "lon", "state"]].head(20))

# Tasa de errores por protocolo
print(df.groupby("protocol")["success"].mean())

# Tiempo de respuesta promedio del servidor
print(f"Latencia media: {df['latency_ms'].mean():.1f} ms")
```

---

## 11. Configuración por defecto (default.json)

El archivo `config/default.json` define los valores que aparecen al abrir la aplicación. Puede editarse con cualquier editor de texto.

```json
{
  "field": {
    "lat": -32.9500,
    "lon": -60.6600,
    "radius_m": 2000,
    "num_cows": 10,
    "report_interval_min": 1.0,
    "random_seed": null
  },
  "server": {
    "protocol": "HTTP Webhook",
    "host": "localhost",
    "port": 8080,
    "mqtt_topic": "application/1/device/{devEUI}/event/up",
    "bearer_token": "",
    "timeout_s": 5
  },
  "lora": {
    "dev_eui": "54524F5000000001",
    "app_eui": "54524F5041505000",
    "app_key": "54524F504150500054524F5041505000",
    "spreading_factor": "SF7",
    "bandwidth": "125kHz",
    "frequency_mhz": 915.2,
    "fport": 2
  }
}
```

**Tip:** Para un equipo que trabaja con el mismo servidor, editar `default.json` con los parámetros correctos una vez y todos los usuarios arrancaran con la configuración correcta sin tener que configurar nada.

---

## 12. Casos de uso típicos

### Caso A — Probar un broker MQTT local (Mosquitto)

```bash
# 1. Instalar e iniciar Mosquitto
sudo apt install mosquitto mosquitto-clients
mosquitto &

# 2. Suscribirse al topic en otra terminal
mosquitto_sub -v -t "application/1/device/#"

# 3. Configurar Tropilla Emulator:
#    Protocolo: MQTT
#    Host: localhost
#    Puerto: 1883
#    Topic: application/1/device/{devEUI}/event/up
#    Vacas: 5  |  Intervalo: 0.5 min

# 4. Iniciar simulación → ver los JSON aparecer en la terminal de mosquitto_sub
```

### Caso B — Probar una API REST con autenticación

```bash
# Configurar Tropilla Emulator:
#   Protocolo: HTTP Webhook
#   Host: api.mi-plataforma.com
#   Puerto: 443  (o 80 si no usa TLS)
#   Token: <API key de la plataforma>
#   Vacas: 20  |  Intervalo: 2 min

# El emulador enviará:
# POST http://api.mi-plataforma.com:443
# Authorization: Bearer <API key>
# Content-Type: application/json
# Body: { "devEUI": "...", "data": "...", ... }
```

### Caso C — Probar ChirpStack con protocolo Semtech UDP

```bash
# Asegurarse de que el network server escucha en UDP 1700
# (ChirpStack Gateway Bridge lo hace por defecto)

# Configurar Tropilla Emulator:
#   Protocolo: UDP Semtech
#   Host: 192.168.1.50   (IP del servidor ChirpStack)
#   Puerto: 1700
#   Vacas: 50  |  Intervalo: 1 min
#   SF: SF9  |  Frecuencia: 915.2
```

### Caso D — Prueba de carga (stress test)

Para evaluar cuántos paquetes por segundo aguanta el servidor:

```
Vacas: 200
Intervalo: 0.1 min (6 segundos)
→ ~33 paquetes/segundo
```

Monitorear la columna `latency_ms` en el CSV exportado para detectar degradación.

### Caso E — Reproducir un escenario exacto

```
Semilla aleatoria: 12345
Vacas: 10
Intervalo: 1 min
```

Con la misma semilla, las trayectorias serán idénticas en cada ejecución, lo que permite reproducir bugs o comparar el comportamiento del servidor ante los mismos datos.

---

## 13. Solución de problemas

### La ventana no se abre / "No module named tkinter"

```bash
# Linux
sudo apt install python3-tk

# macOS: reinstalar Python desde python.org (el de brew no incluye tkinter por defecto)
brew install python-tk@3.11
```

### "TX ERROR: Connection refused" en todas las transmisiones

- Verificar que el servidor de destino está corriendo y accesible.
- Comprobar host y puerto. Un error común es poner el puerto equivocado (ej: `443` para HTTP plano).
- Si hay firewall, asegurarse de que el puerto esté abierto.
- Aumentar el **timeout** a 10–15 segundos si el servidor es lento.

### "TX ERROR: Could not connect to MQTT broker"

- Verificar que Mosquitto (u otro broker) está corriendo: `ps aux | grep mosquitto`
- Comprobar que el broker acepta conexiones sin autenticación, o que el token sea correcto.
- Para brokers en la nube, verificar que el puerto 1883 no esté bloqueado (algunos ISP bloquean 1883; en ese caso, usar 8883 con TLS o 80/443 si el broker lo soporta).

### El log muestra TX OK pero el servidor no recibe nada (UDP)

- UDP no es confiable por diseño. Verificar con `tcpdump` o Wireshark que los paquetes llegan al servidor.
- Si hay NAT de por medio, los paquetes UDP pueden perderse sin aviso.
- Verificar que el Gateway Bridge de ChirpStack está configurado para escuchar en `0.0.0.0:1700` y no solo en `127.0.0.1:1700`.

### Las vacas no se mueven (todas en la misma posición)

- Esto puede ocurrir si el intervalo de TX es muy corto (< 5 segundos) y el movimiento no ha actualizado aún. Las posiciones se actualizan cada **5 segundos internos** independientemente del intervalo de TX.

### La GUI se congela durante la simulación

- La GUI nunca debería congelarse ya que el scheduler corre en un thread separado. Si ocurre, puede ser un problema de timeout muy largo (ej: 30 s) combinado con un servidor que no responde: el thread de envío queda bloqueado y la cola de callbacks de `root.after()` se llena.
- Solución: reducir el **timeout** a 3–5 segundos.

### Alto uso de CPU con muchas vacas

- Con 200 vacas y un intervalo de 6 segundos se generan ~33 TX/s. Cada TX involucra serialización JSON y una llamada de red.
- Si el servidor es local, la latencia es < 1 ms y el CPU debería mantenerse bajo.
- Si el servidor es remoto con latencia > 100 ms, el thread de envío puede saturarse. En ese caso, aumentar el intervalo de TX.

---

## 14. Referencia técnica de módulos

### `emulator/field.py` — `Field`

```python
Field(lat, lon, radius_m)
```

| Método | Descripción |
|--------|-------------|
| `haversine_distance(lat1, lon1, lat2, lon2)` | Distancia en metros entre dos coordenadas |
| `distance_from_centre(lat, lon)` | Distancia al centro del campo |
| `is_inside(lat, lon)` | True si el punto está dentro del campo |
| `offset_point(lat, lon, bearing_deg, distance_m)` | Desplaza un punto en una dirección y distancia |
| `bearing_to_centre(lat, lon)` | Rumbo desde un punto hacia el centro del campo |
| `clamp_to_field(lat, lon, margin_m=50)` | Devuelve el punto corregido si está fuera del campo |
| `random_point_inside(rng)` | Genera un punto aleatorio uniformemente distribuido en el disco |

### `emulator/cattle.py` — `Cow`

```python
Cow(index, field, rng)
```

| Atributo / Método | Descripción |
|-------------------|-------------|
| `deveui` | DevEUI único (hex string de 16 chars) |
| `lat`, `lon` | Posición actual |
| `battery` | Nivel de batería (0–100 %) |
| `state` | Estado conductual actual |
| `speed_ms` | Velocidad en m/s |
| `heading_deg` | Rumbo en grados |
| `alarm` | True si la alarma está activa |
| `update(dt)` | Avanza el estado de la vaca en dt segundos |
| `drain_battery()` | Drena la batería una unidad de TX |
| `flags_byte()` | Devuelve el byte de flags listo para el payload |
| `state_label()` | Etiqueta en inglés del estado (para el log) |

### `emulator/payload.py` — `PayloadEncoder`

```python
PayloadEncoder(fport=2, sf="SF7")
```

| Método | Descripción |
|--------|-------------|
| `encode_binary(lat, lon, battery, flags, speed_ms, heading_deg)` | Devuelve bytes de 16 bytes |
| `decode_binary(data)` | Desempaqueta un payload de 16 bytes en dict |
| `encode_chirpstack(deveui, ...)` | Devuelve el dict JSON estilo ChirpStack |
| `encode_chirpstack_json(deveui, ...)` | Devuelve la cadena JSON serializada |
| `encode_semtech_rxpk(deveui, ..., freq_mhz)` | Devuelve el dict `rxpk` para UDP Semtech |

### `emulator/gateway.py` — `Gateway`

```python
Gateway(config: GatewayConfig, on_log=None)
```

| Método | Descripción |
|--------|-------------|
| `send(deveui, payload_json, freq_mhz)` | Envía por el protocolo configurado, devuelve `SendResult` |
| `close()` | Cierra conexiones MQTT y socket UDP |

`SendResult`:
```python
@dataclass
class SendResult:
    success: bool       # True si el servidor respondió OK
    protocol: str       # "MQTT" | "HTTP" | "UDP"
    detail: str         # Descripción del resultado o error
    latency_ms: float   # Tiempo de respuesta en milisegundos
```

### `emulator/scheduler.py` — `Scheduler`

```python
Scheduler(root, cows, field, gateway, encoder, interval_s, freq_mhz,
          on_tx, on_movement, on_stop)
```

| Método | Descripción |
|--------|-------------|
| `start()` | Arranca el thread de simulación |
| `stop()` | Detiene la simulación y libera recursos |
| `tx_total` | Total de transmisiones desde el inicio |
| `tx_ok` | Transmisiones exitosas |
| `tx_err` | Transmisiones fallidas |

---

## Licencia

MIT — libre para uso personal, educativo y comercial.
