from datetime import datetime, timedelta
from pathlib import Path
import sys

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.animation import FuncAnimation

from glass_radar import GlassRadar
import utils


class Plotter():
    def __init__(self, cfg_path):
        self.dt = None

        self.cfg_path = Path(cfg_path)
        self.cfg_mtime = self.cfg_path.stat().st_mtime
        self.cfg = utils.load_json(self.cfg_path)

        self.radar_1 = GlassRadar(self.cfg['radar_1'])
        self.radar_2 = GlassRadar(self.cfg['radar_2'])

        self.state = 0
        self.no_cmd_until_dt = datetime.now()

        self.x = 3000
        self.y = 3000
        self.ps = 1000
        self.fs = 20

    def check_config(self):
        cfg_mtime = self.cfg_path.stat().st_mtime
        if cfg_mtime != self.cfg_mtime:
            text = f"{self.dt}: exiting due to config file change"
            print(text)
            sys.exit(1)

    def process(self, frame):
        self.dt = datetime.now()
        self.check_config()

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

        both_present = self.radar_1.human_present and self.radar_2.human_present

        #####

        if self.radar_1.t_raw is None:
            offsets1 = [[None, None]]
        else:
            offsets1 = [list(self.radar_1.t_raw)]
        self.sc1.set_offsets(offsets1)

        if self.radar_1.distance_reliable:
            d1t = f'Distance: {self.radar_1.distance_reliable:6.0f} mm'
        else:
            d1t =  'Distance: -- mm'
        self.d1.set_text(d1t)

        if self.radar_1.angle_abs_reliable:
            a1t = f'Angle: {self.radar_1.angle_abs_reliable:4.0f} °'
        else:
            a1t =  'Angle: -- °'
        self.a1.set_text(a1t)

        if self.radar_2.t_raw is None:
            offsets2 = [[None, None]]
        else:
            offsets2 = [list(self.radar_2.t_raw)]
        self.sc2.set_offsets(offsets2)

        if self.radar_1.human_present:
            c1 = (1,0,0,0.2)
        else:
            c1 = (1,0,0,0)
        self.rect1.set_facecolor(c1)

        if self.radar_2.distance_reliable:
            d2t = f'Distance: {self.radar_2.distance_reliable:6.0f} mm'
        else:
            d2t =  'Distance: -- mm'
        self.d2.set_text(d2t)

        if self.radar_2.angle_abs_reliable:
            a2t = f'Angle: {self.radar_2.angle_abs_reliable:4.0f} °'
        else:
            a2t =  'Angle: -- °'
        self.a2.set_text(a2t)

        if self.radar_2.human_present:
            c2 = (1,0,0,0.2)
        else:
            c2 = (1,0,0,0)
        self.rect2.set_facecolor(c2)

        if both_present:
            glass_c = (0,0,0)
        else:
            glass_c = (1,1,1)
        self.glass.set_facecolor(glass_c)

        #####

        cmd = None
        if (self.state != 1) and both_present:
            cmd = 1
        elif (self.state != 0) and (not both_present):
            cmd = 0

        if (cmd is not None) and (self.dt > self.no_cmd_until_dt):
            if cmd == 1:
                self.state = 1
            elif cmd == 0:
                self.state = 0

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

        return (self.sc1, self.sc2,
                self.d1, self.d2,
                self.a1, self.a2)

    def start(self):
        fig, ax = plt.subplots(figsize=(15,8))
        ax.grid(True)
        ax.set_xlim(-self.x, self.x)
        ax.set_ylim(-self.y, self.y)
        ax.set_xlabel('x, mm')
        ax.set_ylabel('y, mm')
        
        self.sc1 = ax.scatter([], [], c='red', s=self.ps)
        self.d1 = ax.text(self.x-1500, self.y-250, '', fontsize=self.fs)
        self.a1 = ax.text(self.x-1500, self.y-500, '', fontsize=self.fs)
        self.rect1 = patches.Rectangle(
            (-self.x, self.y), self.x*2, self.y, linewidth=0)
        ax.add_patch(self.rect1)
        
        self.sc2 = ax.scatter([], [], c='green', s=self.ps)
        self.d2 = ax.text(self.x-1500, -self.y+500, '', fontsize=self.fs)
        self.a2 = ax.text(self.x-1500, -self.y+250, '', fontsize=self.fs)
        self.rect2 = patches.Rectangle(
            (-self.x, 0), self.x*2, self.y, linewidth=0)
        ax.add_patch(self.rect2)

        glass_w = 500
        glass_h = 200
        self.glass = patches.Rectangle(
            (-glass_w, glass_h), glass_w*2, glass_h*2, linewidth=3)
        ax.add_patch(self.glass)

        ani = FuncAnimation(fig=fig, func=self.process, cache_frame_data=False, blit=True)

        mng = plt.get_current_fig_manager()
        mng.full_screen_toggle()

        plt.show()


if __name__ == "__main__":
    try:
        cfg_path = sys.argv[1]
    except:
        print("No path for configuration provided")
        sys.exit(1)

    plotter = Plotter(cfg_path)
    plotter.start()
