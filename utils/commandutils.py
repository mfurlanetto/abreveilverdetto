def isMorning(hour):
    return hour >= 6 and hour < 13

def isAfternoon(hour):
    return hour >= 13 and hour < 17

def greetings(time, name):
    greetings = ''
    actualHour = time.strftime('%H')
    if isMorning(int(actualHour)):
        greetings = 'Buongiorno'
    elif isAfternoon(int(actualHour)):
        greetings = 'Buon pomeriggio'
    else:
        greetings = 'Buonasera'
    return '{} {}'.format(greetings, name)

def getSign(value):
    return '+' if value > 0 else ''

def getVariation(variation):
    return '{}{}'.format(getSign(variation), variation)

def getSeverityColor(comune, regioni):
    regione_comune = comune['regione']['nome']
    regione_lista = next((region for region in regioni if region['name'] == comune['regione']['nome']), None)
    if regione_lista is not None:
        if regione_lista['name'] == 'Trentino-Alto Adige/Südtirol':
            provincia = next((prov for prov in regione_lista['name']['province'] if prov['name'] == comune['provincia']['nome']), None)
            if provincia is not None:
                return provincia['covid_severity_color']
            else:
                return None
        else:
            return regione_lista['covid_severity_color']
    else:
        return None
