import logging
import time
import threading
import os

import cv2
import numpy as np
from streamlink import Streamlink

THRESHOLD = float(os.getenv('THRESHOLD'))
INTERVAL = int(os.getenv('TWITCH_INTERVAL'))

TMP_STREAM_FILE = 'stream.bin'
TEMPLATE_FOLDER = 'templates'

logger = logging.getLogger('twitch')


class SetInterval:
    def __init__(self, interval, action):
        self.interval = interval
        self.action = action
        self.stopEvent = threading.Event()
        thread = threading.Thread(target=self.__setInterval)
        thread.start()

    def __setInterval(self):
        nextTime = time.time()
        while not self.stopEvent.wait(nextTime - time.time()):
            self.action()
            nextTime = time.time() + self.interval

    def cancel(self):
        self.stopEvent.set()


class Twitch:
    def __init__(self, out_folder):
        self.registry = {}
        self.out_folder = out_folder

    def fetch_frame(self, channel):
        streamer = Streamlink()
        streamer.set_plugin_option('twitch', 'disable-ads', True)
        streams = streamer.streams(f"https://twitch.tv/{channel}")
        if len(streams) == 0:
            return None
        stream = streams['1080p60']

        # download enough data to make sure the first frame is there
        fd = stream.open()
        tmp = os.path.join(self.out_folder, TMP_STREAM_FILE)
        with open(tmp, 'wb') as f:
            data = fd.read(1024 ** 2)
            f.write(data)
        fd.close()

        capture = cv2.VideoCapture(tmp)
        imgdata = capture.read()[1]
        return imgdata

    def find_template(self, image_data, template_file, result_file):
        template = cv2.imread(template_file, cv2.IMREAD_UNCHANGED)
        h, w = template.shape[:2]

        tm = template[:, :, 0:3]

        res = cv2.matchTemplate(image_data, tm, cv2.TM_CCORR_NORMED)

        loc = np.where(res >= THRESHOLD)
        result = image_data.copy()
        found = len(loc[0]) > 0
        for pt in zip(*loc[::-1]):
            cv2.rectangle(result, pt, (pt[0] + w, pt[1] + h), (0, 0, 255), 1)
            logger.debug(f'{pt}: {res[pt[1]][pt[0]]}')

        # save results
        if found:
            logger.debug(f'Flushing result to file')
            dir = os.path.dirname(result_file)
            if not os.path.exists(dir):
                os.makedirs(dir)
            cv2.imwrite(result_file, result)
        else:
            logger.debug(f'Not found anything')

    def run_job(self, name, channel, template):
        logger.info(f'Running job {name}')
        data = self.fetch_frame(channel)
        if data is None:
            logger.debug(f'Stream {channel} is down')
        else:
            logger.debug(f'Finding template {template}')
            self.find_template(data, os.path.join(TEMPLATE_FOLDER, f'{template}.png'), os.path.join(self.out_folder, channel, f'{template}.png'))

    def job_name(self, channel, template):
        return f'{channel}:{template}'

    def add(self, channel, template):
        name = self.job_name(channel, template)
        self.registry[name] = SetInterval(INTERVAL, lambda: self.run_job(name, channel, template))
        logger.debug(f'Job {name} is scheduled')

    def remove(self, channel, template):
        name = self.job_name(channel, template)
        if name in self.registry:
            ev = self.registry[name]
            ev.cancel()
            logger.debug(f'Job {name} is removed')
        else:
            logger.debug(f'Job {name} not found')
