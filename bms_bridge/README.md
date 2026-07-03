# BMS MQTT Bridge

A Python service that bridges JK (Jikong) BMS batteries via BLE with MQTT, enabling Home Assistant auto-discovery and real-time monitoring of battery telemetry.

## Features

- **BLE connectivity** - Connects to JK BMS batteries via Bluetooth Low Energy
- **Real-time telemetry** - Publishes cell voltages, currents, temperatures, and more
- **Home Assistant auto-discovery** - Automatically registers all sensors in Home Assistant
- **Async architecture** - Non-blocking BLE and MQTT operations using asyncio
- **Automatic reconnection** - Survives both BLE and MQTT disconnections
- **Systemd integration** - Ready-to-deploy as a system service

## Requirements

- Linux SBC with BLE support (tested on Orange Pi)
- Python 3.10+
- Bluetooth LE hardware (USB dongle or built-in)
- MQTT broker (e.g., Mosquitto)
- JK BMS battery with BLE enabled

## Installation

### 1. Install Dependencies

```bash
# Python packages
pip install bleak aiomqtt

# BlueZ (Bluetooth stack) - usually pre-installed on Linux
sudo apt-get install bluez bluez-tools
```

### 2. Configure Environment Variables

Set the following environment variables:

```bash
export BMS_MAC="C8:47:80:22:29:9F"    # MAC address of your JK BMS
export MQTT_HOST="localhost"           # MQTT broker hostname
```

Or run with inline variables:

```bash
BMS_MAC="C8:47:80:22:29:9F" MQTT_HOST="localhost" python main.py
```

### 3. Run Manually

```bash
python main.py
```

### 4. Deploy as Systemd Service

Copy the service file and enable:

```bash
sudo cp jk-bms-mqtt.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable jk-bms-mqtt
sudo systemctl start jk-bms-mqtt
```

View logs:

```bash
sudo journalctl -u jk-bms-mqtt -f
```

## MQTT Topics

### State Topic

All sensor data is published as JSON to:

```
orangepi/jk_bms/{mac_address}/state
```

Example payload:
```json
{
  "Voltage_Cell01": 3.245,
  "Voltage_Cell02": 3.248,
  "Battery_Current": 12.5,
  "Battery_Voltage": 51.2,
  "Percent_Remain": 75,
  ...
}
```

### Home Assistant Discovery

Discovery payloads are published to:

```
homeassistant/sensor/jk_bms_{mac}/{sensor_name}/config
```

Each sensor (cell voltage, temperature, current, etc.) gets its own discovery config.

## Data Fields

The bridge publishes all data from the JK BMS protocol:

| Category | Fields |
|----------|--------|
| **Cell Data** | `Voltage_Cell01-32`, `Resistance_Cell01-32` |
| **Battery Stats** | `Battery_Voltage`, `Battery_Current`, `Battery_Power` |
| **Temperature** | `MOS_Temp`, `Battery_T1`, `Battery_T2` |
| **Capacity** | `Percent_Remain`, `Capacity_Remain`, `Nominal_Capacity`, `Cycle_Count` |
| **Settings** | Device info, protection thresholds (read-only) |

## Architecture

```
┌─────────────┐     BLE      ┌──────────────┐     MQTT      ┌─────────────┐
│  JK BMS     │◄────────────►│  BleClient   │             │             │
│  (Battery)  │              │              │             │             │
└─────────────┘              └──────┬───────┘             │             │
                                    │                     │             │
                              ┌─────▼───────┐             │             │
                              │  DataStore  │             │             │
                              └─────┬───────┘             │             │
                                    │                     │             │
                              ┌─────▼────────┐   ┌────────▼────────┐   │
                              │ BmsMqttClient│──►│  MQTT Broker    │   │
                              └──────────────┘   └─────────────────┘   │
                                                                       │
                         ┌─────────────────────────────────────────────┤
                         │            Home Assistant                   │
                         └─────────────────────────────────────────────┘
```

- **ble_client.py** - `BleClient` class handles BLE connection and packet parsing
- **bms_mqtt.py** - `BmsMqttClient` class publishes discovery configs and state data
- **protocol.py** - `BmsFrame` base class and response types for JK protocol
- **main.py** - Entry point with `DataStore` for thread-safe data sharing

## Troubleshooting

### BLE Connection Issues

1. Ensure Bluetooth is enabled:
   ```bash
   sudo hciconfig hci0 up
   ```

2. Check if device is discoverable:
   ```bash
   sudo bluetoothctl scan on
   ```

3. You may need to run as root for BLE access:
   ```bash
   sudo python main.py
   ```

### MQTT Connection Issues

Check the logs for connection errors:
```bash
sudo journalctl -u jk-bms-mqtt -n 50
```

## Files

- [main.py](main.py) - Entry point and orchestration
- [ble_client.py](ble_client.py) - BLE client implementation
- [bms_mqtt.py](bms_mqtt.py) - MQTT publishing logic
- [protocol.py](protocol.py) - JK BMS protocol definitions
- [jk-bms-mqtt.service](jk-bms-mqtt.service) - Systemd service definition
