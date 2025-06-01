import RPi.GPIO as GPIO

from rpi_hardware_pwm import HardwarePWM
import utils


class GlassController():
    STATE_OFF             = 0
    STATE_ON              = 1
    STATE_UNKNOWN         = 2

    def __init__(self, cfg):
        self.DC_OFF = cfg['dc_off']
        self.DC_OFF_BORDER_1 = cfg['dc_off_border_1']
        self.DC_OFF_BORDER_2 = cfg['dc_off_border_2']
        self.DC_DELTA_OFF_START = cfg['dc_delta_off_start']
        self.DC_DELTA_OFF_MIDDLE = cfg['dc_delta_off_middle']
        self.DC_DELTA_OFF_END = cfg['dc_delta_off_end']

        self.DC_ON = cfg['dc_on']
        self.DC_ON_BORDER_1 = cfg['dc_on_border_1']
        self.DC_ON_BORDER_2 = cfg['dc_on_border_2']
        self.DC_DELTA_ON_START = cfg['dc_delta_on_start']
        self.DC_DELTA_ON_MIDDLE = cfg['dc_delta_on_middle']
        self.DC_DELTA_ON_END = cfg['dc_delta_on_end']

        self._pwm = HardwarePWM(channel=0, hz=111, chip=0)
        self._dc = None
        self.dc = self.DC_OFF

        print(f"Glass controller initialized")

    def __del__(self):
        try:
            self._pwm.stop()
        except:
            pass

    @property
    def state(self):
        if self._dc == self.DC_OFF:
            return self.STATE_OFF
        elif self._dc == self.DC_ON:
            return self.STATE_ON
        
        return self.STATE_UNKNOWN

    @property
    def dc(self):
        return self._dc

    @dc.setter
    def dc(self, value):
        v = utils.clamp(value, self.DC_OFF, self.DC_ON)
        self._pwm.change_duty_cycle(v)
        self._dc = v

    def get_delta_on(self):
        if self._dc <= self.DC_ON_BORDER_1:
            return self.DC_DELTA_ON_START
        elif self._dc <= self.DC_ON_BORDER_2:
            return self.DC_DELTA_ON_MIDDLE
        else:
            return self.DC_DELTA_ON_END

    def get_delta_off(self):
        if self._dc <= self.DC_OFF_BORDER_1:
            return self.DC_DELTA_OFF_START
        elif self._dc <= self.DC_OFF_BORDER_2:
            return self.DC_DELTA_OFF_MIDDLE
        else:
            return self.DC_DELTA_OFF_END

    def turn_on(self):
        if self.state == 1:
            return

        while (self._dc < self.DC_ON):
            delta = self.get_delta_on()
            self.dc += delta

        print("Glass if ON")

    def turn_off(self):
        if self.state == -1:
            return

        while (self._dc > self.DC_OFF):
            delta = self.get_delta_off()
            self.dc -= delta

        print("Glass if OFF")
