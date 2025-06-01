import math

from radar_ld2450 import LD2450
import utils


class GlassRadar():
    def __init__(self, cfg):
        self.UARTDEV = cfg['uartdev']
        self.MAX_FRAME_FAILURES = cfg['max_frame_failures']
        self.DISTANCE_ACTION_DELTA = cfg['distance_action_delta']
        self.DISTANCE_ACTION_MAX = cfg['distance_action_max']
        self.DISTANCE_ACTION_THR = cfg['distance_action_thr']
        self.ANGLE_ACTION_DELTA = cfg['angle_action_delta']
        self.ANGLE_ACTION_ABS_MAX = cfg['angle_action_abs_max']
        self.ANGLE_ACTION_ABS_THR = cfg['angle_action_abs_thr']

        super().__init__(self.UARTDEV)

        self.set_bluetooth_off(restart=True)
        self.set_multi_tracking()
        self.set_zone_filtering(mode=0)

        self.distance_raw = None
        self.distance_action = None
        self.angle_raw = None
        self.angle_action = None
        self.action = False

        self.text = ""

        print(f"Glass radar initialized ({uartdev})")

    def process(self):
        data = self.get_data()
        if data is None:
            return False

        distance_angle_raw_list = list(
            map(lambda t: (self.distance(t), self.angle(t)), data))

        if distance_angle_raw_list:
            self.distance_raw, self.angle_raw = \
                min(distance_angle_raw_list, key=lambda t: t[0])
        else:
            self.distance_raw = None
            self.angle_raw = None

        if self.distance_raw:
            distance_action_diff = utils.clamp(
                self.distance_raw - self.distance_action,
                -self.DISTANCE_ACTION_DELTA,
                self.DISTANCE_ACTION_DELTA)

            angle_action_diff = utils.clamp(
                self.angle_raw - self.angle_action,
                -self.ANGLE_ACTION_DELTA,
                self.ANGLE_ACTION_DELTA)
        else:
            distance_action_diff = self.DISTANCE_ACTION_DELTA
            angle_action_diff = self.ANGLE_ACTION_DELTA

        self.distance_action = utils.clamp(
            self.distance_action + distance_action_diff,
            0,
            self.DISTANCE_ACTION_MAX)

        self.angle_action = utils.clamp(
            self.angle_action + angle_action_diff,
            -self.ANGLE_ACTION_ABS_MAX,
            self.ANGLE_ACTION_ABS_MAX)

        if (self.distance_action < self.DISTANCE_ACTION_THR) and \
           (math.fabs(self.angle_action) < self.ANGLE_ACTION_ABS_THR):
            self.action = True
        else:
            self.action = False

        self.text =  f"IN: {self.in_waiting:5}"
        if self.distance_raw:
            self.text += f" | Distance: "\
                    f"{self.distance_raw:6.0f} / "\
                    f"{self.distance_action:6.0f}"

            self.text += f" | Angle: "\
                    f"{self.angle_raw:7.2f} / "\
                    f"{self.angle_action:7.2f}"
        else:
            self.text += f" | Distance: "\
                    f"  --   / "\
                    f"{self.distance_action:6.0f}"

            self.text += f" | Angle: "\
                    f"  --   / "\
                    f"{self.angle_action:7.2f}"

        return True
