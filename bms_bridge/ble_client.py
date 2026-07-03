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
      await asyncio.wait_for(self._init_event.wait(), timeout=10)

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
            # discard header to try next frame
            self._buffer = self._buffer[len(BmsFrame.RESP_HEADER):]
            continue

         resp_type = BmsFrame.get_resp_type(frame)
         self.logger.debug(f"Valid frame received, type 0x{resp_type:02X}")

         if resp_type == DeviceInfoResponse.RESP_TYPE:
            self.device_info = DeviceInfoResponse(frame)

         if resp_type == SettingsResponse.RESP_TYPE:
            self.device_settings = SettingsResponse(frame)

         if resp_type == CellDataResponse.RESP_TYPE and self._init_event.is_set():
            if self.cell_data_callback:
               self.cell_data_callback(CellDataResponse(frame))

         if self.device_info is not None and self.device_settings is not None:
            self._init_event.set()

         self._buffer = self._buffer[expected_len:]

   async def _send(self, address, value: list = ()):
      packet = BmsFrame.build_packet(address, value)
      self.logger.info(f"Sending command 0x{address:02X}")
      await self.client.write_gatt_char(CHAR_UUID, packet)
