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
- MQTT broker (e.g., Mosquitto)

## Installation

### 1. Install Dependencies

```bash
# Python packages
pip install gpiod aiomqtt
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
- `default_state` - Initial state for output pins (0 or 1, default: 0)
- `invert` - Whether to invert the logical state (true/false, default: false)

**Inversion feature:**

When `invert` is set to `true`, the logical state is inverted from the physical pin state. This is useful for relays that are active-low (activate when pin is LOW). For example:
- Sending `ON` (logical 1) sets the physical pin to 0 (LOW)
- Sending `OFF` (logical 0) sets the physical pin to 1 (HIGH)
- Home Assistant always sees the logical state, not the physical state

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

Example: `orangepi/gpio/gpiochip1/233/set` with payload `1` or `0`

Valid payloads: `1`, `0`, `ON`, `OFF`, `true`, `false`

**Note:** If `invert` is enabled for a pin, the logical state sent to Home Assistant will be inverted from the physical pin state. Home Assistant always sees the logical state.

### State Topic

Pin states are published automatically:

```
{base_topic}/gpiochip{chip}/{pin}
```

Payload: `1` (high/logical ON) or `0` (low/logical OFF)

When inversion is enabled, the published state represents the logical state, not the physical pin voltage level.

### Home Assistant Discovery

Discovery payloads are published to:

- Outputs: `homeassistant/switch/orangepi_gpio_{chip}_{pin}/config`
- Inputs: `homeassistant/binary_sensor/orangepi_gpio_{chip}_{pin}/config`

## Architecture

- **aiomqtt** - Async MQTT client for non-blocking communication
- **asyncio** - Event-driven architecture with FD-based input polling
- **Queue-based publishing** - Decouples GPIO events from MQTT network operations

## Files

- [`gpio_bridge.py`](gpio_bridge.py) - Main bridge application
- [`config.json`](config.json) - Configuration file
- [`gpio-bridge.service`](gpio-bridge.service) - Systemd service definition

## Troubleshooting

### Common Issues

**GPIO permissions:** If you get permission errors accessing GPIO, add your user to the `gpio` group:
```bash
sudo usermod -aG gpio $USER
# Log out and back in for changes to take effect
```

**libgpiod chip number:** If pins don't work, verify the correct gpiochip number using:
```bash
gpiodetect
gpioinfo
```

**View detailed logs:**
```bash
sudo journalctl -u gpio-bridge -f --no-pager | tail -50
```

### Testing GPIO Manually

You can test GPIO pins manually using gpiod tools:
```bash
# Read pin state
gpiomon gpiochip1/233

# Set pin output (replace with your pin numbers)
gpioset gpiochip1 233=1
gpioset gpiochip1 233=0
```
