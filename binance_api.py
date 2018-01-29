import hashlib
import http.client
import json
import logging
import urllib.parse
import hmac
import time

from exceptions import ApiError

# Class uses API method from Binance.
# information about API
# https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md
# https://support.binance.com/hc/en-us/articles/115003235691-Binance-API-Trading-Rules

API_URL = 'api.binance.com'
API_VERSION_3 = 'v3'
API_VERSION_1 = 'v1'

API_KEY = 'Gowa5xGG3PdCWa5ciCrZeTPXGqrUNy7Qh4MKHXiKUGMvaLM4GAhgIGJlbaFIZVlV'
API_SECRET = 'avIfwd471KlubRpXNHyV2lH9cgRZLfgGngNvBCx2SyzEDVlTbhGqF2vQqiATGUfc'

TRADES_LIMIT = '100'

logger = logging.getLogger('xmb')


class BinanceApi:

    def get_open_orders(self, currency_1, currency_2):
        try:
            timestamp = BinanceApi._calculateTimestamp()
            url = "/api/" + API_VERSION_3 + "/" + 'openOrders' \
                  + '?symbol='+currency_1+currency_2 + '&timestamp='+str(timestamp)
            data =  BinanceApi._call_binance_api(url,'GET', symbol=currency_1+currency_2, timestamp=timestamp)
            newData = BinanceApi._create_exmo_open_orders(self,data)
            return newData
        except KeyError:
            logger.debug('No open market orders')
            return []

    def get_canceled_orders(self, currency_1, currency_2):
        try:
            timestamp = BinanceApi._calculateTimestamp()
            url = "/api/" + API_VERSION_3 + "/" + 'allOrders' \
                  + '?symbol=' + currency_1 + currency_2 + '&timestamp=' + str(timestamp)
            obj = BinanceApi._call_binance_api(url,'GET',symbol=currency_1+currency_2, timestamp=timestamp)
            newObj = []
            for order in obj:
                if order['status'] is 'CANCELED':
                    newObj.append(order)
            return newObj
        except KeyError:
            return []


    def is_order_partially_completed(self, currency_1, currency_2, order_id):
        try:
            timestamp = BinanceApi._calculateTimestamp()
            url = "/api/" + API_VERSION_3 + "/" + 'order' \
                  + '?orderId=' + str(order_id) + '&symbol=' + currency_1 + currency_2 + '&timestamp=' + str(timestamp)
            status = BinanceApi._call_binance_api(url, 'GET', symbol=currency_1 + currency_2, orderId=order_id,
                                                  timestamp=timestamp)['status']
            if status == 'PARTIALLY_FILLED':
                return True
            else:
                return False
        except KeyError:
            logger.debug('No open market orders from partially_completed')
            return []

    def cancel_order(self, currency_1, currency_2, order_id):
        logger.info('Cancel order %s', order_id)
        timestamp = BinanceApi._calculateTimestamp()
        url = "/api/" + API_VERSION_3 + "/" + 'order'
        data = BinanceApi._call_binance_api(url, 'DELETE', symbol=currency_1 + currency_2, orderId=order_id,
                                     timestamp=timestamp)
        newData = BinanceApi._create_exmo_cancel_orders(self, data, order_id)
        return newData

    def get_balances(self):
        timestamp = BinanceApi._calculateTimestamp()
        url = "/api/" + API_VERSION_3 + "/" + 'account' + '?timestamp=' + str(timestamp)
        return BinanceApi._call_binance_api(url, 'GET', timestamp=timestamp)['balances']


    def create_order(self, currency_1, currency_2, quantity, price, side):
        logger.info('Create %s order (quantity=%s, price=%s)', side, quantity, price)
        timestamp = BinanceApi._calculateTimestamp()
        url = "/api/" + API_VERSION_3 + "/" + 'order'
        orderId = BinanceApi._call_binance_api(
            url, http_method='POST',
            symbol=currency_1 + currency_2,
            quantity=quantity,
            price=price,
            side=side,
            type='LIMIT',
            timestamp=timestamp,
            timeInForce='GTC'
        )['orderId']
        return str(orderId)


    def get_trades(self, currency_1, currency_2):
        url = "/api/" + API_VERSION_1 + "/" + 'trades' + '?symbol=' + currency_1 + currency_2 + '&limit=' + TRADES_LIMIT
        data =  BinanceApi._call_binance_api(url, 'GET')
        newData =  BinanceApi._create_exmo_trades(self,data)
        return newData

    def get_user_trades(self, currency_1, currency_2, offset=0, limit=500):
        timestamp = BinanceApi._calculateTimestamp()
        url = "/api/" + API_VERSION_3 + "/" + 'myTrades' + '?limit=' + str(limit) + '&symbol=' + currency_1 + currency_2 \
              + '&timestamp=' + str(timestamp)
        return BinanceApi._call_binance_api(url, 'GET', limit = limit, symbol=currency_1 + currency_2, timestamp=timestamp)


    @staticmethod
    def _call_binance_api(url, http_method, **kwargs):
        logger.debug('Call Binance api. Url {}. Payload: {}'.format(url, kwargs))

        payload = []
        if kwargs:
             payload = sorted(kwargs.items())
        payload = urllib.parse.urlencode(payload)

        sign = hmac.new(API_SECRET.encode('utf-8'), payload.encode('utf-8'), digestmod=hashlib.sha256).hexdigest()

        if http_method == 'GET':
            if API_VERSION_1 not in url:
                url+= '&signature='+sign
        else:
            payload += '&signature=' + sign

        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "X-MBX-APIKEY": API_KEY,
                   "signature": sign}
        conn = http.client.HTTPSConnection(API_URL, timeout=60)
        conn.request(http_method, url, payload, headers)
        response = conn.getresponse().read()
        conn.close()
        try:
            obj = json.loads(response.decode('utf-8'))
            logger.debug('Received response: {}'.format(response))
            if 'error' in obj and obj['error']:
                raise ApiError(obj['error'])
            if 'code' in obj and obj['code']:
                raise ApiError(obj['code'],obj['msg'])
            print(obj)
            return obj
        except json.decoder.JSONDecodeError:
            raise ApiError('Ошибка анализа возвращаемых данных, получена строка', response)

    @staticmethod
    def _calculateTimestamp():
        return int(round(time.time() * 1000))

    #transform Binance response to Exmo response
    def _create_exmo_open_orders(self, data):
        newData = []
        for obj in data:
            newObj = {}
            newObj['order_id'] = obj['orderId']
            newObj['created'] = obj['time']
            newObj['type'] = obj['side']
            newObj['pair'] = obj['symbol'][:3]+'_'+obj['symbol'][3:]
            newObj['price'] = obj['price']
            newObj['quantity'] = obj['origQty']
            newData.append(newObj)
        return newData

    def _create_exmo_cancel_orders(self, data, orderId):
        newObj = {}
        if data['orderId'] == orderId:
            newObj['result'] = 'true'
            newObj['error'] = ''
        else:
            newObj['result'] = 'false'
            newObj['error'] = 'Some error'
        return newObj


    def _create_exmo_trades(self,data):
        newData = []
        for obj in data:
            newObj = {}
            newObj['trade_id'] = obj['id']
            newObj['date'] = obj['time']
            newObj['price'] = obj['price']
            newObj['quantity'] = obj['qty']
            newData.append(newObj)
        return newData