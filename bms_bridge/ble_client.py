from bleak import BleakClient, BleakScanner, BleakError
import asyncio
import logging

from protocol import BmsFrame, CellDataResponse, DeviceInfoResponse, SettingsResponse

CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

class BleClient():
   def __init__(self, address: str):
      self.address = address
      self.client = BleakClient(address, disconnected_callback=self._handle_disconnect)

      self.device_info = None
      self.device_settings = None
      self.cell_data_callback = None

      self._buffer = bytearray()
      
      self._init_event = asyncio.Event()
      self._disconnect_event = asyncio.Event()

      self.logger = logging.getLogger(__name__)

   @property
   def n_cells(self):
      return self.device_settings["Cell_Count"]

   def _handle_disconnect(self, client):
      self.logger.warning(f"Bluetooth connection lost to {self.address}!")
      self._disconnect_event.set()

   async def connect(self, cell_data_callback=None):
      self.logger.info(f"Connecting to {self.address}")

      self.cell_data_callback = cell_data_callback

      # reset state
      self._init_event.clear()
      self._disconnect_event.clear()

      # wait for discovery
      device = await BleakScanner.find_device_by_address(self.address)
      if not device:
         raise BleakError("Device not found")
      
      # bleak client setup
      await asyncio.sleep(3)
      await self.client.connect()
      await self.client.start_notify(
         CHAR_UUID,
         self._notification_handler,
      )

      # send init sequence
      await self._send(0x97)
      await asyncio.sleep(0.2)
      await self._send(0x96)
      try:
         await asyncio.wait_for(self._init_event.wait(), timeout=10)
      except asyncio.TimeoutError:
         # Clean up on timeout to avoid inconsistent state
         await self.client.disconnect()
         raise BleakError("Initialization timeout - device did not respond")

      self.logger.info("Connected and notifications enabled")

   async def disconnect(self):
      if self.client.is_connected:
         self.logger.info("Disconnecting")
         await self.client.stop_notify(CHAR_UUID)
         await self.client.disconnect()
         self.logger.info("Disconnected")
   
   def _notification_handler(self, sender, data: bytearray):
      self._buffer.extend(data)
      
      while True:
         if BmsFrame.RESP_HEADER not in self._buffer:
            self.logger.debug(f"No header in buffer, clearing {len(self._buffer)} bytes")
            self._buffer.clear()
            return
         
         idx = self._buffer.index(BmsFrame.RESP_HEADER)   

         if idx > 0:
            self.logger.warning(f"Discarding {idx} bytes before header")
            self._buffer = self._buffer[idx:]

         expected_len = BmsFrame.RESP_LEN
         if len(self._buffer) < expected_len:
            self.logger.debug(f"Waiting for {expected_len - len(self._buffer)} more bytes")
            return  # wait for more chunks

         frame = self._buffer[:expected_len]

         if not BmsFrame.check_crc(frame):
            self.logger.warning("CRC failed for received frame. Discarding.")
            # discard just the header to try finding next valid frame
            self._buffer = self._buffer[expected_len:]
            continue  # Continue the while loop to check for more frames

         resp_type = BmsFrame.get_resp_type(frame)
         self.logger.debug(f"Valid frame received, type 0x{resp_type:02X}")

         if resp_type == DeviceInfoResponse.RESP_TYPE:
            self.device_info = DeviceInfoResponse(frame)

         if resp_type == SettingsResponse.RESP_TYPE:
            self.device_settings = SettingsResponse(frame)

         # Call callback for cell data once initialized OR during initialization
         # This ensures we don't lose data if it arrives slightly early
         if resp_type == CellDataResponse.RESP_TYPE:
            if self.cell_data_callback is not None:
               try:
                  self.cell_data_callback(CellDataResponse(frame))
               except Exception as e:
                  self.logger.error(f"Error in cell data callback: {e}")

         # Set init event only after both device_info and device_settings are received
         if self.device_info is not None and self.device_settings is not None:
            self._init_event.set()

         # Move past this frame to look for more
         self._buffer = self._buffer[expected_len:]
         
         # Break if no more data to process
         if len(self._buffer) < BmsFrame.RESP_LEN:
            return

   async def _send(self, address, value: list = ()):
      packet = BmsFrame.build_packet(address, value)
      self.logger.info(f"Sending command 0x{address:02X}")
      await self.client.write_gatt_char(CHAR_UUID, packet)
