#!/usr/bin/env python
# -*- coding: utf-8 -*-
# This program is dedicated to the public domain under the CC0 license.

"""
Simple Bot to reply to Telegram messages.

First, a few handler functions are defined. Then, those functions are passed to
the Dispatcher and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.

Usage:
Basic Echobot example, repeats messages.
Press Ctrl-C on the command line or send a signal to the process to stop the
bot.

Telegram commands:
start - Buongiorno da Conte
help - Aiuto da Conte
conte - Foto di Conte
update - Aggiornamenti da Conte
"""

import logging
import json
import urllib.request
import os

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

AUTH_TOKEN = '1132815578:AAHx0IW2ZpPAChG9Yo-7mQVJL_8NqezQFY8'
APP_NAME = 'abreveilverdetto'
GREETINGS = 'Buongiorno {}, siamo consapevoli dei sacrifici'
HELP = '{} non verrai abbandonato a te stesso'
THE_SENTENCE = 'a breve il verdetto'
KEYWORDS = ['furla', 'zoggia', 'daniele', 'verdetto', 'decreto', 'dpcm', 'conte', 'governo', 'casalino', 'rocco']

BASE_URL = 'https://raw.githubusercontent.com/pcm-dpc/COVID-19/master/dati-json/'
REGIONI= 'dpc-covid19-ita-regioni-latest.json'

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)


PORT = int(os.environ.get('PORT', '8443'))


# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    """Send a message when the command /start is issued."""
    user = update.message.from_user
    logger.info('User {} started the conversation.'.format(user.first_name))
    update.message.reply_text(GREETINGS.format(user.first_name))


def conte_command(update, context):
    # update.message.bot.send_photo(chat_id=update.effective_chat.id, photo=open("/home/marco/Documenti/python-telegram-bot/examples/photo_2020-10-25_13-46-43.jpg", 'rb'))
    update.message.reply_text('a breve la foto')


def help_command(update, context):
    """Send a message when the command /help is issued."""
    user = update.message.from_user
    update.message.reply_text(HELP.format(user.first_name))


def update_command(update, context):
    """Send a message when the command /update is issued."""
    user = update.message.from_user
    with urllib.request.urlopen(BASE_URL + REGIONI) as url:
        regioni = json.loads(url.read().decode())
        indice = next((i for i, item in enumerate(regioni) if item.codice_regione == '5'), -1)
        print('Totale positivi {}'.format(regioni[indice]["totale_casi"]))


def handle_message(update, context):
    if update.message.text.lower() in KEYWORDS:
        echo_sentence(update, context, THE_SENTENCE)


def echo_sentence(update, context, sentence=THE_SENTENCE):
    """Echo the user message."""
    update.message.reply_text(sentence)


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(AUTH_TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('conte', conte_command))
    dp.add_handler(CommandHandler('update', echo_sentence))
    dp.add_handler(CommandHandler('help', help_command))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

     # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_webhook(listen="0.0.0.0",
                          port=PORT,
                          url_path=AUTH_TOKEN)
    # updater.bot.set_webhook(url=settings.WEBHOOK_URL)
    updater.bot.set_webhook(APP_NAME + AUTH_TOKEN)

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
