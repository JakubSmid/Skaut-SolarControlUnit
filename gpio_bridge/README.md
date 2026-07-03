# GPIO MQTT Bridge

A Python service that bridges GPIO pins on Orange Pi (or similar Linux SBCs) with MQTT, enabling Home Assistant auto-discovery and remote control of GPIO outputs and monitoring of inputs.

## Features

- **MQTT-based GPIO control** - Control output pins via MQTT commands
- **Input monitoring** - Monitor input pin state changes and publish to MQTT
- **Home Assistant auto-discovery** - Automatically registers all pins in Home Assistant
- **Async architecture** - Uses `gpiod` with asyncio for non-blocking operation
- **Automatic reconnection** - Survives MQTT broker disconnections
- **Systemd integration** - Ready-to-deploy as a system service

## Requirements

- Linux SBC with GPIO support (tested on Orange Pi)
- Python 3.10+
- `libgpiod` library installed
- MQTT broker (e.g., Mosquitto)

## Installation

### 1. Install Dependencies

```bash
# Python packages
pip install gpiod aiomqtt

# libgpiod system library (if not already present)
sudo apt-get install libgpiod
```

### 2. Configure

Edit [config.json](gpio_bridge/config.json):

```json
{
    "mqtt": {
        "broker": "localhost",
        "port": 1883,
        "username": "your_mqtt_user",
        "password": "your_mqtt_password"
    },
    "gpio": {
        "base_topic": "orangepi/gpio",
        "input_pins": [],
        "output_pins": [
            {
                "gpiochip": 1,
                "pin": 233,
                "name": "relay_1"
            }
        ]
    }
}
```

**Configuration options:**

| Field | Description |
|-------|-------------|
| `mqtt.broker` | MQTT broker hostname or IP |
| `mqtt.port` | MQTT broker port (default: 1883) |
| `mqtt.username` | MQTT username (optional) |
| `mqtt.password` | MQTT password (optional) |
| `gpio.base_topic` | Base MQTT topic for GPIO messages |
| `gpio.input_pins` | List of input pin configurations |
| `gpio.output_pins` | List of output pin configurations |

**Pin configuration:**

- `gpiochip` - GPIO chip number (typically 0 or 1 on most SBCs)
- `pin` - Pin number within the chip
- `name` - Human-readable name (used in Home Assistant)

### 3. Run Manually

```bash
GPIO_CONFIG=config.json python gpio_bridge.py
```

### 4. Deploy as Systemd Service

Copy the service file and enable:

```bash
sudo cp gpio-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gpio-bridge
sudo systemctl start gpio-bridge
```

View logs:

```bash
sudo journalctl -u gpio-bridge -f
```

## MQTT Topics

### Command Topic (for outputs)

Send commands to control output pins:

```
{base_topic}/gpiochip{chip}/{pin}/set
```

Example: `orangepi/gpio_bridge/gpiochip1/233/set` with payload `1` or `0`

Valid payloads: `1`, `0`, `ON`, `OFF`, `true`, `false`

### State Topic

Pin states are published automatically:

```
{base_topic}/gpiochip{chip}/{pin}
```

Payload: `1` (high) or `0` (low)

### Home Assistant Discovery

Discovery payloads are published to:

- Outputs: `homeassistant/switch/orangepi_gpio_{chip}_{pin}/config`
- Inputs: `homeassistant/binary_sensor/orangepi_gpio_{chip}_{pin}/config`

## Architecture

- **libgpiod** - Low-level GPIO access via Linux libgpiod
- **aiomqtt** - Async MQTT client for non-blocking communication
- **asyncio** - Event-driven architecture with FD-based input polling
- **Queue-based publishing** - Decouples GPIO events from MQTT network operations

## Files

- [gpio_bridge.py](gpio_bridge.py) - Main bridge application
- [config.json](config.json) - Configuration file
- [gpio-bridge.service](gpio-bridge.service) - Systemd service definition
