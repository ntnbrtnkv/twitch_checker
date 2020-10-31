import logging
import os

import telegram.ext as t

logger = logging.getLogger('telegram-bot')

TOKEN = os.getenv('TELEGRAM_TOKEN')
INTERVAL = int(os.getenv('BOT_INTERVAL'))

class Bot:
    def __init__(self, out_folder, twitch):
        self.out_folder = out_folder
        self.twitch = twitch

    def job_name(self, chat_id, channel, item):
        return f'{chat_id}:{channel}:{item}'

    def check(self, context):
        job = context.job
        [chat_id, channel, item] = job.context
        logger.info('Check')
        p = os.path.join(self.out_folder, channel, f'{item}.png')
        found = os.path.isfile(p)
        if found:
            logger.debug('Found, sending photo')
            context.bot.sendPhoto(chat_id=chat_id, photo=open(p, 'rb'))
            logger.debug('Remove photo from disk')
            os.remove(p)
        else:
            logger.debug('Not found')

    def watch(self, update, context):
        chat_id = update.message.chat_id
        try:
            [channel, obj] = context.args
            job_context = [
                chat_id,
                channel,
                obj
            ]
            context.job_queue.run_repeating(self.check, INTERVAL, context=job_context,
                                            name=self.job_name(chat_id, channel, obj))
            self.twitch.add(channel, obj)
            update.message.reply_text('Job scheduled')
        except (IndexError, ValueError):
            update.message.reply_text('Usage: /watch <channel> <eoe|bread|axe>')

    def remove_job_if_exists(self, name, context):
        """Remove job with given name. Returns whether job was removed."""
        current_jobs = context.job_queue.get_jobs_by_name(name)
        if not current_jobs:
            return False
        for job in current_jobs:
            job.schedule_removal()
        return True

    def stop(self, update, context):
        """Remove the job if the user changed their mind."""
        chat_id = update.message.chat_id
        try:
            [channel, obj] = context.args
            job_removed = self.remove_job_if_exists(self.job_name(chat_id, channel, obj), context)
            if job_removed:
                self.twitch.remove(channel, obj)
                text = 'Watch successfully cancelled!'
            else:
                text = 'You have no active watchers.'
            update.message.reply_text(text)
        except (IndexError, ValueError):
            update.message.reply_text('Usage: /stop <channel> <eoe|bread|axe>')

    def run(self):
        updater = t.Updater(TOKEN, use_context=True)

        dp = updater.dispatcher

        dp.add_handler(t.CommandHandler('watch', self.watch))
        dp.add_handler(t.CommandHandler('stop', self.stop))

        logger.info('Bot starting')

        updater.start_polling()

        updater.idle()