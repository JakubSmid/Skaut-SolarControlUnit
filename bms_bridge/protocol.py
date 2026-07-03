class BmsFrame:
    CMD_HEADER = bytes([0xAA, 0x55, 0x90, 0xEB])
    RESP_HEADER = bytes([0x55, 0xAA, 0xEB, 0x90])
    RESP_LEN = 300
    RESP_TYPE: int = None
    LAYOUT = None

    def __init__(self, frame: bytes):
        self._frame = frame
        self._offset = 0
        self.data = self._parse_layout(self.LAYOUT)

    def __getitem__(self, key):
        return self.data[key]

    def __contains__(self, key):
        return key in self.data

    @classmethod
    def build_packet(cls, address, value: list = ()) -> bytes:
        n = len(value)
        assert n <= 13, f"value {value} too long"
        
        frame = bytearray(cls.CMD_HEADER)
        frame.append(address)
        frame.append(n)
        frame.extend(value)
        frame.extend([0] * (13 - n))
        frame.append(cls._calc_crc(frame))
        return bytes(frame)
    
    @classmethod
    def check_crc(cls, frame):
        return cls._calc_crc(frame[:-1]) == frame[-1]
    
    @staticmethod
    def get_resp_type(frame: bytes) -> int:
        return frame[4]

    @staticmethod
    def _calc_crc(data: bytes) -> int:
        return sum(data) & 0xFF
    
    def _read(self, length: int) -> bytes:
        data = self._frame[self._offset:self._offset + length]
        self._offset += length
        return data

    def _read_ascii(self, length: int) -> str:
        return self._read(length).rstrip(b"\x00").decode()

    def _read_uint_le(self, length: int) -> int:
        return int.from_bytes(self._read(length), "little")

    def _read_int_le(self, length: int) -> int:
        return int.from_bytes(self._read(length), "little", signed=True)

    def _parse_layout(self, layout):
        result = {}

        for t, length, name, unit in layout:
            if t == "discard":
                self._read(length)
                continue

            if t == "str":
                value = self._read(length).hex()

            elif t == "ascii":
                value = self._read_ascii(length)

            elif t.startswith("uint_le") or t.startswith("uptime"):
                value = self._read_uint_le(length)

            elif t.startswith("int_le"):
                value = self._read_int_le(length)

            else:
                raise ValueError(f"Unknown parser type {t}")

            # handle scaling like r/1000
            if ":" in t:
                expr = t.split(":")[1]
                if expr.startswith("r/"):
                    value = value / float(expr[2:])

            result[name] = value

        return result

class DeviceInfoResponse(BmsFrame):
    RESP_TYPE = 0x03
    LAYOUT = [
        ("str", 4, "Header", ""),
        ("str", 1, "Record_Type", ""),
        ("uint_le", 1, "Record_Counter", ""),
        ("ascii", 16, "Device_Model", ""),
        ("ascii", 8, "Hardware_Version", ""),
        ("ascii", 8, "Software_Version", ""),
        ("uptime", 4, "Up_Time", ""),
        ("uint_le", 4, "Power-on_Times", ""),
        ("ascii", 16, "Device_Name", ""),
        ("ascii", 16, "Device_Passcode", ""),
        ("ascii", 8, "Manufacturing_Date", ""),
        ("ascii", 11, "Serial_Number", ""),
        ("ascii", 5, "Passcode", ""),
        ("ascii", 16, "User_Data", ""),
        ("ascii", 16, "Setup_Passcode", "")
    ]

class CellDataResponse(BmsFrame):
    RESP_TYPE = 0x02
    LAYOUT = [
        ("str", 4, "Header", ""),
        ("str", 1, "Record_Type", ""),
        ("uint_le", 1, "Record_Counter", ""),

        ("uint_le:r/1000", 2, "Voltage_Cell01", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell02", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell03", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell04", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell05", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell06", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell07", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell08", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell09", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell10", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell11", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell12", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell13", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell14", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell15", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell16", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell17", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell18", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell19", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell20", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell21", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell22", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell23", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell24", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell25", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell26", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell27", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell28", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell29", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell30", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell31", "V"),
        ("uint_le:r/1000", 2, "Voltage_Cell32", "V"),

        ("discard", 4, "discard1", ""),

        ("uint_le:r/1000", 2, "Average_Cell_Voltage", "V"),
        ("uint_le:r/1000", 2, "Delta_Cell_Voltage", "V"),

        ("discard", 2, "discard2", ""),

        ("uint_le:r/1000", 2, "Resistance_Cell01", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell02", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell03", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell04", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell05", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell06", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell07", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell08", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell09", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell10", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell11", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell12", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell13", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell14", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell15", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell16", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell17", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell18", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell19", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell20", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell21", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell22", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell23", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell24", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell25", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell26", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell27", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell28", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell29", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell30", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell31", "Ohm"),
        ("uint_le:r/1000", 2, "Resistance_Cell32", "Ohm"),

        ("uint_le:r/10", 2, "MOS_Temp", "°C"),

        ("discard", 4, "discard3", ""),

        ("uint_le:r/1000", 4, "Battery_Voltage", "V"),
        ("uint_le:r/1000", 4, "Battery_Power", "W"),
        ("int_le:r/1000", 4, "Battery_Current", "A"),

        ("uint_le:r/10", 2, "Battery_T1", "°C"),
        ("uint_le:r/10", 2, "Battery_T2", "°C"),

        ("uint_le", 2, "Errors_Bitmask", ""),
        ("discard", 2, "System_Alarms", ""),

        ("uint_le:r/1000", 2, "Balance_Current", "A"),

        ("discard", 1, "discard5", ""),

        ("uint_le", 1, "Percent_Remain", "%"),

        ("uint_le:r/1000", 4, "Capacity_Remain", "Ah"),
        ("uint_le:r/1000", 4, "Nominal_Capacity", "Ah"),

        ("uint_le", 4, "Cycle_Count", ""),

        ("uint_le:r/1000", 4, "Cycle_Capacity", "Ah"),

        ("discard", 2, "Unknown12", ""),
        ("discard", 2, "Unknown13", ""),

        ("uptime", 4, "Time", "")
    ]

class SettingsResponse(BmsFrame):
    RESP_TYPE = 0x01
    LAYOUT = [
        ("str", 4, "Header", ""),
        ("str", 1, "Record_Type", ""),
        ("uint_le", 1, "Record_Counter", ""),

        # Battery & Cell Voltage Protections
        ("uint_le:r/1000", 4, "Smart_Sleep_Voltage", "V"),
        ("uint_le:r/1000", 4, "Cell_UVP", "V"),         # Under Voltage Protection
        ("uint_le:r/1000", 4, "Cell_UVPR", "V"),        # Under Voltage Protection Recovery
        ("uint_le:r/1000", 4, "Cell_OVP", "V"),         # Over Voltage Protection
        ("uint_le:r/1000", 4, "Cell_OVPR", "V"),        # Over Voltage Protection Recovery
        ("uint_le:r/1000", 4, "Balance_Trigger_Voltage", "V"),
        ("uint_le:r/1000", 4, "SOC_100_Voltage", "V"),
        ("uint_le:r/1000", 4, "SOC_0_Voltage", "V"),
        ("uint_le:r/1000", 4, "Cell_Request_Charge_Voltage", "V"),
        ("uint_le:r/1000", 4, "Cell_Request_Float_Voltage", "V"),
        ("uint_le:r/1000", 4, "Power_Off_Voltage", "V"),

        # Current & Short Circuit Protections
        ("uint_le:r/1000", 4, "Max_Charge_Current", "A"),
        ("uint_le", 4, "Charge_OCP_Delay", "s"),        # Over Current Protection Delay
        ("uint_le", 4, "Charge_OCP_Recovery_Time", "s"),
        ("uint_le:r/1000", 4, "Max_Discharge_Current", "A"),
        ("uint_le", 4, "Discharge_OCP_Delay", "s"),
        ("uint_le", 4, "Discharge_OCP_Recovery_Time", "s"),
        ("uint_le", 4, "SCPR_Time", "s"),               # Short Circuit Protection Recovery
        ("uint_le:r/1000", 4, "Max_Balance_Current", "A"),

        # Temperature Protections
        ("uint_le:r/10", 4, "Charge_OTP", "°C"),        # Over Temp Protection
        ("uint_le:r/10", 4, "Charge_OTP_Recovery", "°C"),
        ("uint_le:r/10", 4, "Discharge_OTP", "°C"),
        ("uint_le:r/10", 4, "Discharge_OTP_Recovery", "°C"),
        
        # Note: UTP (Under Temp) uses int_le because temps can drop below zero
        ("int_le:r/10", 4, "Charge_UTP", "°C"),         
        ("int_le:r/10", 4, "Charge_UTP_Recovery", "°C"),
        ("int_le:r/10", 4, "MOS_OTP", "°C"),            # Mosfet Over Temp
        ("int_le:r/10", 4, "MOS_OTP_Recovery", "°C"),

        # Hardware & Switches
        ("uint_le", 4, "Cell_Count", ""),
        ("uint_le", 4, "Charge_Switch", ""),            # 0 = Off, 1 = On
        ("uint_le", 4, "Discharge_Switch", ""),         # 0 = Off, 1 = On
        ("uint_le", 4, "Balancer_Switch", ""),          # 0 = Off, 1 = On
        ("uint_le:r/1000", 4, "Nominal_Battery_Capacity", "Ah"),
        ("uint_le", 4, "SCP_Delay", "us"),              # Short Circuit Protection Delay
        ("uint_le:r/1000", 4, "Start_Balance_Voltage", "V"),

        # Wire Resistances (32 possible cells)
        ("uint_le:r/1000", 4, "Wire_Resistance_01", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_02", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_03", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_04", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_05", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_06", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_07", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_08", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_09", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_10", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_11", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_12", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_13", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_14", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_15", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_16", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_17", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_18", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_19", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_20", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_21", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_22", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_23", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_24", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_25", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_26", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_27", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_28", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_29", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_30", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_31", "Ohm"),
        ("uint_le:r/1000", 4, "Wire_Resistance_32", "Ohm"),

        # Extra Device Configurations
        ("uint_le", 4, "Device_Address", ""),
        ("uint_le", 4, "Precharge_Time", "s"),
        ("discard", 4, "Unknown278", ""),
        ("uint_le", 2, "New_Controls_Bitmask", ""),
        ("int_le", 1, "Heating_Start_Temperature", "°C"), # Uses 1-byte signed int
        ("int_le", 1, "Heating_Stop_Temperature", "°C"),  # Uses 1-byte signed int
        ("uint_le", 1, "Smart_Sleep", "h"),
        ("uint_le", 1, "Data_Field_Enable_Control", ""),
    ]