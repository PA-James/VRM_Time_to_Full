# Fetch VRM information and display in Windows CMD session
# Display Solar and Battery state
# Calculate the estimated time to reach 70% battery charge as well as estimate to reach full
# Depending on battery technology (in this case Li-Ion), absorption may add an extra hour after the batteries reach 95% - YMMV
# The max battery charge current may be different in your installation, in this case its 70A
# maxkwh must match your total battery capacity in kWh x10 (eg 19,2kWh x10 = 192)
# max battery voltage is 54 in this case - you may need to adjust to match your installation

import sys
import requests
import json
from colorama import Fore, Back, Style
from datetime import datetime
from datetime import timedelta
from time import sleep
from tenacity import retry, stop_after_attempt, stop_after_delay

from colorama import init

init()
# -----------------------------------------------------------------------------
version = 'v6' # version number to manage whatever changes are needed
login_url = 'https://vrmapi.victronenergy.com/v2/auth/login'

# Configure the 99999 value to match your own victron installation id
diags_url = "https://vrmapi.victronenergy.com/v2/installations/99999/diagnostics?count=1000"
# Configure the username and password to match your VRM login details
login_string = '{"username":"username@youremail.com","password":"MyP455w0rd!78"}'

# attempt connection
try:
    response = requests.post(login_url, login_string)
except Exception as e:
    print(f'Exception {e} occurred:, probably cant connect')
    exit(1)
token = json.loads(response.text)["token"]
headers = {'X-Authorization': "Bearer " + token}

def progress(color, title, count, total, unit='', status=''):
    bar_len = 30
    filled_len = int(round(bar_len * count / float(total)))
    percents = round(100.0 * count / float(total), 1)
    bar = chr(0x2588) * filled_len + '-' * (bar_len - filled_len)
    sys.stdout.write(color + f'{title} : [{bar}] {percents : >5}% {status : >4} {unit}\n' + Style.RESET_ALL)

@retry(stop=(stop_after_delay(1) | stop_after_attempt(5)))
def get_vrm_data():
    # Get current time in local timezone
    current_time = datetime.now()
    print('Data query at : ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '                   ' + version)
    response = requests.get(diags_url, headers=headers)
    data = response.json()["records"]

    State = [element['formattedValue'] for element in data if element['code'] == "ss"][0]
    batterySoC = float([element['rawValue'] for element in data if element['code'] == "VSOC"][0])
    batteryvoltage = float([element['rawValue'] for element in data if element['code'] == "bv"][0])
    batterycurrent = float([element['rawValue'] for element in data if element['code'] == "bc"][0])
    batterypower = int(float([element['rawValue'] for element in data if element['code'] == "bp"][0]))
    solarpower = int(float([element['rawValue'] for element in data if element['code'] == "P"][0]))
    loadpower = int(float([element['rawValue'] for element in data if element['code'] == "a1"][0]))
    gridpower = int(float([element['rawValue'] for element in data if element['code'] == "IP1"][0]))
    outputfreq = (float([element['rawValue'] for element in data if element['code'] == "OF"][0]))
    timestamp = (datetime.fromtimestamp([element['timestamp'] for element in data if element['code'] == "VSOC"][0]))

    if State == 'Discharging':
        print(Fore.LIGHTCYAN_EX + "State       : " + Fore.LIGHTRED_EX + f"{State}")
    else:
        print(Fore.LIGHTCYAN_EX + "State       : " + Fore.LIGHTCYAN_EX + f"{State}")
    progress(Fore.LIGHTCYAN_EX, "SoC    ", batterySoC, 100)
    progress(Fore.LIGHTYELLOW_EX, "Solar  ", solarpower, 5180, "W", f"{solarpower}")
    progress(Fore.LIGHTYELLOW_EX, "AC Load", loadpower, 7000, "W", f"{loadpower}")
    if batterypower >= 0 and batterypower <= 2000:
        progress(Fore.LIGHTGREEN_EX, "Battery", batterypower, 3500, "W", f"{batterypower}")
    elif batterypower > 2000 and batterypower <3500:
        progress(Fore.LIGHTGREEN_EX, "Battery", batterypower, 3500, "W", f"{batterypower}")
    elif batterypower >= 3500:
        progress(Fore.LIGHTRED_EX, "Battery", batterypower, 3500, "W", f"{batterypower}")
    else:
        progress(Fore.LIGHTRED_EX, "Battery", abs(batterypower), 4800, "W", f"{batterypower}")
    batteryvoltage_scaled = batteryvoltage - 48
    progress(Fore.LIGHTGREEN_EX, "Batt V ", batteryvoltage_scaled, 6, "V", f"{batteryvoltage}")
    if batterycurrent >= 0:
        if batterycurrent >=68.5:
            progress(Fore.LIGHTRED_EX, "Batt A ", abs(batterycurrent), 70, "A", f"{batterycurrent}")
        else:
            progress(Fore.LIGHTGREEN_EX, "Batt A ", abs(batterycurrent), 70, "A", f"{batterycurrent}")
    else:
        progress(Fore.LIGHTRED_EX, "Batt A ", abs(batterycurrent), 100, "A", f"{batterycurrent}")

    # Output AC Frequency
    print(Fore.LIGHTYELLOW_EX + f"OP Freq : {outputfreq} Hz")
    if gridpower <= 0:
        print(Fore.LIGHTMAGENTA_EX + f"AC Grid : " + Back.LIGHTGREEN_EX + Fore.BLACK + f"{gridpower :>4} W" + Style.RESET_ALL)
    else:
        print(Fore.LIGHTMAGENTA_EX + f"AC Grid : {gridpower :>4} W" + Style.RESET_ALL)
    timediff = round((datetime.now() - timestamp).seconds, 0)
    print(Fore.YELLOW + f'Data taken at : {timestamp} (Time Diff = {timediff} sec)')
    print('-------------------------------------')
    maxkwh = 192  # this is 19,2kWh x 10, cant recall why
    # to prevent divide by 0 errors, check if any of the following are true, then dont bother estimating time to full
    if float(batterypower) <= 0.0 or float(batterySoC) == 100 or batteryvoltage >= 54: # or float(solarpower) == 0.0:
        ttfmins = 0
        ttfhrs = 0
        ttfmins70 = 0
        ttfhrs70 = 0
    else:
        ttfmins = round((1 / ((float(batterypower)) / (maxkwh * (100 - float(batterySoC)) * 1))) * 60, 2)
        ttfhrs = round(ttfmins / 60, 2)
        if float(batterySoC) < 70:
        # Time to reach 70%, which should be enough to heat geysers the next morning and retain 25% SoC
            ttfmins70 = round((1 / ((float(batterypower)) / (maxkwh * 0.7 * (100 - float(batterySoC)) * 1))) * 60, 2)
            ttfhrs70 = round(ttfmins70 / 60, 2)
        else:
            ttfmins70 = 0
            ttfhrs70 = 0

    # calc expected full time
    # Get current time in local timezone
    current_time = datetime.now()
    ttf_full_time = current_time + timedelta(hours=ttfhrs)
    ttf_full_time_ab = current_time + timedelta(hours=ttfhrs + 1) # add 1hr for absorption
    ttf_full_time_str = ttf_full_time.strftime('%H:%M')
    ttf_full_time_ab_str = ttf_full_time_ab.strftime('%H:%M')

    if batterySoC == 100 or (batteryvoltage >= 53.5 and batterySoC >= 95):
        ttfmins = 0
        ttfhrs = 0
        ttf_full_time_str = "--:--"
        ttf_full_time_ab_str = "--:--"

    print(Fore.LIGHTMAGENTA_EX + f'Mins to reach full  = {ttfmins} mins')
    print(f'Hours to reach full = {ttfhrs} hrs')
    print( 'Time to reach full  = ' + Fore.LIGHTGREEN_EX + f'{ttf_full_time_str} ({ttf_full_time_ab_str})')
    # TT reach 70%
    print(Fore.LIGHTYELLOW_EX + f'Mins to reach 70%  = {ttfmins70} mins')
    print(f'Hours to reach 70% = {ttfhrs70} hrs')

    print('-------------------------------------' + Style.RESET_ALL)


# Loop to fetch status regularly
runloop = True
while runloop:
    try:
        get_vrm_data()
    except Exception as e:
        print(f'Exception {e} occurred while getting VRM data, quitting')
        runloop = False
        exit(1)
    sleep(15)
