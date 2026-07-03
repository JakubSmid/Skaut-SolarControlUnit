import asyncio
import logging
from bleak.exc import BleakError
import aiomqtt
import os

from bms_bridge.ble_client import BleClient
from bms_bridge.protocol import CellDataResponse
from bms_bridge.bms_mqtt import BmsMqttClient

ADDRESS = os.environ.get("BMS_MAC", "C8:47:80:22:29:9F")
MQTT_BROKER = os.environ.get("MQTT_HOST", "localhost")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

ble_logger = logging.getLogger("BLE_Task")
mqtt_logger = logging.getLogger("MQTT_Task")

class DataStore:
   """A simple container to hold the absolute latest BMS data and notify when it updates."""
   def __init__(self):
      self.value = None
      self.new_data_event = asyncio.Event()

   def update(self, data):
      self.value = data
      self.new_data_event.set()

async def ble_task(bms_client: BleClient, latest_data: DataStore):
   """Handles the BLE connection and constantly updates the latest_data object."""
   def on_new_cell_data(cd: CellDataResponse):
      # We just overwrite the old data with the freshest data and set the flag
      latest_data.update(cd.data) 

   while True:
      try:
         await bms_client.connect(on_new_cell_data)
         await bms_client._disconnect_event.wait()

      except BleakError as e:
         ble_logger.error(f"Bluetooth Error: {e}")
      except asyncio.TimeoutError as e:
         ble_logger.error(f"BLE Connection attempt timed out: {e}")
      except Exception as e:
         ble_logger.exception(f"Unexpected BLE error: {e}")
      finally:
         await bms_client.disconnect()
         ble_logger.info("Waiting 10 seconds before attempting to reconnect BLE...")
         await asyncio.sleep(10)

async def mqtt_task(bms_client: BleClient, latest_data: DataStore):
   """Waits for the new data flag, then publishes the latest state to MQTT."""
   while True:
      if not bms_client._init_event.is_set():
         await asyncio.sleep(1)
         continue

      try:
         async with aiomqtt.Client(hostname=MQTT_BROKER) as mqtt_client:
               mqtt_logger.info("Connected to MQTT Broker")
               mqtt_client_ha = BmsMqttClient(mqtt_client, bms_client)
               await mqtt_client_ha.publish_discovery()

               latest_data.new_data_event.clear()
               while True:
                  # Wait infinitely until the BLE task says "I have new data!"
                  await latest_data.new_data_event.wait()
                  
                  # Immediately clear the flag so we can catch the next update
                  latest_data.new_data_event.clear()
                  
                  # Grab the freshest data
                  data_to_publish = latest_data.value
                  await mqtt_client_ha.publish_state(data_to_publish)

      except aiomqtt.MqttError as e:
         mqtt_logger.error(f"MQTT Connection Error: {e}. Reconnecting to Broker in 10 seconds...")
         await asyncio.sleep(10)
      except Exception as e:
         mqtt_logger.exception(f"Unexpected MQTT error: {e}")
         await asyncio.sleep(10)

async def main():
   bms_client = BleClient(ADDRESS)
   latest_data = DataStore()

   # Run both loops simultaneously
   await asyncio.gather(
      ble_task(bms_client, latest_data),
      mqtt_task(bms_client, latest_data)
   )

if __name__ == "__main__":
   try:
      asyncio.run(main())
   except KeyboardInterrupt:
      logging.info("Daemon gracefully stopped by user.")