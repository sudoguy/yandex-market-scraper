import time
import config
import requests
import logging

from random import random
from bs4 import BeautifulSoup


def error_handler(func):
    def error_handler_wrapper(*args, **kwargs):
        self = args[0]
        while True:
            try:
                return func(*args, **kwargs)
            except AttributeError:
                self.logger.error('Captcha! Getting new proxy.')
                self.set_new_proxy()
            except Exception as e:
                self.logger.warning(str(e))
                time.sleep(10 * random())
                continue

    return error_handler_wrapper


class ProxySwitcher(object):
    def __init__(self):
        self.proxies = []
        self.session = requests.Session()
        self.last_response = None
        self.last_page = None

        # handle logging
        self.logger = logging.getLogger('[proxy_switcher]')
        self.logger.setLevel(logging.DEBUG)
        logging.basicConfig(format='%(asctime)s %(message)s',
                            filename='proxy_switcher.log',
                            level=logging.INFO)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        self.load_proxies()

    @error_handler
    def send_request(self, endpoint='/', post=None):
        if not self.session:
            raise Exception("Session is not created!")

        self.session.headers.update({'Connection': 'close',
                                     'Accept': '*/*',
                                     'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                                     'Cookie2': '$Version=1',
                                     'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4',
                                     'User-Agent': config.USER_AGENT[0]})
        try:
            if post is not None:  # POST
                response = self.session.post(
                    config.PROXY_URL + endpoint, data=post)
            else:  # GET
                response = self.session.get(
                    config.PROXY_URL + endpoint)
        except Exception as e:
            self.logger.warning(str(e))
            return False

        if response.status_code == 200:
            self.last_response = response
            self.last_page = response.text
            return True
        else:
            self.logger.warning("Request return " +
                                str(response.status_code) + " error!")
            if response.status_code == 429:
                sleep_minutes = 5
                self.logger.warning("That means 'too many requests'. "
                                    "I'll go to sleep for %d minutes." % sleep_minutes)
                time.sleep(sleep_minutes * 60)

            # for debugging
            try:
                self.last_response = response
                self.last_page = response.text.decode('cp1251')
            except Exception as e:
                self.logger.critical(str(e))
            return False

    @error_handler
    def load_proxies(self):
        if self.send_request():
            soup = BeautifulSoup(self.last_page, 'html.parser')
            tbody = soup.find('table', {'id': 'proxylisttable'}).find('tbody')
            rows = tbody.find_all('tr')
            for row in rows:
                tds = row.find_all('td')
                if not tds:
                    continue
                ip_address = tds[0].text
                port = tds[1].text
                self.proxies.append('{0}:{1}'.format(ip_address, port))
            self.proxies = self.proxies[::-1]
            return True
        return False

    @error_handler
    def get_new_proxy(self):
        try:
            return self.proxies.pop()
        except IndexError:
            self.logger.warning("Proxy list is empty. Timeout 5 minutes and loading new list.")
            time.sleep(60 * 5)
            self.load_proxies()
            self.get_new_proxy()
