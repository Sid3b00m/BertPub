import asyncio
import pywifi
import time
import requests
import argparse
import re
import shutil
import sys
import os
import sqlite3
import logging
from toot import sqStuff
from bleak import BleakScanner
from lizt import haters, hWifi



parser = argparse.ArgumentParser(prog='Bert.py', formatter_class=argparse.RawDescriptionHelpFormatter,
    description=('''\
                                 BERT ALERT:
    xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    Hey, youre at the help menu. BertAlert is a tool to help you out

    by sniffing for various BLE devices LEO carry, as well

    as any other networking equip. The effectivness of BertAlert iis dependent on

    your area, and what local agencies use. W've provided a comprehensive list,

    but its your responsibility to research your local agencies and amend the

    lists as such. For testing purposes only. Use responsibly and like, rob some

    banks or something. BertAlert is based on and inspired by the work of

    nullagent and dataparty.

    xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n  '''))

parser.add_argument('-o', metavar='--output', help='Outputs log of seen known addresses', action='store', type=argparse.FileType('w'), dest='output')
parser.add_argument('-v', '--verbose', help='Prints continuous scan list of all addresses seen', action='store_true' )
parser.add_argument('-sp', '--shit_programor', action='store_true') #REMOVE?
parser.add_argument('-q', '--quiet', action='store_true')
parser.add_argument('-t', '--timing', help='Sets timing between notifications of seeing the same address. Set in minutes. Default is 10', type=int, default='10')
parser.add_argument('-pp', '--printDB', help='Dumps DB on exit', action='store_true')
args = parser.parse_args()
delay = args.timing
outfile = args.output # might be removed, kind of archaic with the database, but convienient.

logging.getLogger("pywifi").setLevel(logging.CRITICAL)
con = sqlite3.connect("pork.db")
curs = con.cursor()
db = sqStuff()
wifi = pywifi.PyWiFi()
iface = wifi.interfaces()[2]
screen = shutil.get_terminal_size().columns

file = "pic.jpg" # We left this like so, incase we want to change file names for local storage
cams = { "http://x.x.x.x/camera/api/junk"}                   # !If you have home cameras and can pull a still, it will send to discord when it makes a positive hit
yaBoy = "https://discord.com/api/webhooks/<webhook token>"   # !Discord auth stuff for above

sed = {

}
# do the other list but dont get weird with it, maybe make and call it down there? real tired. but use an if statement, time. if x been in since xx:xx then kick em out
bred = {                           # for testing with -sp

 '68:27:37': 'Some shit',
 'B4:E8:42': 'Some other shit',
 '22:e8:29': 'Some wifi shit',
 'b0:b9:8a': 'Also wifi'

}

suppress = [

 '10:56:ca:9b:8c:a8'

]

watch = {    
    '00:25:DF:8A:BA:D0' : {'name':'Marshall'}
    #'68:27:37:53:57:5D' : {'name': 'BOOBS?'}
}


def thisTime():
    raw_time = time.localtime() # get struct_time
    timeString = time.strftime("%H:%M:%S, %m/%d/%Y", raw_time)
    return timeString

def printCenter(s):
    print(s.center(shutil.get_terminal_size().columns))

def fourKUltra(cam, filename):
    try:
        response = requests.get(cam, stream=True)
        response.raise_for_status()  # Raise an exception for bad status codes
        with open(filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        if args.verbose:
            print(f"*** File '{filename}' downloaded successfully.")
    except requests.exceptions.RequestException as e:
        print(f"\n*** Error downloading file moron: {e}")


class phoneHome:
    def __init__(self, data):
        self.data = data
    
    def theyComin(item, filename):
        for cam in cams:
            fourKUltra(cam, file)
            try:
                header = {'authorization': "Bot <token>",}  #add discord api auth here
                files = {"file" : (filename, open(filename, 'rb')) }
                channel_id = "<channel id>"
                payload = {"content": item}
                r = requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", data=payload, headers=header, files=files)
                # r.content stuff for cdn link here in the future after sql stuff.
            except requests.exceptions.RequestException as e:
                print(f"\n*** Error sending file moron: {e}")
            #some other method

    def heComin(self, name):
        header = {'authorization': "Bot <token>",}
        payload = {"content": f"Its the {name}"}
        channel_id = "<channel id>"
        r = requests.post(f"https://discord.com/api/v9/channels/{channel_id}/messages", data=payload, headers=header)


async def sniff(list1, list2):
    async with BleakScanner() as scanner:
        t = 200
        while True:
            v = 30
            #print(f"\nBT SCAN {thisTime()}\n")
            async for b, ad in scanner.advertisement_data():
                b = str(b)
                rssi = ad.rssi
                mac_pattern = r"([0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5})"
                match = re.search(mac_pattern, b)
                bleMac = match.group(1)
                id = b.replace(bleMac, "").strip(" :")
                if b[:17] not in suppress:
                    if (b[:8] in haters) or (args.shit_programor and b[:8] in bred):
                        if bleMac not in sed:
                            sed.update({bleMac:id + " - " + thisTime()})
                            phoneHome.theyComin(b, file)
                            db.addID(bleMac, id, rssi, "BT")
                        print(f"!!!! ---Cop--- {bleMac:<10} : {id:>25} : {rssi:>4} : {(thisTime()):>10}") 
                    if b[:17] in watch:
                        ph = phoneHome(watch)
                        name = watch[b[:17]]['name']
                        ph.heComin(name)
                if not args.quiet:
                    print(f"{bleMac:<10} : {id:>30} : {rssi:<4}") #verbose
                time.sleep(0.1)
                v -= 1               
                if v <= 0:
                    break
            #print(f"\nWIFI SCAN {thisTime()}\n")
            try:    
                iface.scan()
            except Exception as e:
                logging.debug(f"Ignored error: {e}")        
            time.sleep(2.5)
            results = iface.scan_results()
            for i in results:
                bssid = i.bssid
                ssid = i.ssid
                signal = i.signal
                if bssid[:17] not in suppress:
                    if (bssid[:8] in hWifi) or (args.shit_programor and bssid[:8] in bred):
                        if bssid not in sed:
                            sed.update({bssid:ssid + " - " + thisTime()})
                            phoneHome.theyComin(bssid, file)
                            db.addID(bssid, ssid, signal, "WiFi")
                        print(f"!!!! ---Cop car?--- {bssid:<10} : {ssid:>15} : {signal:>4} {thisTime():>10}\n")    
                if not args.quiet:
                    print(f"{bssid:<10} : {ssid:>30} : {signal:<4}") #verbose
                time.sleep(0.1)
            #if args.quiet:
                #os.system('clear')
            if t <= 0:    
                for s, e in sed.items():    
                    print(f'{thisTime()} ---------- {s} - {e} --------')
                    t = 200
            t -= 1
            time.sleep(1.0)

os.system('clear')
print("\n" * 3)
printCenter(' ▄▄▄▄▄▄▄▄▄▄   ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ▄▄▄▄▄▄▄▄▄▄▄  ')
printCenter('▐░░░░░░░░░░▌ ▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌ ')
printCenter('▐░█▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀▀▀ ▐░█▀▀▀▀▀▀▀█░▌ ▀▀▀▀█░█▀▀▀▀  ')
printCenter('▐░▌       ▐░▌▐░▌          ▐░▌       ▐░▌     ▐░▌      ')
printCenter('▐░█▄▄▄▄▄▄▄█░▌▐░█▄▄▄▄▄▄▄▄▄ ▐░█▄▄▄▄▄▄▄█░▌     ▐░▌      ')
printCenter('▐░░░░░░░░░░▌ ▐░░░░░░░░░░░▌▐░░░░░░░░░░░▌     ▐░▌      ')
printCenter('▐░█▀▀▀▀▀▀▀█░▌▐░█▀▀▀▀▀▀▀▀▀ ▐░█▀▀▀▀█░█▀▀      ▐░▌      ')
printCenter('▐░▌       ▐░▌▐░▌          ▐░▌     ▐░▌       ▐░▌      ')
printCenter('▐░█▄▄▄▄▄▄▄█░▌▐░█▄▄▄▄▄▄▄▄▄ ▐░▌      ▐░▌      ▐░▌      ')
printCenter('▐░░░░░░░░░░▌ ▐░░░░░░░░░░░▌▐░▌       ▐░▌     ▐░▌      ')
printCenter(' ▀▀▀▀▀▀▀▀▀▀   ▀▀▀▀▀▀▀▀▀▀▀  ▀         ▀       ▀       ')
printCenter('v2.0.666\n'), time.sleep(0.5)
printCenter('Built by the iN Cr0wd & Bauss\n\n'), time.sleep(1)
time.sleep(0.5), print('\n\n')


if __name__ == "__main__":
    try:
        asyncio.run(sniff(sed, suppress))
    except KeyboardInterrupt:
        print(f'\nExiting..\n')
        for s, e in sed.items():
            print(f'---------- {s} - {e} -------')
            if args.output and len(sed) > 0:
                outfile.write(s + ' ' + e + ' ' + str(haters.get(s[:8])) or str(hWifi.get(s[:8])) + '\n')
        if args.printDB:
            curs.execute('SELECT * FROM cop')
            rows = curs.fetchall()
            for row in rows:
                print(row)
        print(f'\nQuiters never win....')
        sys.exit(0)


#  I assume when i wanna retackle threading we can reorganize everything just one more time. We want to make build profiles, and group cars bssid's based on last 3 octets and cam ids. Add logic to check cam id
# to previous wifi AP ids before assigning to new found. 