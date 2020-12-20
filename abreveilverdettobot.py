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

import logging, json, yaml, os, time, utils.emoji as emojis, utils.commandutils as utils, datetime
import base64
from cairosvg import svg2png

from urllib.request import Request, urlopen, urlretrieve
from urllib.error import URLError, HTTPError

from random import randrange
from telegram import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, ConversationHandler, PicklePersistence

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)

def buildPath(relative_path):
    return os.path.join(os.path.dirname(__file__), relative_path)

def directorySize(dir):
    return len([name for name in os.listdir(dir) if os.path.isfile(os.path.join(dir, name))])

def loadJSON(relative_path):
    return json.load(open(buildPath('{}.json'.format(relative_path))))

def loadYAML(relative_path):
    return yaml.load(open(buildPath('{}.yaml'.format(relative_path))), Loader=yaml.Loader)

config = loadYAML('conf/config')

os.environ['TZ'] = config['bot']['localTimezone']
time.tzset()

SALUTI, CTS, DPCM, CONTE, BIMBE, COMUNE, COVID, GIURATO, TORTADIMELE, FIBONACCI, CENTOCENTOCENTO, GHESBORO, POKEMON, COUNTRY, COCKTAIL, SANTI = range(16)

BRISCOLA = 'Come fa 15+18 non fa 36 dio te maledica te do \'n sciafon che te copo d** ***'

NEW_VALUE_KEY = "new_value"
MAX_VALUE_KEY = "max_value"
USER_KEY = "user"
DATE_KEY = "date"
VALUE_KEY = "value"
RUN_NUMBER_KEY = "run_number"
NUMBER_OF_RUNS_KEY = "number_of_runs"
IVA_100_100_100 = "Iva_Zanicchi_CAGA_in_diretta.gif"

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
            InlineKeyboardButton(u'\U0001F30D' + " nazione", callback_data=str(COUNTRY)),
        ],        
        [
            InlineKeyboardButton(u'\U0001F378' + " cocktail", callback_data=str(COCKTAIL)),
            InlineKeyboardButton(u'\U0001F47C' + " santi", callback_data=str(SANTI)),
        ]
       
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Seleziona comando:', reply_markup=reply_markup)
    return 0


def saluti(update, context):
    """Send a message when the command /saluti is issued."""
    query = update.callback_query
    query.answer()
    
    saluti = loadJSON('data/saluti')
    numSalutiConte = len(saluti)
    randomIndex = randrange(numSalutiConte)
    user = update.effective_user
    logger.info('User {} chose saluti.'.format(user.username))
    
    query.edit_message_text(
        text=saluti[randomIndex].format(utils.greetings(time, user.first_name))
    )
    return ConversationHandler.END


def torta_command(update, context):
    query = update.callback_query
    query.answer()
    
    index = randrange(directorySize("media/tortamele"))
    
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
    
    frasi_conte = loadJSON('data/conte')
    index = randrange(directorySize("media/conte"))
    numFrasiConte = len(frasi_conte)
    randomIndexCaption = randrange(numFrasiConte)
    
    query.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    query.bot.send_photo(
        chat_id=update.effective_chat.id, 
        photo=open(buildPath("media/conte/{}.jpg".format(index)), 'rb'),
        caption=frasi_conte[randomIndexCaption]
    )
    return ConversationHandler.END


def bimbe_command(update, context):
    query = update.callback_query
    query.answer()
    
    love_dict = emojis.love
    loveEmojis = list(love_dict.values())
    sizeLove = len(loveEmojis)
    randomIndexImage = randrange(directorySize("media/bimbe"))
    
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
    
    dpcmList = loadJSON('data/dpcm')
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
    
    giurato_list = loadJSON('data/giurato')
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
    
    message = ['Ultimo aggiornamento: {} alle {}'.format(latestDate.strftime("%d/%m/%Y"), latestDate.strftime("%H:%M"))]
    message.append('{} {}  <i>{}</i>'.format(covid_dict['biohazard'], covid_dict['thermoFace'], utils.get_variation(nuoviPositivi)))
    message.append('{} {}  <i>{:,.0f}</i> ({})'.format(covid_dict['hospital'], covid_dict['maskFace'], COVID[-1]['totale_ospedalizzati'], utils.get_variation(varOspedalizzati)))
    message.append('{} {}  <i>{:,.0f}</i> ({})'.format(covid_dict['hospital'], covid_dict['bed'], COVID[-1]['terapia_intensiva'], utils.get_variation(varTerapieI)))
    message.append('{} {}  <i>{:,.0f}</i> ({})'.format(covid_dict['house'], covid_dict['thermoFace'], COVID[-1]['isolamento_domiciliare'], utils.get_variation(varIsolamento)))
    message.append('{} {}  <i>{:,.0f}</i> ({})'.format(covid_dict['latinCross'], covid_dict['angel'], COVID[-1]['deceduti'], utils.get_variation(varDeceduti)))
    message.append('{} {}  <i>{:,.0f}</i> ({})'.format(covid_dict['nose'], covid_dict['testTube'], COVID[-1]['tamponi'], utils.get_variation(varTamponi)))
    message.append('{} / {} {:.3}%'.format(covid_dict['biohazard'], covid_dict['testTube'], percPosTamp))
    """
    message += hospital + maskFace + ' ' + varTerapieI + '\n'
    message += house + ' ' + varIsolamento + '\n'
    """
    query.edit_message_text(
        text="\n".join(message), 
        parse_mode=ParseMode.HTML
    )
    return ConversationHandler.END


def comune_command(update, context):
    query = update.callback_query
    query.answer()
    
    zone_dict = emojis.zone_color
    comuni = json.loads(urlopen(Request(config['comuni']['url'])).read().decode())
    comune = comuni[randrange(len(comuni))]
    urlWeather = config['openweathermap']['url'].format(comune['cap'][0], config['openweathermap']['token'])
    regions_ita = loadJSON('data/regions_ita')
    covid_severity_color = utils.get_severity_color(comune, regions_ita)
    
    message = ['{1} <b>{0}</b> {1}'.format(comune['nome'], zone_dict.get(covid_severity_color) if covid_severity_color is not None else '')]
    message.append('{} {} ({})'.format(comune['cap'][0], comune['provincia']['nome'], comune['sigla']))
    message.append('<i>{:,.0f}</i> abitanti'.format(int(comune['popolazione'])))

    try:
        weather = json.loads(urlopen(Request(urlWeather)).read().decode())
        
        message.append('<b>{1}</b> °C - {0}'.format(weather['weather'][0]['description'].capitalize(),
            '%.1f' % weather['main']['temp']))
        
        query.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id
        )
        query.bot.send_photo(
            chat_id=update.effective_chat.id, 
            photo=config['openweathermap']['icon'].format(weather['weather'][0]['icon']),
            caption="\n".join(message), 
            parse_mode=ParseMode.HTML
        )        
    except:    
        query.edit_message_text(
            text="\n".join(message), 
            parse_mode=ParseMode.HTML
        )
        
    return ConversationHandler.END


def country_command(update, context):
    query = update.callback_query
    query.answer()
    
    request_countries = Request(config['countries']['url'])
    countries = json.loads(urlopen(request_countries).read().decode())
    index_country = randrange(len(countries))
    
    country = countries[index_country]
    country_code = country["alpha3Code"].lower()  
      
    flag_filename = "{}.png".format(country_code)    
    flag_path = buildPath("media/flags/{}".format(flag_filename))
    
    svg2png(url=country["flag"], write_to=flag_path)
    
    message = ["<b>{}</b>".format(build_country_name(country))]
    message.append("Capitale: {}".format(country["capital"]))
    message.append("Paese in {}".format(get_country_region(country)))
    message.append("Popolazione: <i>{:,.0f}</i>".format(country["population"]))
    message.append("Area: {:,.0f} km²".format(country["area"]))
    if country["gini"] is not None:
        message.append("Coefficiente Gini: <b>{}</b>".format(country["gini"]))
    message.append("Moneta: {}".format(", ".join(map(lambda x : "{} ({})".format(x["name"], x["code"]), country["currencies"]))))
    message.append("Lingua: {}".format(", ".join(map(lambda x : x["name"], country["languages"]))))
    message.append("Fuso orario: <i>{}</i>".format(", ".join(country["timezones"])))
    if (len(country["borders"]) > 0): 
        message.append("Confini: {}".format(find_borders(countries, country["borders"])))
    
    query.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    query.bot.send_photo(
        chat_id=update.effective_chat.id, 
        photo=open(flag_path, 'rb'),
        caption="\n".join(message), 
        parse_mode=ParseMode.HTML
    )
    
    return ConversationHandler.END


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

def centocentocento_generate_new_value():
    return 5 + randrange(0, 100, 5)

def centocentocento_command(update, context):
    query = update.callback_query
    query.answer()
    
    new_value = centocentocento_generate_new_value()
    run_number = 1

    if new_value == 100:
        return centocentocento_printresult(context, update.effective_user, query, new_value, run_number) #by definition, there is nothing better than 100, so stop with this run

    #otherwise, ask for another run or not
    context.user_data[NEW_VALUE_KEY] = new_value
    context.user_data[RUN_NUMBER_KEY] = run_number
    keyboard = [
        [
            InlineKeyboardButton("No", callback_data="No"),
            InlineKeyboardButton("Yes", callback_data="Yes"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message_lines = ["".join([emojis.numbers.get(n) for n in str(new_value)])]
    message_lines += ["Another run?"]
    query.edit_message_text("\n".join(message_lines), reply_markup=reply_markup)
    return 2

def centocentocento_anotherrun(update, context):
    query = update.callback_query
    query.answer()

    new_value = context.user_data.pop(NEW_VALUE_KEY)
    run_number = context.user_data.pop(RUN_NUMBER_KEY)
    if query.data == "Yes":
        new_value += centocentocento_generate_new_value()
        run_number += 1
    
    return centocentocento_printresult(update, context, update.effective_user, query, new_value, run_number)

def is_best(value, run_number, current_max_detail, reference_date):
    if value > 100:
        return False
    if current_max_detail is None:
        return True
    if current_max_detail[DATE_KEY] > reference_date:
        return False
    if current_max_detail[DATE_KEY] == reference_date:
        if current_max_detail[VALUE_KEY] > value:
            return False
        elif current_max_detail[VALUE_KEY] == value and current_max_detail[NUMBER_OF_RUNS_KEY] < run_number:
            return False
    return True

def centocentocento_printresult(update, context, user, query, value, run_number):
    message_lines = ["".join([emojis.numbers.get(n) for n in str(value)])]
    message_lines += centocentocento_result_emoji(value)

    chat_data = context.dispatcher.chat_data
    current_max_detail = chat_data[MAX_VALUE_KEY] if MAX_VALUE_KEY in chat_data else None
    today = datetime.date.today()
    if is_best(value, run_number, current_max_detail, today):
        chat_data[MAX_VALUE_KEY] = {DATE_KEY: today, USER_KEY: user.username, VALUE_KEY: value, NUMBER_OF_RUNS_KEY: run_number}
        message_lines += "This is the best score for today!"
    else:
        message_lines += "Today {} has already done the best score (value: {} - runs: {})".format(current_max_detail[USER_KEY], current_max_detail[VALUE_KEY], current_max_detail[NUMBER_OF_RUNS_KEY])

    if value == 100:
        query.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id
        )
        query.bot.send_photo(
            chat_id=update.effective_chat.id, 
            photo=open(buildPath("media/centocentocento/{}".format(IVA_100_100_100)), 'rb'),
            caption=message_lines, 
            parse_mode=ParseMode.HTML
        )
    else:
        query.edit_message_text(
            text=" ".join(message_lines), 
            parse_mode=ParseMode.HTML
        )

    return ConversationHandler.END

def centocentocento_result_emoji(value):
    if value < 100:
        return emojis.centocentocentoresult["below"]
    elif value == 100:
        return emojis.centocentocentoresult["win"]
    return emojis.centocentocentoresult["above"]

def ghesboro_command(update, context):
    """Send a message when the command /ghesboro is issued."""
    query = update.callback_query
    query.answer()
    
    veneto_list = loadJSON('data/ghesboro')
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
    
    heart = emojis.love.get('redHeart')
    pokemonType = emojis.pkmn_type
    logger.info('[POKEMON] - REQUEST URL : {}'.format(config['pokemon']['url']))
    reqPokemon = Request(config['pokemon']['url'])
    pokedex = json.loads(urlopen(reqPokemon).read().decode())

    index_pokemon = randrange(152)
    logger.info('[POKEMON] - index_pokemon : {}'.format(index_pokemon))
    
    if(index_pokemon):
        pokemon = pokedex['pokemon'][str(index_pokemon)]
        logger.info('[POKEMON] - pokemon : {}'.format(pokemon))
        message = '#{} - <b>{}</b>\n'.format(index_pokemon, pokemon['N'].upper())
        types = [pokemonType.get(current_type['n']) for current_type in pokemon['T'][:2]]
        message += "Type(s): {}".format("".join(types))
        image = config['pokemon']['photo'].format("{:03d}".format(index_pokemon))
    else:
        message = '#0 - <b>CESARA BUONAMICI</b>\n'
        message += "Type(s): {0}{0}".format(heart)
        image = open(buildPath("media/others/cesara.jpg"), 'rb')

    query.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    query.bot.send_photo(
        chat_id=update.effective_chat.id, 
        photo=image,
        caption=message, 
        parse_mode=ParseMode.HTML
    ) 
    
    return ConversationHandler.END

def cocktail_command(update, context):
    """Send a message when the command /cocktail is issued."""
    query = update.callback_query
    query.answer()

    reqRecipes = Request(config['cocktail']['url'])
    recipes = json.loads(urlopen(reqRecipes).read().decode())
    index_drink = randrange(len(recipes))
    drink = recipes[index_drink]
    message = '<b>\"{}\"</b>\n'.format(drink['name'].upper())
    message += 'Tipo: <i>{}</i>\n'.format(drink['category'])
    message += 'Bicchiere: <i>{}</i>\n'.format(drink['glass'])
    message += 'Ingredienti:\n'
    for ingredient in drink['ingredients']:
        message += '∘ {} {} di {}\n'.format(ingredient['amount'],ingredient['unit'],ingredient['ingredient'])

    query.edit_message_text(
        text=message, 
        parse_mode=ParseMode.HTML
    )

    return ConversationHandler.END

def santi_command(update, context):
    """Send a message when the command /santi is issued."""
    query = update.callback_query
    query.answer()

    santi_list = loadJSON('data/santi')
    frasi_list = loadJSON('data/santi_frasi')
    index_santi = randrange(len(santi_list))
    index_frasi = randrange(len(frasi_list))
    santo = santi_list[index_santi]
    message = '<b>{}</b>\n'.format(santo['name'].upper())
    message += '<i>{}</i>\n'.format(santo['func'])
    message += '{}\n'.format(frasi_list[index_frasi])

    query.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    query.bot.send_photo(
        chat_id=update.effective_chat.id, 
        photo=open(buildPath("media/santi/{}.jpg".format(santo['photo'])), 'rb'),
        caption=message, 
        parse_mode=ParseMode.HTML
    ) 
    
    return ConversationHandler.END    

def end(update, context):
    """Returns `ConversationHandler.END`, which tells the
    ConversationHandler that the conversation is over"""
    query = update.callback_query
    query.answer()
    query.edit_message_text(text="See you next time!")
    return ConversationHandler.END

def alarm(context):
    """Send the alarm message."""
    job = context.job
    context.bot.send_message(job.context, text='A breve il verdetto')

def remove_job_if_exists(name, context):
    """Remove job with given name. Returns whether job was removed."""
    current_jobs = context.job_queue.get_jobs_by_name(name)
    if not current_jobs:
        return False
    for job in current_jobs:
        job.schedule_removal()
    return True

def set_timer(update, context):
    """Add a job to the queue."""
    chat_id = update.message.chat_id
    
    job_removed = remove_job_if_exists(str(chat_id), context)
    t = datetime.time(16, 30, 00, 000000)
    context.job_queue.run_daily(alarm, t, days=tuple(range(7)), context=chat_id, name=str(chat_id))

    text = 'Timer successfully set!'
    if job_removed:
        text += ' Old one was removed.'
    update.message.reply_text(text)
    
def unset(update, context):
    """Remove the job if the user changed their mind."""
    chat_id = update.message.chat_id
    job_removed = remove_job_if_exists(str(chat_id), context)
    text = 'Timer successfully cancelled!' if job_removed else 'You have no active timer.'
    update.message.reply_text(text)


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

def get_country_region(country):
    region = country["region"]
    subregion = country["subregion"]
    if (subregion != ""):
        region += ", {}".format(subregion)
    return region

def build_country_name(country):
    country_name = country["translations"]["it"]
    
    if country_name is not None:
        return country_name
    else:
        return country["name"]

def buildCtsMessage(qty):
    ctsList = loadJSON('data/cts_list')
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

    # Create the Updater and pass it your bot's token.
    persistence = PicklePersistence(filename='conversationbot')

    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # Make sure to set use_context=True to use the new context based callbacks
    # Post version 12 this will no longer be necessary
    updater = Updater(token, use_context=True, persistence = persistence)

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
                CallbackQueryHandler(pokemon_command, pattern='^' + str(POKEMON) + '$'),
                CallbackQueryHandler(country_command, pattern='^' + str(COUNTRY) + '$'),
                CallbackQueryHandler(cocktail_command, pattern='^' + str(COCKTAIL) + '$'),
                CallbackQueryHandler(santi_command, pattern='^' + str(SANTI) + '$')
            ],
            1: [
                CallbackQueryHandler(ctsCommandHandler, pattern='^(' + str(5) + '|' + str(10) + ')$')
            ]
            , 2: [
                CallbackQueryHandler(centocentocento_anotherrun, pattern='^(No|Yes)$')
            ]
        },
        fallbacks=[CallbackQueryHandler(end)],
        persistent=True, 
        name=config['bot']['handlerName']
    )

    dp.add_handler(conv_handler)
    
    dp.add_handler(CommandHandler("set", set_timer, pass_job_queue=True))
    dp.add_handler(CommandHandler("unset", unset))

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
