from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys
import traceback

from glass_driver import GlassDriver
from glass_radar import GlassRadar
import utils

SCRIPT_DIR = Path(__file__).parent


class Glass():
    STAT_COLS = [
        "timestamp",

        "glass_on",

        "radar_1_in_waiting",
        "radar_1_stuck",
        "radar_1_distance_raw",
        "radar_1_distance_reliable",
        "radar_1_angle_abs_raw",
        "radar_1_angle_abs_reliable",
        "radar_1_human_present",

        "radar_2_in_waiting",
        "radar_2_stuck",
        "radar_2_distance_raw",
        "radar_2_distance_reliable",
        "radar_2_angle_abs_raw",
        "radar_2_angle_abs_reliable",
        "radar_2_human_present",

        "cmd_allowed",
        "both_present",
        "stuck",
    ]

    def __init__(self, cfg_path):
        self.dt = None

        self.cfg_path = Path(cfg_path)
        self.cfg_mtime = self.cfg_path.stat().st_mtime

        self.cfg = utils.load_json(self.cfg_path)

        self.radar_1 = GlassRadar(self.cfg['radar_1'])
        self.radar_2 = GlassRadar(self.cfg['radar_2'])

        self.DELAY_STATE = self.cfg['glass_driver']['delay_state']

        self.stat_dir = Path.cwd() / "stats"
        self.stat_dir.mkdir(exist_ok=True)

        self.stat_f = None

        cmd = [
            "python",
            str(SCRIPT_DIR / "glass_driver.py"),
            str(self.cfg_path)]
        self.glass_driver_proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True)

        self.glass_on = False
        self.no_cmd_until_dt = datetime.now()

    def cleanup(self):
        try:
            self.stat_f.close()
        except:
            pass

    def check_config(self):
        try:
            cfg_mtime = self.cfg_path.stat().st_mtime
        except:
            return

        if cfg_mtime != self.cfg_mtime:
            text = f"{self.dt}: exiting due to config file change"
            print(text)
            sys.exit(1)

    def process(self):
        self.dt = datetime.now()

        self.check_config()

        f1 = self.radar_1.process()
        f2 = self.radar_2.process()

        if (not f1) and (self.radar_1.n_frame_failures >= self.radar_1.MAX_FRAME_FAILURES):
            text = f"{self.dt}: exiting due to radar 1 failures"
            print(text)
            sys.exit(1)

        if (not f2) and (self.radar_2.n_frame_failures >= self.radar_2.MAX_FRAME_FAILURES):
            text = f"{self.dt}: exiting due to radar 2 failures"
            print(text)
            sys.exit(1)

        if self.glass_driver_proc.poll():
            code = self.glass_driver_proc.returncode
            text = f"{self.dt}: exiting due to glass driver stop (its returncode is {code})"
            print(text)
            sys.exit(1)

        if (not f1) or (not f2):
            return

        self.radar_1.stuck = False
        self.radar_1.human_present = True

        cmd_allowed = self.dt > self.no_cmd_until_dt
        both_present = self.radar_1.human_present and self.radar_2.human_present
        stuck = self.radar_1.stuck or self.radar_2.stuck

        cmd = None
        if cmd_allowed:
            if (not self.glass_on) and both_present and (not stuck):
                cmd = GlassDriver.CMD_ON
            elif self.glass_on and (not both_present):
                cmd = GlassDriver.CMD_OFF

        if cmd is not None:
            self.glass_driver_proc.stdin.write(f"{cmd}\n")
            self.glass_driver_proc.stdin.flush()

            if cmd == GlassDriver.CMD_ON:
                self.glass_on = True
            elif cmd == GlassDriver.CMD_OFF:
                self.glass_on = False

            self.no_cmd_until_dt = self.dt + timedelta(seconds=self.DELAY_STATE)

        if self.radar_1.distance_raw is None:
            d1_raw_text = "-----"
        else:
            d1_raw_text = f"{self.radar_1.distance_raw:5.0f}"

        if self.radar_1.angle_abs_raw is None:
            a1_raw_text = "-----"
        else:
            a1_raw_text = f"{self.radar_1.angle_abs_raw:5.0f}"

        if self.radar_2.distance_raw is None:
            d2_raw_text = "-----"
        else:
            d2_raw_text = f"{self.radar_2.distance_raw:5.0f}"

        if self.radar_2.angle_abs_raw is None:
            a2_raw_text = "-----"
        else:
            a2_raw_text = f"{self.radar_2.angle_abs_raw:5.0f}"

        text = f"Glass: {' ON' if self.glass_on else 'OFF'}"

        text += (f"\n[1] {self.radar_1.in_waiting:4} | "
                 f"{'stuck' if self.radar_1.stuck else '-----'} | "
                 f"{d1_raw_text} / {self.radar_1.distance_reliable:5.0f} | "
                 f"{a1_raw_text} / {self.radar_1.angle_abs_reliable:5.0f} | "
                 f"{'yes' if self.radar_1.human_present else ' no'}")

        text += (f"\n[2] {self.radar_2.in_waiting:4} | "
                 f"{'stuck' if self.radar_2.stuck else '-----'} | "
                 f"{d2_raw_text} / {self.radar_2.distance_reliable:5.0f} | "
                 f"{a2_raw_text} / {self.radar_2.angle_abs_reliable:5.0f} | "
                 f"{'yes' if self.radar_2.human_present else ' no'}")

        text += f"\ncmd_allowed: {'yes' if cmd_allowed else ' no'} | both_present: {both_present} | stuck: {stuck}"

        #if cmd == GlassDriver.CMD_ON:
        #    text += (f"\n================================="
        #             f"\n=====           ON          ====="
        #             f"\n=================================")
        #elif cmd == GlassDriver.CMD_OFF:
        #    text += (f"\n================================="
        #             f"\n=====          OFF          ====="
        #             f"\n=================================")

        text += "\n"
        print(text, flush=True)


        stat = (f"{self.dt},"

                f"{self.glass_on},"

                f"{self.radar_1.in_waiting},"
                f"{self.radar_1.stuck},"
                f"{self.radar_1.distance_raw},"
                f"{self.radar_1.distance_reliable},"
                f"{self.radar_1.angle_abs_raw},"
                f"{self.radar_1.angle_abs_reliable},"
                f"{self.radar_1.human_present},"

                f"{self.radar_2.in_waiting},"
                f"{self.radar_2.stuck},"
                f"{self.radar_2.distance_raw},"
                f"{self.radar_2.distance_reliable},"
                f"{self.radar_2.angle_abs_raw},"
                f"{self.radar_2.angle_abs_reliable},"
                f"{self.radar_2.human_present},"

                f"{cmd_allowed},"
                f"{both_present},"
                f"{stuck}")

        self.stat_f.write(f"{stat}\n")

    def start(self):
        stat_name = datetime.now().strftime("%Y%m%dT%H%M%S")
        stat_path = self.stat_dir / f"{stat_name}.csv"
        self.stat_f = stat_path.open("a")

        cols = ",".join(self.STAT_COLS)
        self.stat_f.write(f"{cols}\n")

        while True:
            self.process()


if __name__ == "__main__":
    try:
        cfg_path = sys.argv[1]
    except:
        print("No path for configuration provided")
        sys.exit(1)

    glass = Glass(cfg_path)

    try:
        glass.start()
    except:
        traceback.print_exc()
    finally:
        glass.cleanup()
