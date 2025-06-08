from datetime import datetime
import math
from pathlib import Path
import sys
import threading
import time
import traceback

import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)

import utils


class GlassDriver():
    CMD_OFF               = "off"
    CMD_ON                = "on"

    FREQ                  = 111
    PERIOD                = 1 / FREQ
    HALF_PERIOD           = PERIOD / 2

    ENABLE_PIN            = 16
    A_PIN                 = 5
    B_PIN                 = 6

    def __init__(self, cfg_path):
        self._setup()

        self.cfg_path = Path(cfg_path)
        self.cfg_mtime = self.cfg_path.stat().st_mtime

        self.cfg = None
        self.configure()

        self._dc_prev = None
        self._dc = self.DC_OFF_L3

        self._cmd = None

        self.on = False

    def _setup(self):
        GPIO.setup(self.ENABLE_PIN, GPIO.OUT)
        GPIO.output(self.ENABLE_PIN, GPIO.HIGH)

        GPIO.setup(self.A_PIN, GPIO.OUT)
        GPIO.output(self.A_PIN, GPIO.LOW)

        GPIO.setup(self.B_PIN, GPIO.OUT)
        GPIO.output(self.B_PIN, GPIO.LOW)

    def cleanup(self):
        GPIO.cleanup()

    def configure(self):
        cfg = utils.load_json(self.cfg_path)
        self.cfg = cfg['glass_driver']

        self.DC_OFF_L1 = self.cfg['dc_off_l1']
        self.DC_OFF_L2 = self.cfg['dc_off_l2']
        self.DC_OFF_L3 = self.cfg['dc_off_l3']
        self.DC_OFF_D1 = self.cfg['dc_off_d1']
        self.DC_OFF_D2 = self.cfg['dc_off_d2']
        self.DC_OFF_D3 = self.cfg['dc_off_d3']

        self.DC_ON_L1  = self.cfg['dc_on_l1']
        self.DC_ON_L2  = self.cfg['dc_on_l2']
        self.DC_ON_L3  = self.cfg['dc_on_l3']
        self.DC_ON_D1  = self.cfg['dc_on_d1']
        self.DC_ON_D2  = self.cfg['dc_on_d2']
        self.DC_ON_D3  = self.cfg['dc_on_d3']

        self.VERBOSE   = self.cfg['verbose']

    def check_config(self):
        try:
            cfg_mtime = self.cfg_path.stat().st_mtime
        except:
            return

        if cfg_mtime != self.cfg_mtime:
            self.configure()
            self.cfg_mtime = cfg_mtime
            print("Config reloaded")

    def start(self):
        self._read_cmd_thread = threading.Thread(target=self._read_cmd, daemon=True)
        self._read_cmd_thread.start()

        while True:
            self.check_config()

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

        f = pulse > 0

        pause = self.HALF_PERIOD  - pulse
        if pause < 0:
            pause = 0.

        match self.VERBOSE:
            case 1:
                if self._dc != self._dc_prev:
                    print(f"{self._dc:6.2f}")
            case 2:
                print(f"{self._dc:6.2f}")

        #####

        # 1st half
        if f:
            GPIO.output(self.A_PIN, GPIO.HIGH)
        time.sleep(pulse)

        if f:
            GPIO.output(self.A_PIN, GPIO.LOW)
        time.sleep(pause)

        #####

        # 2nd half
        if f:
            GPIO.output(self.B_PIN, GPIO.HIGH)
        time.sleep(pulse)

        if f:
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
        if self._dc > self.DC_ON_L3:
            self._dc = self.DC_ON_L3

    def _turn_on(self):
        start_dt = datetime.now()
        while (self._dc < self.DC_ON_L3):
            self._dc_up()
            self._cycle()
        td = datetime.now() - start_dt

        self.on = True
        print(f"Glass if ON ({td})")

    def _dc_down(self):
        if self._dc > self.DC_OFF_L1:
            d = self.DC_OFF_D1
        elif self._dc > self.DC_OFF_L2:
            d = self.DC_OFF_D2
        else:
            d = self.DC_OFF_D3

        self._dc -= d
        if self._dc < self.DC_OFF_L3:
            self._dc = self.DC_OFF_L3

    def _turn_off(self):
        start_dt = datetime.now()
        while (self._dc > self.DC_OFF_L3):
            self._dc_down()
            self._cycle()
        td = datetime.now() - start_dt

        self.on = False
        print(f"Glass if OFF ({td})")


if __name__ == "__main__":
    try:
        cfg_path = sys.argv[1]
    except:
        print("No path for configuration provided")
        sys.exit(1)

    glass_driver = GlassDriver(cfg_path)

    try:
        glass_driver.start()
    except:
        traceback.print_exc()
    finally:
        glass_driver.cleanup()
