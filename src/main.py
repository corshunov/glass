from datetime import datetime
import sys

from glass_controller import GlassController
from glass_radar import GlassRadar
import utils


class Glass():
    def __init__(self, cfg_path):
        self.dt = None

        self.cfg_path = cfg_path
        self.cfg = utils.load_json(cfg_path)

        self.radar_1 = GlassRadar(self.cfg['radar_1'])
        self.radar_2 = GlassRadar(self.cfg['radar_2'])
        self.ctl = GlassController(self.cfg['controller'])

    def check_config(self):
        cfg_mtime = self.cfg_path.stat().st_mtime
        if cfg_mtime != self.cfg_mtime:
            text = "{self.dt}: exiting due to config file change"
            print(text)
            sys.exit(1)

    def process(self):
        f1 = self.radar_1.process()
        if not f1:
            if self.radar_1.n_frame_failures >= self.RADAR_MAX_FRAME_FAILURES:
                sys.exit(1)
            return

        f2 = self.radar_2.process()
        if not f2:
            if self.radar_2.n_frame_failures >= self.RADAR_MAX_FRAME_FAILURES:
                sys.exit(1)
            return

        state = self.stl.state
        action = self.radar_1.action and self.radar_2.action

        if (state != GlassController.STATE_ON) and action:
            self.ctl.turn_on()
        elif (state != GlassController.STATE_OFF) and (not action):
            self.ctl.turn_off()

        text = f"{self.dt}: {self.radar_1.text} || {self.radar_2.text} || {state} || {action}"
        print(text)

    def start(self):
        while True:
            self.dt = datetime.now()
            self.check_config()
            self.process()


if __name__ == "__main__":
    glass = Glass()
    glass.start()
