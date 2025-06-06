from pathlib import Path
import sys
import threading
import time
import traceback

import RPi.GPIO as GPIO

import utils


class GlassDriver():
    STATE_OFF             = 0
    STATE_ON              = 1
    STATE_UNKNOWN         = 2

    CMD_OFF               = "off"
    CMD_ON                = "on"

    FREQ                  = 111
    PERIOD                = 1 / FREQ
    HALF_PERIOD           = PERIOD / 2

    ENABLE_PIN            = 16
    A_PIN                 = 20
    B_PIN                 = 21

    def __init__(self, cfg_path, debug=False):
        self._setup()

        self.cfg_path = Path(cfg_path)
        self.cfg_mtime = None
        self.cfg = None
        self.configure()

        self._debug = debug
        if self._debug:
            print("Debug mode")

        self._dc_prev = None
        self._dc = self.DC_OFF

        self._state = self.STATE_OFF

        self._cmd = None

    def _setup(self):
        GPIO.setmode(GPIO.BCM)

        GPIO.setup(self.ENABLE_PIN, GPIO.OUT)
        GPIO.output(self.ENABLE_PIN, GPIO.HIGH)

        GPIO.setup(self.A_PIN, GPIO.OUT)
        GPIO.output(self.A_PIN, GPIO.LOW)

        GPIO.setup(self.B_PIN, GPIO.OUT)
        GPIO.output(self.B_PIN, GPIO.LOW)

    def cleanup(self):
        GPIO.cleanup()

    def configure(self):
        self.cfg_mtime = self.cfg_path.stat().st_mtime

        cfg = utils.load_json(self.cfg_path)
        self.cfg = cfg['controller']

        self.DC_OFF    = self.cfg['dc_off']
        self.DC_OFF_L1 = self.cfg['dc_off_l1']
        self.DC_OFF_L2 = self.cfg['dc_off_l2']
        self.DC_OFF_D1 = self.cfg['dc_off_d1']
        self.DC_OFF_D2 = self.cfg['dc_off_d2']
        self.DC_OFF_D3 = self.cfg['dc_off_d3']

        self.DC_ON     = self.cfg['dc_on']
        self.DC_ON_L1  = self.cfg['dc_on_l1']
        self.DC_ON_L2  = self.cfg['dc_on_l2']
        self.DC_ON_D1  = self.cfg['dc_on_d1']
        self.DC_ON_D2  = self.cfg['dc_on_d2']
        self.DC_ON_D3  = self.cfg['dc_on_d3']

        self.VERBOSE   = self.cfg['verbose']

    def start(self):
        self._read_cmd_thread = threading.Thread(target=self._read_cmd, daemon=True)
        self._read_cmd_thread.start()

        while True:
            if self._debug:
                try:
                    cfg_mtime = self.cfg_path.stat().st_mtime
                    if cfg_mtime != self.cfg_mtime:
                        self.configure()
                        print("Config reloaded")
                except:
                    pass

            if self._cmd == self.CMD_ON:
                self._turn_on()
                self._cmd = None
            elif self._cmd == self.CMD_OFF:
                self._turn_off()
                self._cmd = None
            else:
                self._cycle()

    def _read_cmd(self):
        while True:
            if self._cmd is not None:
                time.sleep(0.5)
                continue

            line = sys.stdin.readline()
            line = line.strip().lower()

            if line == self.CMD_ON:
                self._cmd = self.CMD_ON
            elif line == self.CMD_OFF:
                self._cmd = self.CMD_OFF

    def _cycle(self):
        pulse = self.HALF_PERIOD * self._dc / 100
        if pulse < 0:
            pulse = 0.

        pause = self.HALF_PERIOD  - pulse
        if pause < 0:
            pause = 0.

        match self.VERBOSE:
            case 1:
                if self._dc != self._dc_prev:
                    print(f"{self._dc:6.2f}")
            case 2:
                print(f"{self._dc:6.2f}")

        GPIO.output(self.A_PIN, GPIO.LOW)
        GPIO.output(self.B_PIN, GPIO.LOW)

        # 1st half
        if pulse > 0:
            GPIO.output(self.A_PIN, GPIO.HIGH)
        time.sleep(pulse)

        GPIO.output(self.A_PIN, GPIO.LOW)
        time.sleep(pause)
        #####

        # 2nd half
        if pulse > 0:
            GPIO.output(self.B_PIN, GPIO.HIGH)
        time.sleep(pulse)

        GPIO.output(self.B_PIN, GPIO.LOW)
        time.sleep(pause)
        #####

        self._dc_prev = self._dc

    def _dc_up(self):
        if self._dc < self.DC_ON_L1:
            d = self.DC_ON_D1
        elif self._dc < self.DC_ON_L2:
            d = self.DC_ON_D2
        else:
            d = self.DC_ON_D3

        self._dc += d
        if self._dc > self.DC_ON:
            self._dc = self.DC_ON

    def _turn_on(self):
        while (self._dc < self.DC_ON):
            self._dc_up()
            self._cycle()

        self._state = self.STATE_ON
        print("Glass if ON")

    def _dc_down(self):
        if self._dc > self.DC_OFF_L1:
            d = self.DC_OFF_D1
        elif self._dc > self.DC_OFF_L2:
            d = self.DC_OFF_D2
        else:
            d = self.DC_OFF_D3

        self._dc -= d
        if self._dc < self.DC_OFF:
            self._dc = self.DC_OFF

    def _turn_off(self):
        while (self._dc > self.DC_OFF):
            self._dc_down()
            self._cycle()

        self._state = self.STATE_OFF
        print("Glass if OFF")


if __name__ == "__main__":
    try:
        cfg_path = sys.argv[1]
    except:
        print("No path for configuration provided")
        sys.exit(1)

    debug = "0"
    try:
        debug = sys.argv[2]
    except:
        pass

    if debug == "0":
        debug = False
    elif debug == "1":
        debug = True
    else:
        print("Invalid debug argument provided")
        sys.exit(1)

    glass_ctl = GlassController(cfg_path, debug)

    try:
        glass_ctl.start()
    except Exception as e:
        traceback.print_exc()
    finally:
        glass_ctl.cleanup()
