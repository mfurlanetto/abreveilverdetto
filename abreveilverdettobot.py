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
saluti - Saluti da Conte
cts - Estrazione casuale di 5 membri del Comitato Tecnico Scientifico
conte - Foto di Conte
tortadimele - Foto di una torta di mele
comune - Un comune a caso
help - Aiuto da Conte
update - Aggiornamenti da Conte
"""

import logging
import json
import urllib.request
import os
import datetime
import pytz

from random import randrange
from telegram import ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

script_dir = os.path.dirname(__file__)

def buildPath(relativePath):
    return os.path.join(script_dir, relativePath)

config = json.load(open(buildPath('conf/appConfig.json')))
content = json.load(open(buildPath('conf/appContent.json')))
timezone = pytz.timezone('Europe/Rome')

numFrasiConte = len(content['sentences']['conte'])
numSalutiConte = len(content['greetings'])
ctsMaxLen = 5
ctsSize = len(content['CTS'])
ctsList = content['CTS']

thunderstorm = u'\U0001F4A8'    # Code: 200's, 900, 901, 902, 905
drizzle = u'\U0001F4A7'         # Code: 300's
rain = u'\U00002614'            # Code: 500's
snowflake = u'\U00002744'       # Code: 600's snowflake
snowman = u'\U000026C4'         # Code: 600's snowman, 903, 906
atmosphere = u'\U0001F301'      # Code: 700's foogy
clearSky = u'\U00002600'        # Code: 800 clear sky
fewClouds = u'\U000026C5'       # Code: 801 sun behind clouds
clouds = u'\U00002601'          # Code: 802-803-804 clouds general
hot = u'\U0001F525'             # Code: 904


HELP = '{} non verrai abbandonato a te stesso'
THE_SENTENCE = 'a breve il verdetto'

URL_COMUNI = 'https://raw.githubusercontent.com/matteocontrini/comuni-json/master/comuni.json'

with urllib.request.urlopen(URL_COMUNI) as url:
    global COMUNI
    global TOT_COMUNI
    COMUNI = json.loads(url.read().decode())
    TOT_COMUNI = len(COMUNI)

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


def torta_command(update, context):
    randomIndex = randrange(5)
    update.message.bot.send_photo(chat_id=update.effective_chat.id, photo=open(buildPath("media/tortamele/{}.jpg".format(randomIndex)), 'rb'))

def conte_command(update, context):
    randomIndex = randrange(7)
    # update.message.bot.send_photo(chat_id=update.effective_chat.id, photo=open("/home/marco/Documenti/python-telegram-bot/examples/photo_2020-10-25_13-46-43.jpg", 'rb'))
    #update.message.reply_text(content['sentences']['conte'][randomIndex])
    update.message.bot.send_photo(chat_id=update.effective_chat.id, photo=open(buildPath("media/conte/{}.jpg".format(randomIndex)), 'rb'))


def cts_command(update, context):
    """Send a message when the command /cts is issued."""    
    user = update.message.from_user
    message = buildCtsMessage(user)
    update.message.bot.send_message(chat_id=update.effective_chat.id, text=message, 
                  parse_mode=ParseMode.HTML)

def comune_command(update, context):
    randIndex = randrange(TOT_COMUNI)
    comune = COMUNI[randIndex]
    message = 'Comune di <b>{}</b>\n'.format(comune['nome'])
    message += 'Provincia: {} ({})\n'.format(comune['provincia']['nome'], comune['sigla'])
    message += 'CAP: {}\n'.format(', '.join(comune['cap']))
    message += 'Abitanti: {}'.format(comune['popolazione'])
    update.message.bot.send_message(chat_id=update.effective_chat.id, text=message, 
                  parse_mode=ParseMode.HTML)


def help_command(update, context):
    """Send a message when the command /help is issued."""
    user = update.message.from_user
    update.message.reply_text(HELP.format(user.first_name))


def update_command(update, context):
    """Send a message when the command /update is issued."""
    user = update.message.from_user
    echo_sentence(update, context)



#================================================================================

"""
START OF UTILITY SECTION
"""

def isMorning(hour):
    return hour >= 6 and hour < 13

def isAfternoon(hour):
    return hour >= 13 and hour < 17

def greetings(name):
    greetings = ''
    actualHour = datetime.datetime.now(timezone).hour
    if isMorning(actualHour):
        greetings = 'Buongiorno'
    elif isAfternoon(actualHour):
        greetings = 'Buon pomeriggio'
    else:
        greetings = 'Buona sera'
    return '{} {}'.format(greetings, name)

def generateIndexList():
    i = 0
    list = []
    while i < ctsMaxLen:
        randIndex = randrange(ctsSize)
        if randIndex not in list:
            list.append(randIndex)
            i += 1
    return list

def buildCtsMessage(user):
    message = '<b>Comitato Tecnico-Scientifico</b>\n'
    indexlist = generateIndexList()
    for index in indexlist:
        message += '∘ {}\n'.format(ctsList[index])
    return message

def handle_message(update, context):
    splitText = update.message.text.lower().split()
    if any(x in content['keywords']['verdetto'] for x in splitText):
        echo_sentence(update, context, THE_SENTENCE)
    elif any(x in content['keywords']['autocert'] for x in splitText):
        update.message.bot.send_photo(chat_id=update.effective_chat.id, photo=open(buildPath("media/photo_2020-10-25_23-05-49.jpg"), 'rb'))
    else:
        pass


def echo_sentence(update, context, sentence=THE_SENTENCE):
    """Echo the user message."""
    update.message.reply_text(sentence)


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)



#==============================================================================


def main():

    logger.info('BOT STARTED')

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
    dp.add_handler(CommandHandler('saluti', start))
    dp.add_handler(CommandHandler('conte', conte_command))
    dp.add_handler(CommandHandler('cts', cts_command))
    dp.add_handler(CommandHandler('tortadimele', torta_command))
    dp.add_handler(CommandHandler('comune', comune_command))
    dp.add_handler(CommandHandler('update', echo_sentence))
    dp.add_handler(CommandHandler('help', help_command))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, handle_message))

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
