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