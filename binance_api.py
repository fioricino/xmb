import hashlib
import http.client
import json
import logging
import urllib.parse

import requests
import hmac

import time

from exceptions import ApiError

API_URL = 'api.binance.com'
API_VERSION = 'v3'

API_KEY = 'HegeFPcysaLj8SMJYvEt5oE0gbJucrymRo91bnw8c5xRQ0pGotwn7Y58EPlF4KrZ'
API_SECRET = b'htTDnjZNJUroN7WydpP7OdKaQd95CywKHsWUMGEkVLuR8SK3VZJOHreOp2ilp0kM'

logger = logging.getLogger('xmb')


class BinanceApi:

    def get_open_orders(self, currency_1, currency_2):
        try:
            timestamp = int(time.time() * 1000)
            url = "/api/" + API_VERSION + "/" + 'openOrders' \
                  + '?symbol='+currency_1+currency_2 + '&timestamp='+str(timestamp)
            return BinanceApi._call_binance_api(url,'GET', symbol=currency_1+currency_2, timestamp=timestamp)
        except KeyError:
            logger.debug('No open market orders')
            return []

    def get_canceled_orders(self, currency_1, currency_2):
        try:
            timestamp = int(time.time() * 1000)
            return BinanceApi._call_api('allOrders','GET',symbol=currency_1+currency_2, timestamp=timestamp)
        except KeyError:
            return []

    # def prices(self):
    #     BinanceApi._call_binance_api("ticker/allPrices")


    @staticmethod
    def _call_binance_api(url, http_method, **kwargs):
        logger.debug('Call Binance api. Url {}. Payload: {}'.format(url, kwargs))

        if kwargs:
             payload = kwargs
        payload = urllib.parse.urlencode(payload)

        H = hmac.new(key=API_SECRET, digestmod=hashlib.sha256)
        H.update(payload.encode('utf-8'))
        sign = H.hexdigest()

        # url = "/api/" + API_VERSION + "/" + api_method
        # if http_method == 'GET':
        #      url += '?symbol='+symbol + '&timestamp='+str(timestamp)  +'&signature='+sign
        url+= '&signature='+sign

        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "X-MBX-APIKEY": API_KEY,
                   "signature": sign}
        conn = http.client.HTTPSConnection(API_URL, timeout=60)
        conn.request(http_method, url, payload, headers)
        # conn.request(http_method, "/api/" + API_VERSION + "/" + api_method)
        response = conn.getresponse().read()
        conn.close()
        try:
            obj = json.loads(response.decode('utf-8'))
            logger.debug('Received response: {}'.format(response))
            if 'error' in obj and obj['error']:
                raise ApiError(obj['error'])
            print(obj)
        except json.decoder.JSONDecodeError:
            raise ApiError('Ошибка анализа возвращаемых данных, получена строка', response)
