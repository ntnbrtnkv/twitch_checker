import logging
import os

import telegram.ext as t

logger = logging.getLogger('telegram-bot')

TOKEN = os.getenv('TELEGRAM_TOKEN')
INTERVAL = int(os.getenv('BOT_INTERVAL'))
THRESHOLD = float(os.getenv('THRESHOLD'))


class Bot:
    def __init__(self, out_folder, twitch):
        self.out_folder = out_folder
        self.twitch = twitch
        self.jobs = {}

    def global_job_name(self, chat_id, channel, item):
        return f'{chat_id}:{channel}:{item}'

    def job_name(self, channel, item):
        return f'{channel}:{item}'

    def parse_job(self, job_name):
        return job_name.split(':')

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
            [channel, obj] = context.args[:2]
            job_context = [
                chat_id,
                channel,
                obj
            ]
            threshold = THRESHOLD
            if len(context.args) == 3:
                threshold = float(context.args[2])
            context.job_queue.run_repeating(self.check, INTERVAL, context=job_context,
                                            name=self.global_job_name(chat_id, channel, obj))
            job_name = self.job_name(channel, obj)
            if chat_id not in self.jobs:
                self.jobs[chat_id] = []
            if job_name in self.jobs[chat_id]:
                update.message.reply_text(f'Job {job_name} has been scheduled already')
                return
            self.jobs[chat_id].append(job_name)
            self.twitch.add(channel, obj, threshold)
            update.message.reply_text(f'Job {job_name} scheduled', )
        except (IndexError, ValueError):
            update.message.reply_text('Usage: /watch <channel> <eoe|bread|axe> <optional: threshold>')

    def remove_job_if_exists(self, chat_id, channel, obj, context):
        """Remove job with given name. Returns whether job was removed."""
        global_name = self.global_job_name(chat_id, channel, obj)
        job_name = self.job_name(channel, obj)
        current_jobs = context.job_queue.get_jobs_by_name(global_name)
        if not current_jobs:
            return 'You have no active watchers.'
        for job in current_jobs:
            job.schedule_removal()
        self.jobs[chat_id].remove(job_name)
        found = False
        for c in self.jobs:
            found = found or any(job == job_name for job in self.jobs[c])
        if not found:
            self.twitch.remove(channel, obj)
        return 'Watch successfully cancelled!'

    def stop(self, update, context):
        """Remove the job if the user changed their mind."""
        chat_id = update.message.chat_id
        try:
            [channel, obj] = context.args
            update.message.reply_text(self.remove_job_if_exists(chat_id, channel, obj, context))
        except (IndexError, ValueError):
            update.message.reply_text('Usage: /stop <channel> <eoe|bread|axe>')

    def my_jobs(self, update, context):
        chat_id = update.message.chat_id
        if chat_id not in self.jobs or len(self.jobs[chat_id]) == 0:
            update.message.reply_text('No active jobs')
        else:
            update.message.reply_text('\n'.join(self.jobs[chat_id]))

    def clear(self, update, context):
        chat_id = update.message.chat_id
        if chat_id not in self.jobs or len(self.jobs[chat_id]) == 0:
            update.message.reply_text('No active jobs')
        else:
            jobs = []
            for job in self.jobs[chat_id]:
                [channel, obj] = self.parse_job(job)
                self.remove_job_if_exists(chat_id, channel, obj, context)
                jobs.append(job)
            update.message.reply_text('Removed jobs:\n' + '\n'.join(jobs))

    def run(self):
        updater = t.Updater(TOKEN, use_context=True)

        dp = updater.dispatcher

        dp.add_handler(t.CommandHandler('watch', self.watch))
        dp.add_handler(t.CommandHandler('stop', self.stop))
        dp.add_handler(t.CommandHandler('jobs', self.my_jobs))
        dp.add_handler(t.CommandHandler('clear', self.clear))

        logger.info('Bot starting')

        updater.start_polling()

        updater.idle()
