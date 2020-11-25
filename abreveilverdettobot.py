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

import logging, json, os, time, utils.emoji as emojis, utils.commandutils as utils, datetime
#from cairosvg import svg2png

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

def buildPath(relativePath):
    return os.path.join(os.path.dirname(__file__), relativePath)

config = json.load(open(buildPath('conf/appConfig.json')))
content = json.load(open(buildPath('conf/appContent.json')))

SALUTI, CTS, DPCM, CONTE, BIMBE, COMUNE, COVID, GIURATO, TORTADIMELE, FIBONACCI, CENTOCENTOCENTO, GHESBORO, POKEMON, COUNTRY = range(14)

HELP = '{} non verrai abbandonato a te stesso'
BRISCOLA = 'Come fa 15+18 non fa 36 dio te maledica te do \'n sciafon che te copo d** ***'
THE_SENTENCE = 'a breve il verdetto'


logger = logging.getLogger(__name__)


"""
START OF COMMANDS SECTION
"""


# Define a few command handlers. These usually take the two arguments update and
# context. Error handlers also receive the raised TelegramError object in error.


def start_command(update, context):
    """Send a message when the command /start is issued."""
    user = update.message.from_user
    logger.info("User %s started the conversation.", user.first_name)
    
    keyboard = [
        [
            InlineKeyboardButton(u'\U0001F44B' + " saluti", callback_data=str(SALUTI)),
            InlineKeyboardButton(u'\U0001f52c' + " cts", callback_data=str(CTS)),
            InlineKeyboardButton(u'\U0001F4DC' + " dpcm", callback_data=str(DPCM)),
        ],
        [
            InlineKeyboardButton(u'\U0001F647' + " conte", callback_data=str(CONTE)),
            InlineKeyboardButton(u'\U0001F63b' + " bimbe", callback_data=str(BIMBE)),
            InlineKeyboardButton(u'\U0001F3D9' + " comune", callback_data=str(COMUNE))
        ],
        [
            InlineKeyboardButton(u'\U0001F9EA' + " covid", callback_data=str(COVID)),
            InlineKeyboardButton(u'\U0001F926' + " giurato", callback_data=str(GIURATO)),
            InlineKeyboardButton(u'\U0001F967' + " torta", callback_data=str(TORTADIMELE))
        ],
        [
            InlineKeyboardButton(u'\U0001F522' + " fibonacci", callback_data=str(FIBONACCI)),
            InlineKeyboardButton('{0} {0} {0}'.format(u'\U0001F4AF'), callback_data=str(CENTOCENTOCENTO)),
            InlineKeyboardButton(u'\U0001F981' + " ghesboro", callback_data=str(GHESBORO)),
        ],        
        [
            InlineKeyboardButton(u'\U0001F995' + " pokemon", callback_data=str(POKEMON)),            
            InlineKeyboardButton(u'\U0001F30D' + " nazione", callback_data=str(COUNTRY))
        ]
       
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Seleziona comando:', reply_markup=reply_markup)
    return 0


def saluti(update, context):
    """Send a message when the command /saluti is issued."""
    query = update.callback_query
    query.answer()
    
    numSalutiConte = len(content['greetings'])
    randomIndex = randrange(numSalutiConte)
    user = update.effective_user
    logger.info('User {} chose saluti.'.format(user.username))
    
    query.edit_message_text(
        text=content['greetings'][randomIndex].format(utils.greetings(time, user.first_name))
    )
    return ConversationHandler.END


def torta_command(update, context):
    query = update.callback_query
    query.answer()
    
    index = randrange(6)
    
    query.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    query.bot.send_photo(
        chat_id=update.effective_chat.id, 
        photo=open(buildPath("media/tortamele/{}.jpg".format(index)), 'rb')
    )
    return ConversationHandler.END


def conte_command(update, context):
    query = update.callback_query
    query.answer()
    
    index = randrange(12)
    numFrasiConte = len(content['sentences']['conte'])
    randomIndexCaption = randrange(numFrasiConte)
    
    query.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    query.bot.send_photo(
        chat_id=update.effective_chat.id, 
        photo=open(buildPath("media/conte/{}.jpg".format(index)), 'rb'),
        caption=content['sentences']['conte'][randomIndexCaption]
    )
    return ConversationHandler.END


def bimbe_command(update, context):
    query = update.callback_query
    query.answer()
    
    love_dict = emojis.love
    loveEmojis = list(love_dict.values())
    sizeLove = len(loveEmojis)
    randomIndexImage = randrange(20)
    
    query.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    query.bot.send_photo(
        chat_id=update.effective_chat.id, 
        photo=open(buildPath("media/bimbe/{}.jpg".format(randomIndexImage)), 'rb'),
        caption=loveEmojis[randrange(sizeLove)] + loveEmojis[randrange(sizeLove)] + loveEmojis[randrange(sizeLove)]
    )
    return ConversationHandler.END


def cts_command(update, context):
    """Send a message when the command /cts is issued."""
    query = update.callback_query
    query.answer()
    
    keyboard = [
        [
            InlineKeyboardButton("5", callback_data=str(5)),
            InlineKeyboardButton("10", callback_data=str(10)),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text('Quanti membri desideri?', reply_markup=reply_markup)
    return 1


def dpcm_command(update, context):
    """Send a message when the command /dpcm is issued."""
    query = update.callback_query
    query.answer()
    
    dpcmList = content['DPCM']
    randIndex = randrange(len(dpcmList))
    
    query.edit_message_text(
        text='<i>\"{}\"</i>'.format(dpcmList[randIndex]), 
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


def giurato_command(update, context):
    """Send a message when the command /giurato is issued."""
    query = update.callback_query
    query.answer()
    
    giurato_list = content['sentences']['giurato']
    randIndex = randrange(len(giurato_list))
    
    query.edit_message_text(
        text='<i>\"{}\"</i>'.format(giurato_list[randIndex]), 
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


def covid_command(update, context):
    query = update.callback_query
    query.answer()
    
    covid_dict = emojis.covid
    reqCovid = Request(config['covid']['url'])
    COVID = json.loads(urlopen(reqCovid).read().decode())
    latestDate = datetime.datetime.strptime(COVID[-1]['data'], '%Y-%m-%dT%H:%M:%S')
    
    nuoviPositivi = COVID[-1]['nuovi_positivi']
    varOspedalizzati = COVID[-1]['totale_ospedalizzati'] - COVID[-2]['totale_ospedalizzati']
    varTerapieI = COVID[-1]['terapia_intensiva'] - COVID[-2]['terapia_intensiva']
    varIsolamento = COVID[-1]['isolamento_domiciliare'] - COVID[-2]['isolamento_domiciliare']
    varDeceduti = COVID[-1]['deceduti'] - COVID[-2]['deceduti']
    varTamponi = COVID[-1]['tamponi'] - COVID[-2]['tamponi']
    percPosTamp = 100 * COVID[-1]['nuovi_positivi'] / varTamponi
    
    message = 'Ultimo aggiornamento: {} alle {}\n'.format(latestDate.strftime("%d/%m/%Y"), latestDate.strftime("%H:%M"))
    message += '{}{} {}\n'.format(covid_dict['biohazard'], covid_dict['thermoFace'], utils.get_variation(nuoviPositivi))
    message += '{}{} {} ({})\n'.format(covid_dict['hospital'], covid_dict['maskFace'], COVID[-1]['totale_ospedalizzati'], utils.get_variation(varOspedalizzati))
    message += '{}{} {} ({})\n'.format(covid_dict['hospital'], covid_dict['bed'], COVID[-1]['terapia_intensiva'], utils.get_variation(varTerapieI))
    message += '{}{} {} ({})\n'.format(covid_dict['house'], covid_dict['thermoFace'], COVID[-1]['isolamento_domiciliare'], utils.get_variation(varIsolamento))
    message += '{}{} {} ({})\n'.format(covid_dict['latinCross'], covid_dict['angel'], COVID[-1]['deceduti'], utils.get_variation(varDeceduti))
    message += '{}{} {} ({})\n'.format(covid_dict['nose'], covid_dict['testTube'], COVID[-1]['tamponi'], utils.get_variation(varTamponi))
    message += '{}\{} {:.3}%'.format(covid_dict['biohazard'], covid_dict['testTube'], percPosTamp)
    """
    message += hospital + maskFace + ' ' + varTerapieI + '\n'
    message += house + ' ' + varIsolamento + '\n'
    """
    query.edit_message_text(
        text=message, 
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


def comune_command(update, context):
    query = update.callback_query
    query.answer()
    
    zone_dict = emojis.zone_color
    request_comuni = Request(config['comuni']['url'])
    comuni = json.loads(urlopen(request_comuni).read().decode())
    index_comune = randrange(len(comuni))
    comune = comuni[index_comune]
    urlWeather = config['openweathermap']['url'].format(comune['cap'][0], config['openweathermap']['token'])
    reqMeteo = Request(urlWeather)
    covid_severity_color = utils.get_severity_color(comune, content['ItalianRegions'])

    try:
        weather = json.loads(urlopen(reqMeteo).read().decode())
        message = '{1} <b>{0}</b> {1}\n'.format(comune['nome'], zone_dict.get(covid_severity_color) if covid_severity_color is not None else '')
        message += '{} {} ({})\n'.format(comune['cap'][0], comune['provincia']['nome'], comune['sigla'])
        message += '<i>{:,.0f}</i> abitanti\n'.format(int(comune['popolazione']))
        message += '<b>{1}</b> °C - {0}'.format(weather['weather'][0]['description'].capitalize(),
            '%.1f' % weather['main']['temp'])
        
        query.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id
        )
        query.bot.send_photo(
            chat_id=update.effective_chat.id, 
            photo=config['openweathermap']['icon'].format(weather['weather'][0]['icon']),
            caption=message, 
            parse_mode=ParseMode.HTML
        )        
    except:
        message = '{1} <b>{0}</b> {1}\n'.format(comune['nome'], zone_dict.get(covid_severity_color) if covid_severity_color is not None else '')
        message += '{} {} ({})\n'.format(comune['cap'][0], comune['provincia']['nome'], comune['sigla'])
        message += '<i>{:,.0f}</i> abitanti\n'.format(int(comune['popolazione']))
    
        query.edit_message_text(
            text=message, 
            parse_mode=ParseMode.HTML
        )
        
    return ConversationHandler.END


""" def country_command(update, context):
    query = update.callback_query
    query.answer()
    
    request_countries = Request(config['countries']['url'])
    countries = json.loads(urlopen(request_countries).read().decode())
    index_country = randrange(len(countries))
    
    country = countries[index_country]
    country_code = country["alpha3Code"].lower()    
    flag_filename = "{}.png".format(country_code)
    flag_path = buildPath("media/flags/{}".format(flag_filename))
    
    if find(flag_filename) == "NO_RESULT":    
        svg2png(
            url=country["flag"], 
            write_to=flag_path)
    
    query.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    query.bot.send_photo(
        chat_id=update.effective_chat.id, 
        photo=open(flag_path, 'rb'),
        caption=build_country_message(country, countries), 
        parse_mode=ParseMode.HTML
    ) 
    
    return ConversationHandler.END """


def fibonacci_command(update, context):
    query = update.callback_query
    query.answer()
    
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
    
    query.edit_message_text(
        text="\n".join(response), 
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


def centocentocento_command(update, context):
    query = update.callback_query
    query.answer()
    
    numbers_dict = emojis.numbers
    value = 5 + randrange(0, 100, 5)
    new_value = []
    
    for n in str(value):
        new_value.append(numbers_dict.get(n))
    
    query.edit_message_text(
        text=" ".join(new_value), 
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END

def ghesboro_command(update, context):
    """Send a message when the command /ghesboro is issued."""
    query = update.callback_query
    query.answer()
    
    veneto_list = content['sentences']['veneto']
    randIndex = randrange(len(veneto_list))
    
    query.edit_message_text(
        text='<i>\"{}\"</i>'.format(veneto_list[randIndex]), 
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END

def pokemon_command(update, context):
    """Send a message when the command /pokemon is issued."""
    query = update.callback_query
    query.answer()
    
    index_str = ''
    index_pokemon = randrange(150)
    if (index_pokemon < 100):
        index_str = '0{}'.format(index_pokemon)
    else:
        index_str = '{}'.format(index_pokemon)
    reqPokemon = Request(config['pokemon']['url'])
    Pokedex = json.loads(urlopen(reqPokemon).read().decode())
    message = '#{} - {}\n'.format(index_pokemon, Pokedex['pokemon'][index_pokemon]['N'])

    query.edit_message_text(
        text='<i>{}</i>'.format(message),
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END

def help_command(update, context):
    """Send a message when the command /help is issued."""
    user = update.message.from_user
    update.message.reply_text(HELP.format(user.first_name))
    

def end(update, context):
    """Returns `ConversationHandler.END`, which tells the
    ConversationHandler that the conversation is over"""
    query = update.callback_query
    query.answer()
    query.edit_message_text(text="See you next time!")
    return ConversationHandler.END


#================================================================================

"""
START OF UTILITY SECTION
"""

def find(name):
    result = "NO_RESULT"
    for root, dirs, files in os.walk(buildPath("media/flags")):
        if name in files:
            result = os.path.join(root, name)
    return result

def find_borders(countries, codes):
    name_list = []
    for code in codes:
        result = next((country for country in countries if country['alpha3Code'] == code), None)
        if result is not None:
            name_list.append(build_country_name(result))
    return ', '.join(name_list)

def build_country_name(country):
    country_name = ""
    try:
        country_name = country["translations"]["it"]
    except:
        country_name = country["name"]
        
    return country_name

def build_country_message(country, countries):
    message = "<b>{}</b>\n".format(build_country_name(country))
    message += "Capitale: {}\n".format(country["capital"])
    message += "Continente: {}\n".format(country["region"])
    message += "Popolazione: {}\n".format(country["population"])
    message += "Moneta: {}\n".format(country["currencies"][0]["symbol"])
    message += "Lingua: {}\n".format(country["languages"][0]["name"])
    message += "Confina con: {}".format(find_borders(countries, country["borders"]))
    
    return message

def buildCtsMessage(qty):
    ctsList = content['CTS']
    ctsSize = len(ctsList)
    message = '<b>Comitato Tecnico-Scientifico</b>\n'
    indexlist = utils.get_index_list(qty, ctsSize)
    for index in indexlist:
        message += '∘ {}\n'.format(ctsList[index])
    return message

def ctsCommandHandler(update, context):
    query = update.callback_query
    query.answer()
    message = buildCtsMessage(query.data)
    query.edit_message_text(text=message, parse_mode=ParseMode.HTML)
    return ConversationHandler.END    

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

        
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            0: [
                CallbackQueryHandler(saluti, pattern='^' + str(SALUTI) + '$'),
                CallbackQueryHandler(cts_command, pattern='^' + str(CTS) + '$'),
                CallbackQueryHandler(dpcm_command, pattern='^' + str(DPCM) + '$'),
                CallbackQueryHandler(conte_command, pattern='^' + str(CONTE) + '$'),
                CallbackQueryHandler(bimbe_command, pattern='^' + str(BIMBE) + '$'),
                CallbackQueryHandler(comune_command, pattern='^' + str(COMUNE) + '$'),
                CallbackQueryHandler(covid_command, pattern='^' + str(COVID) + '$'),
                CallbackQueryHandler(giurato_command, pattern='^' + str(GIURATO) + '$'),
                CallbackQueryHandler(torta_command, pattern='^' + str(TORTADIMELE) + '$'),
                CallbackQueryHandler(fibonacci_command, pattern='^' + str(FIBONACCI) + '$'),
                CallbackQueryHandler(centocentocento_command, pattern='^' + str(CENTOCENTOCENTO) + '$'),
                CallbackQueryHandler(ghesboro_command, pattern='^' + str(GHESBORO) + '$'),
                CallbackQueryHandler(pokemon_command, pattern='^' + str(POKEMON) + '$')
            ],
            1: [
                CallbackQueryHandler(ctsCommandHandler, pattern='^(' + str(5) + '|' + str(10) + ')$')
            ]
        },
        fallbacks=[CallbackQueryHandler(end)],
    )

    dp.add_handler(conv_handler)

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
