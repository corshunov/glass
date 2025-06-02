from pathlib import Path
import sys
import threading
import time

import RPi.GPIO as GPIO

import utils


class GlassController():
    STATE_OFF             = 0
    STATE_ON              = 1
    STATE_UNKNOWN         = 2

    CMD_OFF               = "off"
    CMD_ON                = "on"

    FREQ                  = 111
    PERIOD                = 1. / FREQ
    HALF_PERIOD           = PERIOD / 2.

    ENABLE_PIN            = 24
    A_PIN                 = 25
    B_PIN                 = 27

    def __init__(self, cfg_path):
        GPIO.setmode(GPIO.BCM)
        GPIO.cleanup()

        self.cfg_path = Path(cfg_path)

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

        self._dc = self.DC_OFF
        self._state = self.STATE_OFF

        self._cmd = None

    def __del__(self):
        GPIO.cleanup()

    def start(self):
        GPIO.setup(self.ENABLE_PIN, GPIO.OUT)
        GPIO.output(self.ENABLE_PIN, GPIO.HIGH)

        GPIO.setup(self.A_PIN, GPIO.OUT)
        GPIO.output(self.A_PIN, GPIO.LOW)

        GPIO.setup(self.B_PIN, GPIO.OUT)
        GPIO.output(self.B_PIN, GPIO.LOW)

        self._read_cmd_thread = threading.Thread(target=self._read_cmd, daemon=True)
        self._read_cmd_thread.start()

        while True:
            if (self._cmd == self.CMD_ON) and \
               (self.state != self.STATE_ON):
                self.turn_on()
                self._cmd = None
            
            elif (self._cmd == self.CMD_OFF) and \
                 (self.state != self.STATE_OFF):
                self.turn_off()
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
        pulse = self.HALF_PERIOD * self._dc
        pause = self.HALF_PERIOD  - pulse

        GPIO.output(self.A_PIN, GPIO.LOW)
        GPIO.output(self.B_PIN, GPIO.LOW)

        if pulse == 0:
            return

        # Half wave 1
        GPIO.output(self.A_PIN, GPIO.HIGH)
        time.sleep(pulse)

        GPIO.output(self.A_PIN, GPIO.LOW)
        time.sleep(pause)

        # Half wave 2
        GPIO.output(self.B_PIN, GPIO.HIGH)
        time.sleep(pulse)

        GPIO.output(self.B_PIN, GPIO.LOW)
        time.sleep(pause)

    def _dc_up(self):
        if self._dc <= self.DC_ON_L1:
            d = self.DC_ON_D1
        elif self._dc <= self.DC_ON_L2:
            d = self.DC_ON_D2
        else:
            d = self.DC_ON_D3

        self._dc += d

    def _turn_on(self):
        while (self._dc < self.DC_ON):
            self._dc_up()
            self._cycle()

        self._state = self.STATE_ON
        print("Glass if ON")

    def _dc_down(self):
        if self._dc <= self.DC_OFF_L1:
            d = self.DC_OFF_D1
        elif self._dc <= self.DC_OFF_L2:
            d = self.DC_OFF_D2
        else:
            d = self.DC_OFF_D3

        self._dc -= d

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

    glass_ctl = GlassController(cfg_path)
    glass_ctl.start()
