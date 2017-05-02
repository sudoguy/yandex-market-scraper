import json
import logging
import re

import requests
import sys
import urllib3
import time

import config

from bs4 import BeautifulSoup

# The urllib library was split into other modules from Python 2 to Python 3
if sys.version_info.major == 3:
    from urllib.parse import urljoin
else:
    from urlparse import urljoin


class API(object):
    def __init__(self):
        self.LastResponse = None
        self.LastPage = None
        self.session = requests.Session()

        # handle logging
        self.logger = logging.getLogger('[yandex-market-scraper]')
        self.logger.setLevel(logging.DEBUG)
        logging.basicConfig(format='%(asctime)s %(message)s',
                            filename='ymscraper.log',
                            level=logging.INFO)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def send_request(self, endpoint, post=None):
        if not self.session:
            self.logger.critical("Session is not created.")
            raise Exception("Session is not created!")

        self.session.headers.update({'Connection': 'close',
                                     'Accept': '*/*',
                                     'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                                     'Cookie2': '$Version=1',
                                     'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4',
                                     'User-Agent': config.USER_AGENT})
        try:
            if post is not None:  # POST
                response = self.session.post(
                    config.BASE_URL + endpoint, data=post)
            else:  # GET
                response = self.session.get(
                    config.BASE_URL + endpoint)
        except Exception as e:
            self.logger.warning(str(e))
            return False

        if response.status_code == 200:
            self.LastResponse = response
            self.LastPage = response.text
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
                self.LastResponse = response
                self.LastPage = response.text.decode('cp1251')
            except:
                pass
            return False

    def get_page_by_name(self, name, page=1):
        if not name:
            self.logger.warning('Parameter "name" must be exist')
            return False
        return self.send_request('/search?text={0}&page={1}'.format(name, page))

    def get_items_from_page(self, page_text):
        items =  BeautifulSoup(page_text, 'html.parser').find('div', {'class': 'filter-applied-results'}) \
            .find_all('div', {'class': 'snippet-list'})[1] \
            .find_all('div', {'class': 'snippet-card'})
        return map(lambda item: str(item), items)

    def get_item_view(self, item):
        if not item:
            self.logger.error('Item not found!')
            return False
        soup = BeautifulSoup(item, 'html.parser')
        item_view = soup.find('div', {'class': 'snippet-card__view'})
        thumb_image = item_view.find('img', {'class': 'image'}).get('src')
        thumb_image = urljoin(config.BASE_URL, thumb_image)
        rating = item_view.find('div', {'class': 'rating'})
        if rating:
            rating = rating.text
        else:
            rating = None
        return json.dumps({
            'thumb_image': thumb_image,
            'rating': rating
        })

    def get_item_info(self, item):
        if not item:
            self.logger.error('Item not found!')
            return False
        soup = BeautifulSoup(item, 'html.parser')
        item_info = soup.find('div', {'class': 'snippet-card__info'})
        min_price = item_info.find('div', {'class': 'price'})
        max_price = item_info.find('span', {'class': 'price'})
        if min_price and max_price:
            min_price = re.match(r'[\d\s]+', min_price.text)
            min_price = min_price.group(0).replace(' ', '')
            max_price = re.match(r'[\d\s]+', max_price.text)
            max_price = max_price.group(0).replace(' ', '')
        else:
            min_price = None
            max_price = None
        rating = item_info.find('div', {'class': 'rating'})

        return json.dumps({
            'min_price': min_price,
            'max_price': max_price
        })


bot = API()
bot.get_page_by_name('macbook')

soup = BeautifulSoup(bot.LastPage, 'html.parser')
results = soup.find('div', {'class': 'filter-applied-results'}) \
    .find_all('div', {'class': 'snippet-list'})[1] \
    .find_all('div', {'class': 'snippet-card'})
for item in results:
    print(bot.get_item_view(item))
    print(bot.get_item_info(item))
print(results)
