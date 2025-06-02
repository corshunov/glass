import math

from radar_ld2450 import LD2450
import utils


class GlassRadar(LD2450):
    def __init__(self, cfg):
        self.UARTDEV = cfg['uartdev']
        self.MAX_FRAME_FAILURES = cfg['max_frame_failures']
        self.DISTANCE_DELTA = cfg['distance_delta']
        self.DISTANCE_MAX = cfg['distance_max']
        self.DISTANCE_THR = cfg['distance_thr']
        self.ANGLE_DELTA = cfg['angle_delta']
        self.ANGLE_ABS_MAX = cfg['angle_abs_max']
        self.ANGLE_ABS_THR = cfg['angle_abs_thr']

        super().__init__(self.UARTDEV)

        self.set_bluetooth_off(restart=True)
        self.set_multi_tracking()
        self.set_zone_filtering(mode=0)

        self.distance_raw = None
        self.distance_reliable = self.DISTANCE_MAX
        self.angle_abs_raw = None
        self.angle_abs_reliable = self.ANGLE_ABS_MAX
        self.human_present = False

        print(f"Glass radar initialized ({self.UARTDEV})")

    def process(self):
        data = self.get_data()
        if data is None:
            return False

        distance_angle_raw_list = list(
            map(lambda t: (self.distance(t), self.angle(t)), data))

        if distance_angle_raw_list:
            self.distance_raw, angle_raw = \
                min(distance_angle_raw_list, key=lambda t: t[0])

            self.angle_abs_raw = math.fabs(angle_raw)
        else:
            self.distance_raw = None
            self.angle_abs_raw = None

        if self.distance_raw:
            distance_diff = utils.clamp(
                self.distance_raw - self.distance_reliable,
                -self.DISTANCE_DELTA,
                self.DISTANCE_DELTA)

            angle_diff = utils.clamp(
                self.angle_abs_raw - self.angle_abs_reliable,
                -self.ANGLE_DELTA,
                self.ANGLE_DELTA)
        else:
            distance_diff = self.DISTANCE_DELTA
            angle_diff = self.ANGLE_DELTA

        self.distance_reliable = utils.clamp(
            self.distance_reliable + distance_diff,
            0,
            self.DISTANCE_MAX)

        self.angle_abs_reliable = utils.clamp(
            self.angle_abs_reliable + angle_diff,
            0,
            self.ANGLE_ABS_MAX)

        if (self.distance_reliable < self.DISTANCE_THR) and \
           (self.angle_abs_reliable < self.ANGLE_ABS_THR):
            self.human_present = True
        else:
            self.human_preset = False

        return True
