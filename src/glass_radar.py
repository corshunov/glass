import math

from radar_ld2450 import LD2450
import utils


class GlassRadar(LD2450):
    def __init__(self, cfg):
        self.UARTDEV = cfg['uartdev']
        self.MAX_FRAME_FAILURES = cfg['max_frame_failures']
        self.BLUETOOTH = cfg['bluetooth']
        self.MULTI_TRACKING = cfg['multi_tracking']
        self.DISTANCE_DELTA = cfg['distance_delta']
        self.DISTANCE_MAX = cfg['distance_max']
        self.DISTANCE_THR = cfg['distance_thr']
        self.ANGLE_DELTA = cfg['angle_delta']
        self.ANGLE_ABS_MAX = cfg['angle_abs_max']
        self.ANGLE_ABS_THR = cfg['angle_abs_thr']

        super().__init__(self.UARTDEV)

        if self.BLUETOOTH:
            self.set_bluetooth_on(restart=True)
        else:
            self.set_bluetooth_off(restart=True)

        if self.MULTI_TRACKING:
            self.set_multi_tracking()
        else:
            self.set_single_tracking()

        self.set_zone_filtering(mode=0)

        self.stuck = False
        self.n_times_stuck = 0

        self.t_raw_prev = None
        self.t_raw = None

        self.distance_raw = None
        self.distance_reliable = self.DISTANCE_MAX

        self.angle_abs_raw = None
        self.angle_abs_reliable = self.ANGLE_ABS_MAX

        self.human_present = False

        print(f"Glass radar initialized ({self.UARTDEV})")

    def process(self):
        self.t_raw_prev = self.t_raw

        data = self.get_data()

        data_ok = True
        if data is None:
            data_ok = False

        data_present = False
        if data_ok and len(data) > 0:
            data_present = True

        if data_present:
            data_extended = list(
                map(lambda t: (t, self.distance(t), self.angle(t)), data))

            self.t_raw, self.distance_raw, angle_raw = \
                min(data_extended, key=lambda t: t[1])

            self.angle_abs_raw = math.fabs(angle_raw)
        else:
            self.t_raw = None
            self.distance_raw = None
            self.angle_abs_raw = None

        if data_present:
            distance_diff = utils.clamp(
                self.distance_raw - self.distance_reliable,
                -self.DISTANCE_DELTA,
                self.DISTANCE_DELTA)
        else:
            distance_diff = self.DISTANCE_DELTA

        if data_present:
            angle_diff = utils.clamp(
                self.angle_abs_raw - self.angle_abs_reliable,
                -self.ANGLE_DELTA,
                self.ANGLE_DELTA)
        else:
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
            self.human_present = False

        if data_present and (self.t_raw == self.t_raw_prev):
                self.n_times_stuck += 1
        else:
            self.n_times_stuck -= 1

        if self.n_times_stuck > 5:
            self.n_times_stuck = 5
        elif self.n_times_stuck < 0:
            self.n_times_stuck = 0

        if self.n_times_stuck == 5:
            self.stuck = True
        elif self.n_times_stuck == 0:
            self.stuck = False

        return data_ok


if __name__ == "__main__":
    import sys

    try:
        cfg_path = sys.argv[1]
    except:
        print("No argument for UART device provided")
        sys.exit(1)


    cfg = utils.load_json(cfg_path)
    r = GlassRadar(cfg['radar_2'])

    try:
        while True:
            f = r.process()
            if not f:
                continue

            if r.distance_raw:
                sys.stdout.write(f"{r.in_waiting:4} | "\
                                 f"{'stuck' if r.stuck else ' --- '} | "\
                                 f"{r.distance_raw:5.0f} / {r.distance_reliable:5.0f} | "\
                                 f"{r.angle_abs_raw:4.0f} / {r.angle_abs_reliable:4.0f}\n")
            else:
                sys.stdout.write(f"   - | "\
                                 f"    - | "\
                                 f"    - /     - | "\
                                 f"   - /    -\n")

            sys.stdout.flush()

    except KeyboardInterrupt:
        print("\nExiting...\n")
