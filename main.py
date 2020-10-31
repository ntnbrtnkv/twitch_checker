import logging
import os
import shutil
import sys

from dotenv import load_dotenv

load_dotenv()
from bot import Bot
from twitch import Twitch

OUT_FOLDER = 'out'

logging.basicConfig(stream=sys.stdout, level=os.getenv('LOG_LEVEL'))

if os.path.exists(OUT_FOLDER):
    shutil.rmtree(OUT_FOLDER)
os.mkdir(OUT_FOLDER)

twitch = Twitch(OUT_FOLDER)
bot = Bot(OUT_FOLDER, twitch)
bot.run()
