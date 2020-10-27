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
import datetime
import pytz

from random import randrange
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

script_dir = os.path.dirname(__file__)

def buildPath(relativePath):
    return os.path.join(script_dir, relativePath)

config = json.load(open(buildPath('conf/appConfig.json')))
content = json.load(open(buildPath('conf/appContent.json')))
timezone = pytz.timezone('Europe/Rome')

numFrasiConte = len(content['sentences']['conte'])
numSalutiConte = len(content['greetings'])


HELP = '{} non verrai abbandonato a te stesso'
THE_SENTENCE = 'a breve il verdetto'
KEYWORDS_VERDETTO = ['furla', 'zoggia', 'daniele', 'verdetto', 'decreto', 'dpcm', 'conte', 'governo', 'casalino', 'rocco']
KEYWORDS_AUTOCERTIFICAZIONE = ['autocertificazione', 'cazzo', 'tiro', 'tiri', 'tira', 'foglio', 'fogli', 'coprifuoco']

BASE_URL = 'https://raw.githubusercontent.com/pcm-dpc/COVID-19/master/dati-json/'
URL_COMUNI = 'https://raw.githubusercontent.com/matteocontrini/comuni-json/master/comuni.json'
REGIONI= 'dpc-covid19-ita-regioni-latest.json'

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)


"""
START OF COMMANDS SECTION
"""


# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.
def start(update, context):
    """Send a message when the command /start is issued."""
    randomIndex = randrange(numSalutiConte)
    user = update.message.from_user
    logger.info('User {} started the conversation.'.format(user.first_name))
    update.message.reply_text(content['greetings'][randomIndex].format(greetings(user.first_name)))


def conte_command(update, context):
    randomIndex = randrange(numFrasiConte)
    # update.message.bot.send_photo(chat_id=update.effective_chat.id, photo=open("/home/marco/Documenti/python-telegram-bot/examples/photo_2020-10-25_13-46-43.jpg", 'rb'))
    update.message.reply_text(content['sentences']['conte'][randomIndex])


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


"""
END OF COMMANDS SECTION
"""

#================================================================================

"""
START OF UTILITY SECTION
"""

def greetings(name):
    rome_now = datetime.datetime.now(timezone)
    actualHour = rome_now.hour
    if (actualHour >= 13 and actualHour < 17):
      return 'Buon pomeriggio {}'.format(name)
    elif (actualHour >= 17):
        return 'Buona sera {}'.format(name)
    elif (actualHour >= 6 and actualHour < 13):
        return 'Buongiorno {}'.format(name)
    else:
         pass

def handle_message(update, context):
    text = update.message.text.lower()
    splitText = text.split()
    if any(x in KEYWORDS_VERDETTO for x in splitText):
        echo_sentence(update, context, THE_SENTENCE)
    elif any(x in KEYWORDS_AUTOCERTIFICAZIONE for x in splitText):
        update.message.bot.send_photo(chat_id=update.effective_chat.id, photo=open(buildPath("/media/photo_2020-10-25_23-05-49.jpg"), 'rb'))


def echo_sentence(update, context, sentence=THE_SENTENCE):
    """Echo the user message."""
    update.message.reply_text(sentence)


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


"""
END OF UTILITY SECTION
"""

#==============================================================================


def main():
    """ Get configurations """
    token = config['token']
    appName = config['name']
    port = config['port']
    listen = config['listen']


    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(token, use_context=True)

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
    updater.start_webhook(listen=listen,
                          port=int(os.environ.get('PORT', port)),
                          url_path=token)
    # updater.bot.set_webhook(url=settings.WEBHOOK_URL)
    updater.bot.set_webhook(appName + token)

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
