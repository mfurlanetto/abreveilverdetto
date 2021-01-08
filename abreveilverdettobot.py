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

import psycopg2 #DB communication library

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
MR_BEAN_FUCK_YOU = "Mr_Bean_Middle_Finger.gif"

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
    
    user = update.effective_user
    logger.debug('User {} chose saluti.'.format(user.username))
    
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
            InlineKeyboardButton("5", callback_data="5"),
            InlineKeyboardButton("10", callback_data="10"),
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
    
    user = update.effective_user
    logger.error('User {} chose saluti.'.format(user.username))
    
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
    
    message = ['{1} *{0}* {1}\n'.format(" ".join(comune['nome'].upper()), zone_dict.get(covid_severity_color) if covid_severity_color is not None else '')]
    message.append('```')
    message.append('{} {} ({})'.format(comune['cap'][0], comune['provincia']['nome'], comune['sigla']))
    message.append('{:,.0f} abitanti'.format(int(comune['popolazione'])))

    try:
        weather = json.loads(urlopen(Request(urlWeather)).read().decode())
        
        message.append('{1} °C - {0}'.format(weather['weather'][0]['description'].capitalize(),
            '%.1f' % weather['main']['temp']))        
        message.append('```')
        
        query.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id
        )
        query.bot.send_photo(
            chat_id=update.effective_chat.id, 
            photo=config['openweathermap']['icon'].format(weather['weather'][0]['icon']),
            caption="\n".join(message), 
            parse_mode=ParseMode.MARKDOWN_V2
        )        
    except:        
        message.append('```')
        query.edit_message_text(
            text="\n".join(message), 
            parse_mode=ParseMode.MARKDOWN_V2
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
    
    message = ["*{}*\n".format(" ".join(build_country_name(country).upper()))]
    message.append('```')
    message.append("Capitale:       {}".format(country["capital"]))
    message.append("Paese in:       {}".format(get_country_region(country)))
    message.append("Popolazione:    {:,.0f}".format(country["population"]))
    message.append("Area:           {:,.0f} km²".format(country["area"]))
    if country["gini"]:
        message.append("Gini:           {}".format(country["gini"]))
    message.append("Moneta:         {}".format("\n                ".join(map(lambda x : "{} ({})".format(x["name"], x["code"]), country["currencies"]))))
    message.append("Lingua:         {}".format("\n                ".join(map(lambda x : x["name"], country["languages"]))))
    message.append("Fuso orario:    {}".format("\n                ".join(country["timezones"])))
    if country["borders"]: 
        message.append("Confini:        {}".format(find_borders(countries, country["borders"])))
    message.append('```')
    
    query.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    query.bot.send_photo(
        chat_id=update.effective_chat.id, 
        photo=open(flag_path, 'rb'),
        caption="\n".join(message), 
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    return ConversationHandler.END

def fibonacci_start(update, context):
    query = update.callback_query
    query.answer()

    query.edit_message_text(
        text="Maximum number of iterations?"
        , parse_mode=ParseMode.MARKDOWN_V2
    )

    return 3

def fibonacci_command(update, context):   
    logger.info("FIBONACCI update.message.text = {}".format(update.message.text))
    response = []
    error = False
    try:
        maxNumberOfIterations = int(update.message.text)
    except (IndexError):    
        response.append("maxNumberOfIterations parameter not passed")
        error = True
    except (ValueError):
        response.append("Exception converting maxNumberOfIterations parameter")
        response.append("Received value is {}".format(update.message.text))
        error = True
    except:
        response.append("Generic exception while reading maxNumberOfIterations parameter")
        error = True
    if (error == True):
        maxNumberOfIterations = 10
        response.append("Default will be {}".format(maxNumberOfIterations))
    elif (maxNumberOfIterations > 10):
        maxNumberOfIterations = 10
        response.append("The maximum number of iterations will be set to {}, that is the maximum allowed".format(maxNumberOfIterations))
    logger.info("FIBONACCI maxNumberOfIterations after the check = {}".format(maxNumberOfIterations))

    numberOfIterations = randrange(maxNumberOfIterations)
    sequence = [1, 1]
    if (numberOfIterations <= len(sequence)):
        sequence = sequence[:numberOfIterations]
    else:
        for _ in range(numberOfIterations):
            sequence.append(sequence[-1] + sequence[-2])
    logger.info("FIBONACCI sequence = {}".format(sequence))
    response.append(', '.join(map(str, sequence)))
    
    logger.info("FIBONACCI response = {}".format(response))
    update.message.reply_text(
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
        return centocentocento_printresult(update, context, update.effective_user, query, new_value, run_number) #by definition, there is nothing better than 100, so stop with this run

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
    message_lines = ["{} {}".format("".join([emojis.numbers.get(n) for n in str(value)]), centocentocento_result_emoji(value))]
    chat_data = context.dispatcher.chat_data
    current_max_detail = chat_data[MAX_VALUE_KEY] if MAX_VALUE_KEY in chat_data else None
    today = datetime.date.today()
    if is_best(value, run_number, current_max_detail, today):
        chat_data[MAX_VALUE_KEY] = {DATE_KEY: today, USER_KEY: user.username, VALUE_KEY: value, NUMBER_OF_RUNS_KEY: run_number}
        message_lines.append("This is the best score for today\\!")
    else:
        message_lines.append("Today {} has already done the best score \\(value: {} \\- runs: {}\\)".format(current_max_detail[USER_KEY], current_max_detail[VALUE_KEY], current_max_detail[NUMBER_OF_RUNS_KEY]))

    if value == 100:
        today = datetime.datetime.today()
        DATABASE_URL = os.environ['DATABASE_URL']
        db_connection = psycopg2.connect(DATABASE_URL, sslmode='require')
        with db_connection.cursor() as cursor:
            cursor.execute("select won_match_counter from winnings where chat_id = %s and username = %s;", (update.effective_chat.id, user.username))
            record = cursor.fetchone()
            if record is None:
                won_match_counter = 1
                cursor.execute("insert into winnings(username, won_match_counter, last_win, chat_id) values (%s, %s, %s, %s);", (user.username, won_match_counter, today, update.effective_chat.id))
            else:
                won_match_counter = record[0] + 1
                #we increment in DB without passing the value calculated in the code. anyway, we expect them to always be the same
                cursor.execute("update winnings set won_match_counter = won_match_counter + 1, last_win = %s where chat_id = %s and username = %s;", (today, update.effective_chat.id, user.username))
            db_connection.commit()
            
            message_lines.append("You have won {} time{}".format(won_match_counter, "s" if won_match_counter > 1 else ""))

            cursor.execute("select username, won_match_counter from winnings where chat_id = %s order by won_match_counter desc, last_win;", (update.effective_chat.id,))
            top_scorer, max_won_match_counter = cursor.fetchone() #we are sure at least one record exists
            message_lines.append("{} the top scorer with {} win{}".format("You are" if top_scorer == user.username else "{} is".format(top_scorer), max_won_match_counter, "s" if max_won_match_counter > 1 else ""))
        db_connection.close()

        query.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id
        )
        query.bot.send_animation(
            chat_id=update.effective_chat.id, 
            animation=open(buildPath("media/centocentocento/{}".format(IVA_100_100_100)), 'rb'),
            caption= "\n".join(message_lines), 
            parse_mode=ParseMode.MARKDOWN_V2
        )
    elif run_number == 2 and (value == 95 or value == 105):
        query.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id
        )
        query.bot.send_animation(
            chat_id=update.effective_chat.id, 
            animation=open(buildPath("media/centocentocento/{}".format(MR_BEAN_FUCK_YOU)), 'rb'),
            caption= "\n".join(message_lines), 
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        query.edit_message_text(
            text="\n".join(message_lines), 
            parse_mode=ParseMode.MARKDOWN_V2
        )

    return ConversationHandler.END

def centocentocento_result_emoji(value):
    if value < 100:
        return emojis.centocentocentoresult["below"]
    elif value == 100:
        return emojis.centocentocentoresult["win"]
    return emojis.centocentocentoresult["above"]

def bravitutti_command(update, context):
    row_len = 20
    message = ["*HIGHSCORES*"]
    chat_id = update.effective_chat.id
    DATABASE_URL = os.environ['DATABASE_URL']
    db_connection = psycopg2.connect(DATABASE_URL, sslmode='require')
    message.append('```')
    with db_connection.cursor() as cursor:
        cursor.execute("select username, won_match_counter from winnings where chat_id = %s ORDER BY won_match_counter DESC", (update.effective_chat.id, ))
        records = cursor.fetchall()
        for record in records:
            spaces_len = row_len - (len(record[0]) -1 ) - (len(str(record[1])) - 1)
            spaces = ' ' * spaces_len
            message.append("{}:{}{}".format(record[0], spaces, record[1]))        
        message.append('```')
    db_connection.close()
    
    update.message.bot.send_message(
        chat_id=chat_id, 
        text="\n".join(message), 
        parse_mode=ParseMode.MARKDOWN_V2)

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
    #--------------------------------
    reqRecipes = Request(config['cocktail']['url2'])
    drinkList = json.loads(urlopen(reqRecipes).read().decode())
    drink = drinkList.drinks[0]
    message = '<b>\"{}\"</b>\n'.format(drink['strDrink'].upper())
    message += 'Tipo: <i>{}</i>\n'.format(drink['strCategory'])
    message += 'Bicchiere: <i>{}</i>\n'.format(drink['strGlass'])
    drinkImage = drink['strDrinkThumb']

    query.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=update.effective_message.message_id
    )
    query.bot.send_photo(
        chat_id=update.effective_chat.id, 
        photo=drinkImage,
        caption=message, 
        parse_mode=ParseMode.HTML
    ) 
    #--------------------------------
    """
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
    """
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
    return "\n                ".join(name_list)

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
                CallbackQueryHandler(fibonacci_start, pattern='^' + str(FIBONACCI) + '$'),
                CallbackQueryHandler(centocentocento_command, pattern='^' + str(CENTOCENTOCENTO) + '$'),
                CallbackQueryHandler(ghesboro_command, pattern='^' + str(GHESBORO) + '$'),
                CallbackQueryHandler(pokemon_command, pattern='^' + str(POKEMON) + '$'),
                CallbackQueryHandler(country_command, pattern='^' + str(COUNTRY) + '$'),
                CallbackQueryHandler(cocktail_command, pattern='^' + str(COCKTAIL) + '$'),
                CallbackQueryHandler(santi_command, pattern='^' + str(SANTI) + '$')
            ],
            1: [
                CallbackQueryHandler(ctsCommandHandler, pattern='^(5|10)$')
            ], 
            2: [
                CallbackQueryHandler(centocentocento_anotherrun, pattern='^(No|Yes)$')
            ]
            , 3: [
                MessageHandler(Filters.regex(r'^\d$'), fibonacci_command)
            ]
        },
        fallbacks=[CallbackQueryHandler(end)],
        persistent=True,
        allow_reentry =True, 
        name=config['bot']['handlerName']
    )

    dp.add_handler(conv_handler)
    
    dp.add_handler(CommandHandler("bravitutti", bravitutti_command))

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
