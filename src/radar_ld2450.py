import math
from datetime import datetime, timedelta
import serial
import time


class LD2450():
    CMD_HEADER = bytes([0xFD, 0xFC, 0xFB, 0xFA])
    CMD_EOF = bytes([0x04, 0x03, 0x02, 0x01])

    DATA_HEADER = bytes([0xAA, 0xFF, 0x03, 0x00])
    DATA_EOF = bytes([0x55, 0xCC])

    ANGLE_ABS_MAX = math.pi / 3

    @staticmethod
    def bs2str(bs):
        return " ".join([f"{i:02X}" for i in bs])

    @staticmethod
    def _convert_data_int16(bs, signed):
        v = int.from_bytes(bs, byteorder='little')

        if signed:
            if v < 2**15:
                v = -v
            else:
                v = v - 2**15

        return v

    @staticmethod
    def _is_res_ok(res):
        flag = int.from_bytes(res[4:6], byteorder='little')
        return not flag

    @staticmethod
    def distance(t):
        return math.sqrt(t[0]**2 + t[1]**2)
    
    @staticmethod
    def angle(t):
        rad = math.atan(t[0]/t[1])
        deg = int(rad * 180 / math.pi)
        return deg

    def __init__(self, uartdev, verbose=False):
        self.uartdev = uartdev
        self.verbose = verbose
        self.n_frame_failures = 0

        if self.uartdev == "/dev/ttyUSBx":
            dev_path = Path("/dev")
            for p in dev_path.glob('ttyUSB*'):
                self.uartdev = str(p)
                print(f"Trying '{p}'...")
                try:
                    self._ser = self._get_serial()
                    break
                except:
                    pass
            else:
                raise Exception("Failed to init radar.")
        else:
            self._ser = self._get_serial()

    def _get_serial(self):
        try:
            return serial.Serial(self.uartdev, 256000, timeout=1)
        except:
            raise Exception(f"Failed to open UART device '{self.uartdev}'.") from None

    def __del__(self):
        try:
            self._ser.close()
        except:
            pass

    @property
    def in_waiting(self):
        return self._ser.in_waiting

    def _send_cmd(self, cmd_word, cmd_value, reverse_value=True): 
        cmd_word_str = self.bs2str(cmd_word)

        cmd_data_len = len(cmd_word + cmd_value)
        cmd_data_len = cmd_data_len.to_bytes(2, byteorder='little')

        cmd_word = bytes(cmd_word)[::-1]

        cmd_value = bytes(cmd_value)
        if reverse_value:
            cmd_value = cmd_value[::-1]

        cmd = self.CMD_HEADER + cmd_data_len + cmd_word + cmd_value + self.CMD_EOF
        self._ser.write(cmd)

        res = self._ser.read_until(self.CMD_EOF)

        if self.verbose:
            print(f"CMD: {self.bs2str(cmd)}\nRESPONSE: {self.bs2str(res)}\n\n")
        
        if self.CMD_HEADER in res:
            res = res.split(self.CMD_HEADER)[-1][:-4]
        else:
            raise Exception(f"No header in response to cmd '{cmd_word_str}'.")

        if not self._is_res_ok(res):
            raise Exception(f"No acknowledge in response to cmd '{cmd_word_str}'.")

        return res

    def _start_configuration(self):
        cmd_word = [0x00, 0xFF]
        cmd_value = [0x00, 0x01]
        self._send_cmd(cmd_word, cmd_value)

    def _end_configuration(self):
        cmd_word = [0x00, 0xFE]
        cmd_value = []
        self._send_cmd(cmd_word, cmd_value)

    def _execute_cmd(self, cmd_word, cmd_value, reverse_value=True):
        cmd_word_str = self.bs2str(cmd_word)

        n = 4
        for l in range(n):
            for i in range(n):
                try:
                    self._start_configuration()
                    break
                except Exception as e:
                    print(f"Failed to start configuration\n{e}")
            else:
                raise Exception(f"Failed to start configuration while executing cmd '{cmd_word_str}'.")

            for i in range(n):
                try:
                    res = self._send_cmd(cmd_word, cmd_value, reverse_value)
                    break
                except Exception as e:
                    print(f"Failed to execute cmd '{cmd_word_str}'\n{e}")
            else:
                print(f"Failed to execute cmd '{cmd_word_str}'.")
                continue

            for i in range(n):
                try:
                    self._end_configuration()
                    break
                except Exception as e:
                    print(f"Failed to end configuration\n{e}")
            else:
                print(f"Failed to end configuration while executing cmd '{cmd_word_str}'.")
                continue

            break
        else:
            raise Exception(f"Failed to execute cmd '{cmd_word_str}'.")

        return res

    def get_firmware_version(self, raw=False):
        cmd_word = [0x00, 0xA0]
        cmd_value = []
        res = self._execute_cmd(cmd_word, cmd_value)
        
        if raw:
            return res

        #ft = int.from_bytes(res[6:8], byteorder='little')
        vx = int.from_bytes(res[9:10], byteorder='little')
        vy = int.from_bytes(res[8:9], byteorder='little')
        vz = "".join([f"{i:02X}" for i in res[13:9:-1]])
        return f"V{vx}.{vy:02}.{vz}"

    def restart(self):
        cmd_word = [0x00, 0xA3]
        cmd_value = []
        self._execute_cmd(cmd_word, cmd_value)
        time.sleep(3)

        self._ser = self._get_serial()

    def restore_factory_settings(self, restart=False):
        # Baudrate: 256000.
        # Bluetooth: on.
        # Track mode: multi.
        # Area filtering: off.

        cmd_word = [0x00, 0xA2]
        cmd_value = []
        self._execute_cmd(cmd_word, cmd_value)

        if restart:
            self.restart()

    def set_baudrate(self, baudrate, restart=False):
        baudrates = [9600, 19200, 38400, 57600, 115200, 230400, 256000, 460800]
        if baudrate not in baudrates:
            baudrates_str = ", ".join(map(str, baudrates))
            raise ValueError(f"Baudrate must be one of the following: {baudrates_str}.")   

        baudrate_index = baudrates.index(baudrate) + 1

        cmd_word = [0x00, 0xA1]
        cmd_value = [0x00, baudrate_index]
        self._execute_cmd(cmd_word, cmd_value)

        if restart:
            self.restart()

    def get_mac_address(self, raw=False):
        cmd_word = [0x00, 0xA5]
        cmd_value = [0x00, 0x01]
        res = self._execute_cmd(cmd_word, cmd_value)

        if raw:
            return res

        mac_address = self.bs2str(res[6:12])
        return mac_address

    def get_bluetooth_state(self):
        # This method is not native for radar!

        # Bluetooth states:
        # True - On
        # False - Off

        mac_address = self.get_mac_address()
        if len(mac_address) != 17:
            return False
        else:
            return True

    def set_bluetooth_on(self, restart=False):
        cmd_word = [0x00, 0xA4]
        cmd_value = [0x00, 0x01]
        self._execute_cmd(cmd_word, cmd_value)

        if restart:
            self.restart()

    def set_bluetooth_off(self, restart=False):
        cmd_word = [0x00, 0xA4]
        cmd_value = [0x00, 0x00]
        self._execute_cmd(cmd_word, cmd_value)

        if restart:
            self.restart()

    def get_tracking_mode(self, raw=False):
        # Tracking modes:
        # 1 - single target
        # 2 - multi target

        cmd_word = [0x00, 0x91]
        cmd_value = []
        res = self._execute_cmd(cmd_word, cmd_value)

        if raw:
            return res

        track_mode = int.from_bytes(res[6:8], byteorder='little')
        return track_mode

    def set_single_tracking(self):
        cmd_word = [0x00, 0x80]
        cmd_value = []
        self._execute_cmd(cmd_word, cmd_value)
    
    def set_multi_tracking(self):
        cmd_word = [0x00, 0x90]
        cmd_value = []
        self._execute_cmd(cmd_word, cmd_value)

    def get_zone_filtering(self, raw=False):
        cmd_word = [0x00, 0xC1]
        cmd_value = []
        res = self._execute_cmd(cmd_word, cmd_value)

        if raw:
            return res

        # Zone filtering mode: 0 - off; 1 - in region; 2 - out of region.
        mode = int.from_bytes(res[6:8], byteorder='little')

        data = [mode]
        for i in range(3):
            from_i = (i+1) * 8
            to_i = from_i + 8
            c = res[from_i:to_i]

            x1 = int.from_bytes(c[0:2], byteorder='little', signed=True)
            y1 = int.from_bytes(c[2:4], byteorder='little', signed=True)
            x2 = int.from_bytes(c[4:6], byteorder='little', signed=True)
            y2 = int.from_bytes(c[6:8], byteorder='little', signed=True)
            data.extend([x1,y1,x2,y2])

        return data

    def set_zone_filtering(self, mode, reg1=None, reg2=None, reg3=None):
        cmd_word = [0x00, 0xC2]

        cmd_value = [mode, 0x00]
        for reg in [reg1,reg2,reg3]:
            if reg is None:
                regb = [0x00] * 8
            else:
                regb = []
                for i in reg:
                    ib = list(i.to_bytes(2, byteorder='little', signed=True))
                    regb.extend(ib)

            cmd_value.extend(regb)

        self._execute_cmd(cmd_word, cmd_value, reverse_value=False)

    def show_info(self):
        firmware_version = self.get_firmware_version()

        bl_state = self.get_bluetooth_state()
        if bl_state:
            mac_address = self.get_mac_address()
            bl_state = "ON"
        else:
            mac_address = "---"
            bl_state = "OFF"

        tracking_mode = self.get_tracking_mode()
        if tracking_mode == 1:
            mt_state = "OFF"
        else:
            mt_state = "ON"

        zone_filtering = self.get_zone_filtering()

        print(f"UART device: {self.uartdev}")
        print(f"Firmware version: {firmware_version}")
        print(f"Bluetooth: {bl_state} (MAC address: {mac_address})")
        print(f"Multi tracking: {mt_state}")
        print(f"Zone filtering: {zone_filtering}")

    def test(self, n=200):
        l1 = []
        l2 = []
        l3 = []
        
        for i in range(n):
            print(i)
        
            firmware_version = self.get_firmware_version()
            mac_address = self.get_mac_address()
            tracking_mode_index = self.get_tracking_mode()
        
            l1.append(firmware_version)
            l2.append(mac_address)
            l3.append(tracking_mode_index)
        
        print()
        print(f"Firmware version: {sorted(set(l1))}")
        print(f"MAC address: {sorted(set(l2))}")
        print(f"Tracking mode: {sorted(set(l3))}")

    def clean(self, ret=False):
        if ret:
            return self._ser.read(size=self.in_waiting)
        else:
            self._ser.reset_input_buffer()

    def get_frame(self):
        n_all = self.in_waiting
        if n_all >= 60:
            n_skipped = n_all - 30
            _ = self._ser.read(n_skipped)
            res = self._ser.read_until(self.DATA_EOF)
            n_skipped += len(res)
            print(f"Skipping {n_skipped} bytes")

        res = self._ser.read_until(self.DATA_EOF)

        if res[-30:-26] != self.DATA_HEADER:
            self.n_frame_failures += 1
            print("Invalid data header")
            return

        self.n_frame_failures = 0
        return res
        
    def parse_frame(self, frame, full=False):
        payload = frame[-26:-4]

        data = []
        for i in range(3):
            from_i = i * 8
            to_i = from_i + 8
            c = payload[from_i:to_i]

            x = self._convert_data_int16(c[0:2], signed=True)
            y = self._convert_data_int16(c[2:4], signed=True)
            if (x != 0) and (y != 0):
                if full:
                    s = self._convert_data_int16(c[4:6], signed=True)
                    d = self._convert_data_int16(c[4:6], signed=False)
                    idata = (x,y,s,d)
                else:
                    idata = (x,y)

                data.append(idata)

        return data

    def get_data(self, full=False):
        frame = self.get_frame()
        if frame is None:
            return

        return self.parse_frame(frame, full=full)

    def show_data(self, n=None, clean=True):
        if clean:
            self.clean(ret=True)

        td = timedelta(seconds=1)

        dt_end = datetime.now() + td
        i = 0
        c = 0
        while True:
            if (n is not None) and (c > n):
                break

            data = self.get_data()
            if data is None:
                continue

            dt = datetime.now()
            if dt > dt_end:
                dt_end = dt + td
                i = 0
                print()

            i += 1
            c += 1

            text = f"Sample: {i:5} | IN: {self.in_waiting:5}"
            text += " | ".join([f"{x:5} {y:5}" for (x,y) in data])
            print(text)

if __name__ == "__main__":
    import sys

    try:
        uartdev = sys.argv[1]
    except:
        print("No argument for UART device provided")
        sys.exit(1)

    try:
        bl = sys.argv[2]
    except:
        print("No argument for Bluetooth provided")
        sys.exit(1)

    try:
        bl = int(bl)
        if bl not in [0, 1]:
            raise Exception
    except:
        print("Bluetooth argument must be 0 (off) or 1 (on)")
        sys.exit(1)

    try:
        mt = sys.argv[3]
    except:
        print("No argument for multi tracking provided")
        sys.exit(1)

    try:
        mt = int(mt)
        if mt not in [0, 1]:
            raise Exception
    except:
        print("Multi tracking argument must be 0 (off, or single) or 1 (on)")
        sys.exit(1)

    try:
        cmd = sys.argv[4]
    except:
        cmd = "info"

    if cmd not in ["info", "data", "test"]:
        print("\nCmd argument must be:\n"
                        "- empty or 'info': showing radar info\n"
                        "- 'data': collecting and printing data\n"
                        "- 'test': conducting test\n")
        sys.exit(1)

    ##########

    r = LD2450(uartdev)

    if bl == 1:
        r.set_bluetooth_on(restart=True)
    else:
        r.set_bluetooth_off(restart=True)

    if mt == 1:
        r.set_multi_tracking()
    else:
        r.set_single_tracking()

    r.set_zone_filtering(mode=0)
        
    ##########

    if cmd == 'info':
        r.show_info()
    elif cmd == 'test':
        r.test()
    elif cmd == 'data':
        try:
            r.show_data()
        except KeyboardInterrupt:
            print("\nExiting...\n")
