from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys

from glass_controller import GlassController
from glass_radar import GlassRadar
import utils

SCRIPT_DIR = Path(__file__).parent


class Glass():
    def __init__(self, cfg_path):
        self.dt = None

        self.cfg_path = Path(cfg_path)
        self.cfg_mtime = self.cfg_path.stat().st_mtime
        self.cfg = utils.load_json(self.cfg_path)

        self.radar_1 = GlassRadar(self.cfg['radar_1'])
        self.radar_2 = GlassRadar(self.cfg['radar_2'])

        cmd = [
            "python",
            str(SCRIPT_DIR / "glass_controller.py"),
            str(self.cfg_path)]
        self.ctl_proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True)

        self.state = GlassController.STATE_OFF
        self.no_cmd_until_dt = datetime.now()

    def check_config(self):
        cfg_mtime = self.cfg_path.stat().st_mtime
        if cfg_mtime != self.cfg_mtime:
            text = f"{self.dt}: exiting due to config file change"
            print(text)
            sys.exit(1)

    def process(self):
        f1 = self.radar_1.process()
        if not f1:
            if self.radar_1.n_frame_failures >= self.RADAR_MAX_FRAME_FAILURES:
                text = f"{self.dt}: exiting due to radar 1 failures"
                print(text)
                sys.exit(1)
            return

        f2 = self.radar_2.process()
        if not f2:
            if self.radar_2.n_frame_failures >= self.RADAR_MAX_FRAME_FAILURES:
                text = f"{self.dt}: exiting due to radar 2 failures"
                print(text)
                sys.exit(1)
            return

        if self.ctl_proc.poll():
            ctlcode = self.ctl_proc.returncode
            text = f"{self.dt}: exiting due to glass controller stop (its returncode is {ctlcode})"
            print(text)
            sys.exit(1)

        both_present = self.radar_1.human_present and self.radar_2.human_present

        cmd = None
        if (self.state != GlassController.STATE_ON) and both_present:
            cmd = GlassController.CMD_ON
        elif (self.state != GlassController.STATE_OFF) and (not both_present):
            cmd = GlassController.CMD_OFF

        if (cmd is not None) and (self.dt > self.no_cmd_until_dt):
            self.ctl_proc.stdin.write(cmd)
            self.ctl_proc.stdin.flush()

            if cmd == GlassController.CMD_ON:
                self.state = GlassController.STATE_ON
            elif cmd == GlassController.CMD_OFF:
                self.state = GlassController.STATE_OFF

            self.no_cmd_until_dt = self.dt + timedelta(seconds=3)

        self.stats = [
            self.dt,

            self.radar_1.in_waiting,
            self.radar_1.distance_raw,
            self.radar_1.distance_reliable,
            self.radar_1.angle_abs_raw,
            self.radar_1.angle_abs_reliable,

            self.radar_2.in_waiting,
            self.radar_2.distance_raw,
            self.radar_2.distance_reliable,
            self.radar_2.angle_abs_raw,
            self.radar_2.angle_abs_reliable,

            self.state,
            both_present,
        ]
        print(self.stats)

    def start(self):
        while True:
            self.dt = datetime.now()
            self.check_config()
            self.process()


if __name__ == "__main__":
    try:
        cfg_path = sys.argv[1]
    except:
        print("No path for configuration provided")
        sys.exit(1)

    glass = Glass(cfg_path)
    glass.start()
