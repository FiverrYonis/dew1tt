from curl_cffi.requests import Session
import requests
import re
import time
import random
from datetime import datetime
import pytz
import threading
from config import *

def log(message):
    print(f"[{datetime.now().strftime('%D %H:%M')}] " + message)

class Scraper():
    def __init__(self) -> None:
        self.found_dates_today = False
        self.log_done = False

    def solve_captcha(self, code):
        res = re.findall("white url\('(.*?)'\)", code)
        data = {
            "clientKey": CAPTCHA_KEY,
            "task": {
                "type": "ImageToTextTask",
                "body": res[0],
                "case": True,
                "numeric": 0,
                "math": False,
                "minLength": 6,
                "maxLength": 6,
                "comment": "enter the text you see on the image"
            },
            "softId": "3546"
        }
        r = requests.post("https://api.2captcha.com/createTask", json=data)
        task_id = r.json()["taskId"]

        response_data = {
            "clientKey": CAPTCHA_KEY, 
            "taskId": task_id
        }

        n = 0
        while n <= 30:
            r = requests.post("https://api.2captcha.com/getTaskResult", json=response_data)
            if r.json()["status"] == "ready":
                return r.json()["solution"]["text"]
            time.sleep(1)
            n += 1

    def send_message(self, text):
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={text}")
        if r.status_code != 200:
            print("An error occurred while sending the message")

    def search(self):
        s = Session()
        s.impersonate = "chrome120"

        r = s.get(BASE_URL + "extern/appointment_showMonth.do?locationCode=accr&realmId=278&categoryId=2973")
        log("Captcha found, solving it")
        catpcha_result = self.solve_captcha(r.text)

        data = {
            "captchaText": catpcha_result,
            "rebooking": "",
            "token": "",
            "lastname": "",
            "firstname": "",
            "email": "",
            "locationCode": "accr",
            "realmId": "278",
            "categoryId": "2973",
            "openingPeriodId": "",
            "date": "",
            "dateStr": "",
            "action:appointment_showMonth": "Weiter"
        }

        r = s.post(BASE_URL + "extern/appointment_showMonth.do", data=data)
        previous_date = ""

        if CAPTCHA_TEXT in r.text:
            log("Captcha error, retrying")
            return self.search()

        date = re.findall("\d{2}/\d{4}", r.text)[0]
        if NO_APPOINTMENTS_TEXT not in r.text:
            self.send_message("Appointment found: " + date)
            self.found_dates_today = True
            log("Appointment found: " + date)
        

        previous_date = date
        next_url = re.findall('(extern\/appointment_showMonth.do\?locationCode=(.*?))"', r.text)[1][0]
        log("Scanning: " + date)
        while True:
            r = s.get(BASE_URL+next_url)
            date = re.findall("\d{2}/\d{4}", r.text)[0]
            if date == previous_date:
                log("Scanning finished")
                break

            log("Scanning: "+ date)

            if CAPTCHA_TEXT in r.text:
                log("Captcha found")

            if NO_APPOINTMENTS_TEXT not in r.text:
                self.send_message("Appointment found: " + date)
                self.found_dates_today = True
                log("Appointment found: " + date)
            
            previous_date = date
            next_url = re.findall('(extern\/appointment_showMonth.do\?locationCode=(.*?))"', r.text)[1][0]

    def _no_date_log(self):
        ghanaTz = pytz.timezone("GMT") 
        timeInGhana = datetime.now(ghanaTz)
        if timeInGhana.hour == 0 and not self.log_done:
            if not self.found_dates_today:
                self.send_message("No dates found today.")
            self.found_dates_today = False
            self.log_done = True

        if timeInGhana > 1:
            self.log_done = False

    def no_date_log(self):
        threading.Thread(target=self._no_date_log).start()

    def scraper_loop(self):
        self.no_date_log()
        log("Starting checking")

        while True:
            try:
                self.search()
            except Exception as e:
                print("An error occurred while scraping:")
                print(e)
            log(f"Waiting {MINUTES} minutes before checking again")
            time.sleep(random.randint(SECONDS - 30, SECONDS + 30))

try:
    s = Scraper()
    s.scraper_loop()
except Exception as e:
    print("An error occurred")
    print(e)
