from random import randrange

def isMorning(hour):
    return hour >= 6 and hour < 13

def isAfternoon(hour):
    return hour >= 13 and hour < 17

def greetings(time, name):
    greetings = ''
    current_hour = time.strftime('%H')
    if isMorning(int(current_hour)):
        greetings = 'Buongiorno'
    elif isAfternoon(int(current_hour)):
        greetings = 'Buon pomeriggio'
    else:
        greetings = 'Buonasera'
    return '{} {}'.format(greetings, name)

def get_sign(value):
    return '+' if value > 0 else ''

def get_variation(variation):
    return '{}{}'.format(get_sign(variation), variation)

def get_severity_color(comune, regioni):
    regione_comune = comune['regione']['nome']
    regione_lista = next((region for region in regioni if region['name'] == comune['regione']['nome']), None)
    if regione_lista is not None:
        if regione_lista['name'] == 'Trentino-Alto Adige/Südtirol':
            provincia = next((prov for prov in regione_lista['name']['province'] if prov['name'] == comune['provincia']['nome']), None)
            return provincia['covid_severity_color'] if provincia is not None else None
        else:
            return regione_lista['covid_severity_color']
    else:
        return None
    
def get_index_list(how_many, size):
    i = 0
    list = []
    while i < int(how_many):
        index = randrange(size)
        if index not in list:
            list.append(index)
            i += 1
    return list
