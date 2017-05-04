import json
import logging
import re
from random import random, choice

import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from requests.exceptions import ProxyError, SSLError
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


def error_handler(func):
    def error_handler_wrapper(*args, **kwargs):
        self = args[0]
        while True:
            try:
                return func(*args, **kwargs)
            except AttributeError:
                self.logger.error('Captcha! Getting new proxy.')
                self.user_agent = choice(config.USER_AGENT)
                self.set_new_proxy()
                time.sleep(60 * random())
            except (ProxyError, SSLError) as e:
                self.logger.error(str(e))
                self.logger.error('Not working proxy. Getting new one.')
                self.set_new_proxy()
                time.sleep(60 * random())
            except Exception as e:
                self.logger.warning(str(e))
                time.sleep(60 * random())
                continue

    return error_handler_wrapper


def clean_url(url):
    # filter links on local stores
    if 'market-click' in url:
        return None
    # remove parameters from url
    if url.find('?') == -1:
        return url
    else:
        return url[:url.find('?')]


class API(object):
    def __init__(self):
        self.LastResponse = None
        self.LastPage = None
        self.session = requests.Session()
        self.session.mount('https://', HTTPAdapter(max_retries=3))
        from proxy_switcher import ProxySwitcher
        self.proxy_switcher = ProxySwitcher()
        self.user_agent = choice(config.USER_AGENT)
        self.session.proxies = None

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
        self.set_new_proxy()

    @error_handler
    def send_request(self, endpoint, post=None):
        if not self.session:
            self.logger.critical("Session is not created.")
            raise Exception("Session is not created!")

        self.session.headers.update({'Connection': 'close',
                                     'Accept': '*/*',
                                     'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                                     'Cookie2': '$Version=1',
                                     'Accept-Language': 'ru-RU,ru;q=0.8,en-US;q=0.6,en;q=0.4',
                                     'User-Agent': self.user_agent})

        if post is not None:  # POST
            response = self.session.post(
                config.BASE_URL + endpoint, data=post)
        else:  # GET
            response = self.session.get(
                config.BASE_URL + endpoint)

        if response.status_code == 200:
            if 'showcaptcha' in response.url:
                raise AttributeError
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

    @error_handler
    def get_page_by_name(self, name, page=1):
        if not name:
            self.logger.warning('Parameter "name" must be exist')
            return False
        return self.send_request('/search?text={0}&page={1}'.format(name, page))

    @error_handler
    def get_items_from_page(self, page_text):
        if not page_text:
            self.logger.error('Page not found!')
            assert ValueError('Page not found!')

        items = BeautifulSoup(page_text, 'html.parser').find('div', {'class': 'filter-applied-results'}) \
            .find_all('div', {'class': 'snippet-list'})[1] \
            .find_all('div', {'class': 'snippet-card'})
        return map(lambda item: str(item), items)

    @error_handler
    def set_new_proxy(self):
        new_proxy = None
        while not new_proxy:
            new_proxy = self.proxy_switcher.get_new_proxy()
        self.session.proxies = {'https': new_proxy}
        self.logger.warning("New proxy - {0} [LEFT {1}]".format(new_proxy, len(self.proxy_switcher.proxies)))

    @error_handler
    def get_item_view(self, item):
        if not item:
            self.logger.error('Item is empty!')
            assert ValueError('Item is empty!')
        soup = BeautifulSoup(item, 'html.parser')
        item_view = soup.find('div', {'class': 'snippet-card__view'})
        thumb_image = item_view.find('img', {'class': 'image'})
        if thumb_image:
            thumb_image = urljoin(config.BASE_URL, thumb_image.get('src'))
        else:
            thumb_image = None

        rating = item_view.find('div', {'class': 'rating'})
        if rating:
            rating = float(rating.text)
        else:
            rating = None
        return {
            'thumb_image': thumb_image,
            'rating': rating
        }

    @error_handler
    def get_item_info(self, item):
        if not item:
            self.logger.error('Item is empty!')
            assert ValueError("Item is empty!")
        soup = BeautifulSoup(item, 'html.parser')
        item_info = soup.find('div', {'class': 'snippet-card__info'})
        min_price = item_info.find('div', {'class': 'price'})
        max_price = item_info.find('span', {'class': 'price'})
        if min_price:
            min_price = re.search(r'(\d+)', min_price.text.replace(' ', ''))
            min_price = int(min_price.group())
        else:
            min_price = None
        if max_price:
            max_price = re.search(r'(\d+)', max_price.text.replace(' ', ''))
            max_price = int(max_price.group())
        else:
            max_price = None

        return {
            'min_price': min_price,
            'max_price': max_price
        }

    @error_handler
    def get_item_content(self, item):
        if not item:
            self.logger.error('Item is empty!')
            assert ValueError("Item is empty!")
        soup = BeautifulSoup(item, 'html.parser')
        item_content = soup.find('div', {'class': 'snippet-card__content'})
        product = item_content.find(
            'span', {'class': 'snippet-card__header-text'}).text

        product_link = item_content.find(
            'a', {'class': 'snippet-card__header-link'})['href']
        product_link = clean_url(urljoin(config.BASE_URL, product_link))

        category = item_content.find(
            'a', {'class': 'snippet-card__subheader-link'})

        if category:
            category = category.text
            category_link = urljoin(config.BASE_URL,
                                    item_content.find('a', {'class': 'snippet-card__subheader-link'})['href'])
            category_link = clean_url(category_link)
        else:
            category = None
            category_link = None

        short_description = item_content.find_all(
            'li', {'class': 'snippet-card__desc-item'})
        if short_description:
            short_description = [
                li.text for li in short_description if 'Цвет' not in li.text]
        else:
            short_description = None

        return {
            'product': product,
            'product_link': product_link,
            'category': category,
            'category_link': category_link,
            'short_description': short_description,
        }


bot = API()

products = []
for x in tqdm(range(1, 10), desc='Pages processed'):
    bot.get_page_by_name('macbook', page=x)

    results = bot.get_items_from_page(bot.LastPage)
    if results:
        for item in results:
            view_data = bot.get_item_view(item)
            info_data = bot.get_item_info(item)
            content_data = bot.get_item_content(item)
            product = {
                'preview': {
                    'view': view_data,
                    'info': info_data,
                    'content': content_data
                }
            }
            products.append(product)

with open('products.json', 'w') as file:
    file.write(json.dumps(products, ensure_ascii=False))
    file.close()
