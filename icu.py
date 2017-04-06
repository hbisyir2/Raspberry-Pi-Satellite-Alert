# In order to run text message: sudo apt-get install ssmtp mailutils


import collections
import argparse
import requests
import RPi.GPIO as GPIO
import datetime
import time
import pygame # for standard audio output
import smtplib # for texting interface
import json
import sys
import math
import ephem

GPIO.setmode(GPIO.BOARD) ## Use board pin numbering
GPIO.setup(7, GPIO.OUT) ## Setup GPIO Pin 7 to OUT

s = smtplib.SMTP('smtp.gmail.com',587)

phoneAddress = '7034701866@txt.att.net' #Number to send message to

audioFile = 'MarioAlert.mp3'

# Function to blink LED
def Blink():
	numTimes = 5
	speed = 1
	for i in range(0,numTimes):
		GPIO.output(7,True)
		time.sleep(speed)
		GPIO.output(7,False)
		time.sleep(speed)

# Function to play audio file
def PlaySound(soundFile):
	pygame.mixer.init()
	pygame.mixer.music.load(soundFile)
	pygame.mixer.music.play()
	while pygame.mixer.music.get_busy() == True:
		continue

# Function to send text message
def SendText(phone, message):
	smtpUser = 'hakeem.bisyir@gmail.com'
	smtpPass = 'mrykxzkntlaxycsv'
	s.ehlo()
	s.starttls()
	s.ehlo()
	s.login(smtpUser, smtpPass)
	s.sendmail(smtpUser, phone, message)
	s.quit()

# Function to trigger all three alerts
def TriggerAlert(phoneNumber, messageBody, soundFile):
	SendText(phoneNumber, messageBody)
	for _ in range(50):
		Blink()
		PlaySound(soundFile)
	GPIO.cleanup()


# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument('-z', required=True)
parser.add_argument('-s', required=True)
args = parser.parse_args()

zipcode = args.z
noradId = args.s


# Parameter satellite: NORAD ID as type string
# Returns a TLE of the satellite as type string
def getTLE(satellite):
	try:	
	    loginURL = 'https://www.space-track.org/ajaxauth/login'
	    baseURL = 'https://www.space-track.org/'
	    controller = 'basicspacedata/'
	    requestAction = 'query/'
	    predicate = 'class/'
	    value = 'tle_latest/format/tle/NORAD_CAT_ID/' + satellite + '/ORDINAL/1'
	
	    r = requests.post(loginURL, data={'identity':'bjason1@vt.edu', 'password':'virginiatechspacetrack'})
	    cookie = r.cookies
	    if r.ok:
	        r = requests.get(baseURL + controller + requestAction + predicate + value, cookies=cookie)
	        return r.text
	    print("Error code ", r.text)

	except Exception:
		print("Error: Satellite API Error: ", Exception)

#Get weather data ######################################################
url = 'http://api.openweathermap.org/data/2.5/forecast/daily?zip=' + str(zipcode) + ',us&cnt=16&APPID=00d0fe518cb4d72c67a854cca7963815'

response = requests.get(url)

try:
	if(response.ok):
		str_response = response.content.decode('utf-8')
		weatherdata = json.loads(str_response)
		latitude = weatherdata['city']['coord']['lat']
		longitude = weatherdata['city']['coord']['lon']

		print ("Latitude: ", latitude, " Longitude: ", longitude, '\n')

		weatherDict = {}
		x=0;
		for keys in weatherdata['list']:
			date = weatherdata['list'][x]['dt']
			weatherCond = weatherdata['list'][x]['weather'][0]['main']
			print("Day ", x, " : ", str(weatherCond))
			if(weatherdata['list'][x]['clouds'] < 20):
				weatherDict[date] = True
			else:
				weatherDict[date] = False
			x+=1
	else:
		response.raise_for_status()



	
	weatherDict_o = collections.OrderedDict(sorted(weatherDict.items()))

except Exception:
	print("Weather API Error: ", Exception)
########################################################################


try:
	#Get satellite information
	resp = getTLE(noradId)
	lines = resp.splitlines()	
	
	#Satellite Object
	sat = ephem.readtle(noradId, lines[0], lines[1])

	#Observer Objects
	observer = ephem.Observer()
	observer.lat = latitude
	observer.long = longitude
	observer.horizon = '-0:34'	
	print ("Satellite TLE: \n", lines[0], '\n', lines[1])

	
	
		
except Exception:
	print("Error: ", Exception)



visible_dates = []

tr, azr, tt, altt, ts, azs = observer.next_pass(sat)

print("tr:", tr, " azr:", azr, " tt:", tt, " altt:", altt, " ts:", ts, " azs:", azs)

sr_day = str(tr).partition(" ")[0]

for p in weatherDict_o:

    w_day = time.strftime('%Y/%-m/%-d %H:%M:%S', time.localtime(p)).partition(" ")[0]

    #While satellite rising date
    while(w_day == sr_day):
        while tr < ts:

            #Sun object
            sun = ephem.Sun()

            #Compute sun and satellite values
            sun.compute(observer)
            sat.compute(observer)

            sun_alt = math.degrees(sun.alt)
            observer.date = tr

            satFound = False

            # If satellite is not eclipsed and light conditions are good
            if sat.eclipsed is False and -18 < math.degrees(sun_alt) < -6:
                if len(visible_dates) < 5 and weatherDict[p] is True:
                    
                    tr_parse = datetime.datetime.strptime(str(tr), '%Y/%m/%d %H:%M:%S')
                    tr_to_save = tr_parse - datetime.timedelta(minutes=15)
                    
                    visible_dates.append(str(tr_to_save))
                    
                    print("Satellite visible", tr)
                    print("Sublatitude:", sat.sublat)
                    print("Sublongitude:", sat.sublong)
                    print("Apparent geocentric position:", sat.g_ra, sat.g_dec)
                    # If weather is < 20% cloud coverage
                    if weatherDict[p] is False:
                        print("Note: cloud coverage may prevent clear sight of satellite")
                    satFound = True
                    

            if not satFound:
                #Move forward one minute
                tr = ephem.Date(tr + (60 * ephem.second))

        t = datetime.datetime.strptime(str(tr), '%Y/%m/%d %H:%M:%S')
        observer.date = t + datetime.timedelta(seconds=10)
        tr, azr, tt, altt, ts, azs = observer.next_pass(sat)
        print("tr:", tr, " azr:", azr, " tt:", tt, " altt:", altt, " ts:", ts, " azs:", azs)
        sr_day = str(tr).partition(" ")[0]

if(len(visible_dates) < 5):
	print("Less than 5 visible dates in the next 15 days")

for next_time in visible_dates:
	visible_year = next_time.split(' ')[0].split('-')[0]
	visible_month = next_time.split(' ')[0].split('-')[1]
	visible_day = next_time.split(' ')[0].split('-')[2]
	visible_hour = next_time.split(' ')[1].split(':')[0]
	visible_min = next_time.split(' ')[1].split(':')[1]
	curr_year = datetime.datetime.now().strftime('%Y')
	curr_month = datetime.datetime.now().strftime('%m')
	curr_day = datetime.datetime.now().strftime('%d')
	curr_hour = datetime.datetime.now().strftime('%H')
	curr_min = datetime.datetime.now().strftime('%M')
	
	while visible_year != curr_year or visible_month != curr_month or visible_day != curr_day or visible_hour != curr_hour or visible_min != curr_min:
		time.sleep(60)
		curr_year = datetime.datetime.now().strftime('%Y')
		curr_month = datetime.datetime.now().strftime('%m')
		curr_day = datetime.datetime.now().strftime('%d')
		curr_hour = datetime.datetime.now().strftime('%H')
		curr_min = datetime.datetime.now().strftime('%M')
	textMessage = 'Satallite ' + noradId + ' will be visible in zipcode ' + zipcode + ' in 15 minutes!'
	TriggerAlert(phoneAddress, textMessage, audioFile)
	
