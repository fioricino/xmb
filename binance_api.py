import hashlib
import http.client
import json
import logging
import urllib.parse
from collections import OrderedDict

import requests
import hmac

import time

from exceptions import ApiError

API_URL = 'api.binance.com'
API_VERSION = 'v3'

API_KEY = 'Gowa5xGG3PdCWa5ciCrZeTPXGqrUNy7Qh4MKHXiKUGMvaLM4GAhgIGJlbaFIZVlV'
API_SECRET = 'avIfwd471KlubRpXNHyV2lH9cgRZLfgGngNvBCx2SyzEDVlTbhGqF2vQqiATGUfc'

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
            timestamp = int(round(time.time() * 1000))
            url = "/api/" + API_VERSION + "/" + 'allOrders' \
                  + '?symbol=' + currency_1 + currency_2 + '&timestamp=' + str(timestamp)
            obj = BinanceApi._call_binance_api(url,'GET',symbol=currency_1+currency_2, timestamp=timestamp)
            print(obj)
            newObj = []
            for order in obj:
                if order['status'] is 'CANCELED':
                    newObj.append(order)
            return newObj
        except KeyError:
            return []


    def is_order_partially_completed(self, currency_1, currency_2, order_id):
        try:
            timestamp = int(round(time.time() * 1000))
            url = "/api/" + API_VERSION + "/" + 'order' \
                  + '?orderId=' + str(order_id) + '&symbol=' + currency_1 + currency_2 + '&timestamp=' + str(timestamp)
            BinanceApi._call_binance_api(url, 'GET', symbol=currency_1 + currency_2, orderId=order_id,
                                                  timestamp=timestamp)
        except Exception as e:
            if 'Error 50304' in str(e):
                return False
            else:
                raise e
        return True

    # TODO: fix '{"code":-1101,"msg":"Duplicate values for a parameter detected."}'
    def cancel_order(self, currency_1, currency_2, order_id):
        logger.info('Cancel order %s', order_id)
        timestamp = int(round(time.time() * 1000))
        url = "/api/" + API_VERSION + "/" + 'order' \
              + '?orderId=' + str(order_id) + '&symbol=' + currency_1 + currency_2 + '&timestamp=' + str(timestamp)
        return BinanceApi._call_binance_api(url, 'DELETE', symbol=currency_1 + currency_2, orderId=order_id,
                                     timestamp=timestamp)

    def get_balances(self):
        timestamp = int(round(time.time() * 1000))
        url = "/api/" + API_VERSION + "/" + 'account'+ '?timestamp=' + str(timestamp)
        return BinanceApi._call_binance_api(url, 'GET', timestamp=timestamp)['balances']

    # def prices(self):
    #     BinanceApi._call_binance_api("ticker/allPrices")


    @staticmethod
    def _call_binance_api(url, http_method, **kwargs):
        logger.debug('Call Binance api. Url {}. Payload: {}'.format(url, kwargs))

        if kwargs:
             payload = sorted(kwargs.items())
        payload = urllib.parse.urlencode(payload)

        H = hmac.new(key=API_SECRET.encode('utf-8'), digestmod=hashlib.sha256)
        H.update(payload.encode('utf-8'))
        sign = H.hexdigest()
        # sign = hmac.new(API_SECRET.encode('utf-8'), payload.encode('utf-8'), digestmod=hashlib.sha256).hexdigest()

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
            # if 'code' in obj and obj['code']:
            #     raise ApiError(obj['code'],obj['msg'])
            print(obj)
            return obj
        except json.decoder.JSONDecodeError:
            raise ApiError('Ошибка анализа возвращаемых данных, получена строка', response)
