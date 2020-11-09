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
start - Lista dei comandi
"""

import logging, json, os, time, utils.emoji

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from random import randrange
from telegram import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, ConversationHandler

os.environ['TZ'] = 'Europe/Rome'
time.tzset()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

script_dir = os.path.dirname(__file__)

def buildPath(relativePath):
    return os.path.join(script_dir, relativePath)

config = json.load(open(buildPath('conf/appConfig.json')))
content = json.load(open(buildPath('conf/appContent.json')))


SALUTI, CTS, DPCM, CONTE, BIMBE, COMUNE, COVID, GIURATO, TORTADIMELE, FIBONACCI, CENTOCENTOCENTO = range(11)


HELP = '{} non verrai abbandonato a te stesso'
BRISCOLA = 'Come fa 15+18 non fa 36 dio te maledica te do \'n sciafon che te copo d** ***'
THE_SENTENCE = 'a breve il verdetto'


medical = u'\U00002695'
maskFace = u'\U0001F637'
thermoFace = u'\U0001F912'
headstone = u'\U0001FAA6'
hospital = u'\U0001F3E5'
latinCross = u'\U0000271D'
biohazard = u'\U00002623'
house = u'\U0001F3E0'
bed = u'\U0001F6CF'
pill = u'\U0001F48A'
angel = u'\U0001F47C'
testTube = u'\U0001F9EA'
nose = u'\U0001F443'

logger = logging.getLogger(__name__)


"""
START OF COMMANDS SECTION
"""


# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.


def new_start(update, context):
    """Send a message when the command /start2 is issued."""
    user = update.message.from_user
    logger.info("User %s started the conversation.", user.first_name)
    
    keyboard = [
        [
            InlineKeyboardButton("SALUTI", callback_data=str(SALUTI)),
            InlineKeyboardButton("CTS", callback_data=str(10)),
            InlineKeyboardButton("DPCM", callback_data=str(10)),
        ],
        [
            InlineKeyboardButton("CONTE", callback_data=str(5)),
            InlineKeyboardButton("BIMBE", callback_data=str(10)),
            InlineKeyboardButton("COMUNE", callback_data=str(10))
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Seleziona comando', reply_markup=reply_markup)
    return 0


def start_command(update, context):
    """Send a message when the command /start is issued."""
    user = update.message.from_user
    logger.info('User {} started the conversation.'.format(user.first_name))
    message = '<b>{}</b>, di seguito la lista dei comandi:\n'.format(greetings(user.first_name))
    message += '/saluti - <i>Saluti da Conte</i>\n'
    message += '/cts - <i>Membri del Comitato Tecnico Scientifico a caso</i>\n'
    message += '/dpcm - <i>Un DPCM a caso</i>\n'
    message += '/conte - <i>Foto di Conte con frase</i>\n'
    message += '/bimbe - <i>Foto per le Bimbe di Conte</i>\n'
    message += '/comune - <i>Un comune a caso</i>\n'
    message += '/covid - <i>Dati nazionali sul COVID-19</i>\n'
    message += '/giurato - <i>Una frase a caso di Luca Giurato</i>\n'
    message += '/tortadimele - <i>Foto torte di mele</i>\n'
    message += '/help - <i>Aiuto da Conte</i>\n'
    message += '/fibonacci - <i>un prefisso di lunghezza variabile della successione di fibonacci</i>\n'
    message += '/centocentocento - <i>numero pseudocasuale multiplo di 5 nell\'intervallo [5;100]</i>\n'
    message += '/update - <i>Aggiornamenti da Conte</i>'
    update.message.bot.send_message(chat_id=update.effective_chat.id, 
        text=message, 
        parse_mode=ParseMode.HTML)


def saluti_command(update, context):
    """Send a message when the command /saluti is issued."""
    numSalutiConte = len(content['greetings'])
    randomIndex = randrange(numSalutiConte)
    user = update.message.from_user
    logger.info('User {} started the conversation.'.format(user.first_name))
    update.message.reply_text(content['greetings'][randomIndex].format(greetings(user.first_name)))

def saluti(update, context):
    """Send a message when the command /saluti is issued."""
    query = update.callback_query
    query.answer()
    numSalutiConte = len(content['greetings'])
    randomIndex = randrange(numSalutiConte)
    user = update.message.from_user
    logger.info('User {} chose saluti.'.format(user.first_name))
    query.edit_message_text(
        text=content['greetings'][randomIndex].format(greetings(user.first_name))
    )
    #update.message.reply_text(content['greetings'][randomIndex].format(greetings(user.first_name)))
    return ConversationHandler.END

def end(update, context):
    """Returns `ConversationHandler.END`, which tells the
    ConversationHandler that the conversation is over"""
    query = update.callback_query
    query.answer()
    query.edit_message_text(text="See you next time!")
    return ConversationHandler.END

def torta_command(update, context):
    randomIndex = randrange(5)
    update.message.bot.send_photo(chat_id=update.effective_chat.id, photo=open(buildPath("media/tortamele/{}.jpg".format(randomIndex)), 'rb'))

def conte_command(update, context):
    randomIndexImage = randrange(12)
    numFrasiConte = len(content['sentences']['conte'])
    randomIndexCaption = randrange(numFrasiConte)
    update.message.bot.send_photo(chat_id=update.effective_chat.id, 
        photo=open(buildPath("media/conte/{}.jpg".format(randomIndexImage)), 'rb'),
        caption=content['sentences']['conte'][randomIndexCaption])

def bimbe_command(update, context):
    love_dict = utils.emoji.love
    loveEmojis = list(love_dict.values())
    sizeLove = len(loveEmojis)
    randomIndexImage = randrange(20)
    update.message.bot.send_photo(chat_id=update.effective_chat.id, 
        photo=open(buildPath("media/bimbe/{}.jpg".format(randomIndexImage)), 'rb'),
        caption=loveEmojis[randrange(sizeLove)] + loveEmojis[randrange(sizeLove)] + loveEmojis[randrange(sizeLove)])


def cts_command(update, context):
    """Send a message when the command /cts is issued."""
    keyboard = [
        [
            InlineKeyboardButton("5", callback_data=str(5)),
            InlineKeyboardButton("10", callback_data=str(10)),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Quanti membri desideri?', reply_markup=reply_markup)

def dpcm_command(update, context):
    """Send a message when the command /dpcm is issued."""
    dpcmList = content['DPCM']
    dpcmSize = len(dpcmList)
    randIndex = randrange(dpcmSize)
    message = dpcmList[randIndex]
    update.message.reply_text('\"{}\"'.format(message))

def giurato_command(update, context):
    """Send a message when the command /giurato is issued."""    
    giuratoList = content['sentences']['giurato']
    giuratoSize = len(giuratoList)
    randIndex = randrange(giuratoSize)
    message = giuratoList[randIndex]
    update.message.reply_text('\"{}\"'.format(message))

def covid_command(update, context):
    reqCovid = Request(config['covid']['url'])
    COVID = json.loads(urlopen(reqCovid).read().decode())
    lastIndex = len(COVID) - 1
    latestData = COVID[lastIndex]['data']
    latestUpdate = latestData[0:10]
    nuoviPositivi = COVID[lastIndex]['nuovi_positivi']
    varOspedalizzati = COVID[lastIndex]['totale_ospedalizzati'] - COVID[lastIndex - 1]['totale_ospedalizzati']
    varTerapieI = COVID[lastIndex]['terapia_intensiva'] - COVID[lastIndex - 1]['terapia_intensiva']
    varIsolamento = COVID[lastIndex]['isolamento_domiciliare'] - COVID[lastIndex - 1]['isolamento_domiciliare']
    varDeceduti = COVID[lastIndex]['deceduti'] - COVID[lastIndex - 1]['deceduti']
    varTamponi = COVID[lastIndex]['tamponi'] - COVID[lastIndex - 1]['tamponi']
    percPosTamp = 100*COVID[lastIndex]['nuovi_positivi']/varTamponi
    signNuoviPositivi = ''
    if nuoviPositivi>0 : signNuoviPositivi = '+'
    signVarOspedalizzati = ''
    if varOspedalizzati>0 : signVarOspedalizzati = '+'
    signVarTerapieI = ''
    if varTerapieI>0 : signVarTerapieI = '+'
    signVarIsolamento = ''
    if varIsolamento>0 : signVarIsolamento = '+'
    signVarDeceduti = ''
    if varDeceduti>0 : signVarDeceduti = '+'
    signVarTamponi = ''
    if varTamponi>0 : signVarTamponi = '+'
    message = 'Ultimo aggiornamento: {}\n'.format(latestUpdate)
    message += '{}{} {}{}\n'.format(biohazard,thermoFace,signNuoviPositivi,nuoviPositivi)
    message += '{}{} {} ({}{})\n'.format(hospital,maskFace,COVID[lastIndex]['totale_ospedalizzati'],signVarOspedalizzati,varOspedalizzati)
    message += '{}{} {} ({}{})\n'.format(hospital,bed,COVID[lastIndex]['terapia_intensiva'],signVarTerapieI,varTerapieI)
    message += '{}{} {} ({}{})\n'.format(house,thermoFace,COVID[lastIndex]['isolamento_domiciliare'],signVarIsolamento,varIsolamento)
    message += '{}{} {} ({}{})\n'.format(latinCross,angel,COVID[lastIndex]['deceduti'], signVarDeceduti,varDeceduti)
    message += '{}{} {} ({}{})\n'.format(nose,testTube,COVID[lastIndex]['tamponi'], signVarTamponi,varTamponi)
    message += '{}\{} {:.3}%'.format(biohazard,testTube,percPosTamp)
    """
    message += hospital + maskFace + ' ' + varTerapieI + '\n'
    message += house + ' ' + varIsolamento + '\n'
    """
    update.message.bot.send_message(chat_id=update.effective_chat.id, text=message, 
                parse_mode=ParseMode.HTML)

def comune_command(update, context):
    zone_dict = utils.emoji.zone_color
    reqComuni = Request(config['comuni']['url'])
    comuni = json.loads(urlopen(reqComuni).read().decode())
    randIndex = randrange(len(comuni))
    comune = comuni[randIndex]
    urlWeather = config['openweathermap']['url'].format(comune['cap'][0], config['openweathermap']['token'])
    reqMeteo = Request(urlWeather)
    meteoStr = ''

    try:
        weather = json.loads(urlopen(reqMeteo).read().decode())
        meteoStr = '{} ({}) ᛫ {} °C\n'.format(getEmoji(weather['weather'][0]['id']), 
            weather['weather'][0]['description'].capitalize(),
            '%.1f' % weather['main']['temp'])
    except HTTPError as e:
        logger.error('Error code: ', e.code)
        meteoStr = content['MESSAGES']['WEATHER_URL_NOT_FOUND']
    except URLError as e:
        logger.error('Reason: ', e.reason)
        meteoStr = content['MESSAGES']['WEATHER_URL_NOT_FOUND']

    covid_serverity_color = next((region["covid_serverity_color"] for region in content['ItalianRegions'] if region['name'] == comune['regione']['nome']), None)

    message = '<b>{}</b>\n'.format(comune['nome'])
    message += '{} {} ({})\n'.format(comune['cap'][0], comune['provincia']['nome'], comune['sigla'])
    if covid_serverity_color is not None:
        message += 'Zone: ' + zone_dict.get(covid_serverity_color) + '\n'
    message += '{} abitanti\n'.format(comune['popolazione'])
    message += meteoStr
    message += 'I bar chiudono alle ore 18:00'
    update.message.bot.send_message(chat_id=update.effective_chat.id, text=message, 
                parse_mode=ParseMode.HTML)

def fibonacci_command(update, context):
    response = []
    error = False
    try:
        maxNumberOfIterations = int(context.args[0])
    except (IndexError):    
        response.append("maxNumberOfIterations parameter not passed")
        error = True
    except (ValueError):
        response.append("Exception converting maxNumberOfIterations parameter")
        response.append("Received value is {}".format(context.args[0]))
        error = True
    except:
        response.append("Generic exception while reading maxNumberOfIterations parameter")
        error = True
    if (error == True):
        maxNumberOfIterations = 10
        response.append("Default will be {}".format(maxNumberOfIterations))
    numberOfIterations = randrange(maxNumberOfIterations)
    sequence = [1, 1]
    if (numberOfIterations <= len(sequence)):
        sequence = sequence[:numberOfIterations]
    else:
        for _ in range(numberOfIterations):
            sequence.append(sequence[-1] + sequence[-2])
    response.append(', '.join(map(str, sequence)))
    update.message.bot.send_message(chat_id=update.effective_chat.id, text="\n".join(response), parse_mode=ParseMode.HTML)

def centocentocento_command(update, context):
    value = 5 + randrange(0, 100, 5)
    update.message.bot.send_message(chat_id=update.effective_chat.id, text="{}".format(value), parse_mode=ParseMode.HTML)

def help_command(update, context):
    """Send a message when the command /help is issued."""
    user = update.message.from_user
    update.message.reply_text(HELP.format(user.first_name))


#================================================================================

"""
START OF UTILITY SECTION
"""

def generateIndexList(qty, ctsSize):
    i = 0
    list = []
    while i < int(qty):
        randIndex = randrange(ctsSize)
        if randIndex not in list:
            list.append(randIndex)
            i += 1
    return list

def buildCtsMessage(qty):
    ctsList = content['CTS']
    ctsSize = len(ctsList)
    message = '<b>Comitato Tecnico-Scientifico</b>\n'
    indexlist = generateIndexList(qty, ctsSize)
    for index in indexlist:
        message += '∘ {}\n'.format(ctsList[index])
    return message

def ctsCommandHandler(update, context):
    query = update.callback_query
    query.answer()
    message = buildCtsMessage(query.data)
    query.edit_message_text(text=message, parse_mode=ParseMode.HTML)

def isMorning(hour):
    return hour >= 6 and hour < 13

def isAfternoon(hour):
    return hour >= 13 and hour < 17

def greetings(name):
    greetings = ''
    actualHour = time.strftime('%H')
    if isMorning(int(actualHour)):
        greetings = 'Buongiorno'
    elif isAfternoon(int(actualHour)):
        greetings = 'Buon pomeriggio'
    else:
        greetings = 'Buonasera'
    return '{} {}'.format(greetings, name)

def handle_message(update, context):
    message = update.message.text.replace('?', '')
    splitText = message.lower().split()
    if all(x in splitText for x in ['15', '18']):
        update.message.bot.send_photo(chat_id=update.effective_chat.id, 
            photo=open(buildPath("media/others/15e18.png"), 'rb'),
            caption=BRISCOLA)
    else:
        pass

def handle_sticker(update, context):
    logger.info('[STICKER] - UPDATE OBJ : {}'.format(update))


def echo_sentence(update, context, sentence=THE_SENTENCE):
    """Echo the user message."""
    update.message.reply_text(sentence)

"""
    Return related emojis according to weather
"""
def getEmoji(weatherID):
    weather_dict = utils.emoji.weather
    if weatherID:
        if str(weatherID)[0] == '2' or weatherID == 900 or weatherID==901 or weatherID==902 or weatherID==905:
            return weather_dict.get("thunderstorm")
        elif str(weatherID)[0] == '3':
            return  weather_dict.get("drizzle")
        elif str(weatherID)[0] == '5':
            return  weather_dict.get("rain")
        elif str(weatherID)[0] == '6' or weatherID==903 or weatherID== 906:
            return weather_dict("snowflake") + ' ' + weather_dict("snowman")
        elif str(weatherID)[0] == '7':
            return  weather_dict.get("atmosphere")
        elif weatherID == 800:
            return  weather_dict.get("clearSky")
        elif weatherID == 801:
            return  weather_dict.get("fewClouds")
        elif weatherID==802 or weatherID==803 or weatherID==803:
            return  weather_dict.get("clouds")
        elif weatherID == 904:
            return  weather_dict.get("hot")
        else:
            return weather_dict.get("defaultEmoji")    # Default emoji 
    else:
        return weather_dict.get("defaultEmoji")   # Default emoji


def error(update, context):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)



#==============================================================================


def main():

    logger.info('BOT STARTED')

    """ Get configurations """
    token = config['bot']['token']
    appName = config['bot']['name']
    port = config['bot']['port']
    listen = config['bot']['listen']


    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(token, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher
    
    #SALUTI, CTS, DPCM, CONTE, BIMBE, COMUNE, COVID, GIURATO, TORTADIMELE, FIBONACCI, CENTOCENTOCENTO = range(11)

        
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('test', new_start)],
        states={
            0: [
                CallbackQueryHandler(saluti, pattern='^' + str(SALUTI) + '$')
            ],
            1: [
                CallbackQueryHandler(end)
            ]
        },
        fallbacks=[CallbackQueryHandler(end)],
    )

    dp.add_handler(conv_handler)

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler('start', start_command))
    dp.add_handler(CommandHandler('test', start_command))
    dp.add_handler(CommandHandler('saluti', saluti_command))
    dp.add_handler(CommandHandler('conte', conte_command))
    dp.add_handler(CommandHandler('bimbe', bimbe_command))
    dp.add_handler(CommandHandler('cts', cts_command))
    dp.add_handler(CommandHandler('dpcm', dpcm_command))
    dp.add_handler(CommandHandler('giurato', giurato_command))
    dp.add_handler(CallbackQueryHandler(ctsCommandHandler))
    dp.add_handler(CommandHandler('tortadimele', torta_command))
    dp.add_handler(CommandHandler('comune', comune_command))
    dp.add_handler(CommandHandler('covid', covid_command))
    dp.add_handler(CommandHandler('update', echo_sentence))
    dp.add_handler(CommandHandler('fibonacci', fibonacci_command))
    dp.add_handler(CommandHandler('centocentocento', centocentocento_command))
    dp.add_handler(CommandHandler('help', help_command))

    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, handle_message))
    dp.add_handler(MessageHandler(Filters.sticker, handle_sticker))

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
