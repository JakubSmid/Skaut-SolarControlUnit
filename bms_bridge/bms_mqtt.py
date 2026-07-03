import json
import logging
from ble_client import BleClient
from protocol import CellDataResponse

class BmsMqttClient:
    def __init__(self, mqtt_client, bms_client: BleClient):
        self.logger = logging.getLogger(__name__)

        self.mqtt_client = mqtt_client
        self.bms_client = bms_client

        mac_address = bms_client.address
        self.mac = mac_address.replace(":", "").lower()
        self.state_topic = f"orangepi/jk_bms/{self.mac}/state"

        # This groups all sensors under one physical device in the HA UI
        self.device_info = {
            "identifiers": [f"jk_bms/{self.mac}"],
            "manufacturer": "Jikong",
            "name": bms_client.device_info["Device_Name"],
            "model": bms_client.device_info["Device_Model"],
            "serial_number": bms_client.device_info["Serial_Number"],
            "sw_version": bms_client.device_info["Software_Version"],
            "hw_version": bms_client.device_info["Hardware_Version"],
        }

    async def publish_discovery(self):
        """Generates and publishes HA Auto-Discovery configs based on your LAYOUT."""
        self.logger.info("Publishing Home Assistant MQTT Discovery configs...")
        
        for t, length, name, unit in CellDataResponse.LAYOUT:
            if t == "discard":
               continue

            if name.startswith(("Voltage_Cell", "Resistance_Cell")):
                cell_number = int(name[-2:])
                if cell_number > self.bms_client.n_cells:
                    continue

            # Map your units to Home Assistant Device Classes for nice UI icons
            device_class = None
            state_class = "measurement" # Tells HA to graph this historically
            entity_category = None
            suggested_display_precision = None
            
            if any(x in name for x in ["Cell", "Time", "Balance", "Capacity", "Header", "Record"]):
                state_class = None
                entity_category = "diagnostic"

            if any(x in name for x in ["Cycle", "Time"]):
                state_class = "total_increasing"

            if unit == "V":
                device_class = "voltage"
                suggested_display_precision = 3
            elif unit == "A": device_class = "current"
            elif unit == "°C": device_class = "temperature"
            elif unit == "%": device_class = "battery"

            config_topic = f"homeassistant/sensor/jk_bms_{self.mac}/{name}/config"

            payload = {
                "name": name.replace('_', ' '),
                "unique_id": f"jk_bms_{self.mac}_{name}",
                "state_topic": self.state_topic,
                "value_template": f"{{{{ value_json.{name} }}}}",
                "device": self.device_info,
            }
            if unit: payload["unit_of_measurement"] = unit
            if device_class: payload["device_class"] = device_class
            if state_class: payload["state_class"] = state_class
            if entity_category: payload["entity_category"] = entity_category
            if suggested_display_precision: payload["suggested_display_precision"] = suggested_display_precision

            # Retain=True is crucial so HA sees them even if it reboots after your script
            await self.mqtt_client.publish(config_topic, json.dumps(payload), retain=True)

    async def publish_state(self, data_dict):
        """Publishes the actual live data to the state topic."""
        await self.mqtt_client.publish(self.state_topic, json.dumps(data_dict))