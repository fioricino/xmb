import hashlib
import hmac
import http.client
import json
import logging
import time
import urllib
import urllib.parse

from exceptions import ApiError

API_URL = 'api.exmo.me'
API_VERSION = 'v1'

logger = logging.getLogger('xmb')

class ExmoApi:

    def __init__(self, api_key, api_secret):
        self._api_key = api_key
        self._api_secret = api_secret.encode('ascii')

    def get_open_orders(self, currency_1, currency_2):
        try:
            return self._call_api('user_open_orders')[currency_1 + '_' + currency_2]
        except KeyError:
            logger.debug('No open market orders')
            return []

    def get_canceled_orders(self, currency_1, currency_2):
        try:
            return self._call_api('user_cancelled_orders')[currency_1 + '_' + currency_2]
        except KeyError:
            return []

    def is_order_partially_completed(self, order_id):
        try:
            trades = self._call_api('order_trades', order_id=order_id)
        except Exception as e:
            if 'Error 50304' in str(e):
                return False
            else:
                raise e
        return True

    def cancel_order(self, order_id):
        logger.info('Cancel order %s', order_id)
        return self._call_api('order_cancel', order_id=order_id)

    def get_balances(self):
        return self._call_api('user_info')['balances']

    def create_order(self, currency_1, currency_2, quantity, price, type):
        logger.info('Create %s order (quantity=%s, price=%s)', type, quantity, price)
        return str(self._call_api(
            'order_create',
            pair=currency_1 + '_' + currency_2,
            quantity=quantity,
            price=price,
            type=type
        )['order_id'])

    def get_trades(self, currency_1, currency_2):
        return self._call_api('trades', pair=currency_1 + '_' + currency_2)[currency_1 + '_' + currency_2]

    def get_user_trades(self, currency_1, currency_2, offset=0, limit=100):
        return self._call_api('user_trades', pair=currency_1 + '_' + currency_2, offset=offset, limit=limit)[
            currency_1 + '_' + currency_2]

    def _call_api(self, api_method, http_method="POST", **kwargs):
        logger.debug('Call Exmo api. Method {}. Payload: {}'.format(api_method, kwargs))
        payload = {'nonce': int(round(time.time() * 1000))}

        if kwargs:
            payload.update(kwargs)
        payload = urllib.parse.urlencode(payload)

        H = hmac.new(key=self._api_secret, digestmod=hashlib.sha512)
        H.update(payload.encode('utf-8'))
        sign = H.hexdigest()

        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Key": self._api_key,
                   "Sign": sign}
        conn = http.client.HTTPSConnection(API_URL, timeout=60)
        conn.request(http_method, "/" + API_VERSION + "/" + api_method, payload, headers)
        response = conn.getresponse().read()
        conn.close()
        try:
            obj = json.loads(response.decode('utf-8'))
            logger.debug('Received response: {}'.format(response))
            if 'error' in obj and obj['error']:
                raise ApiError(obj['error'])
            return obj
        except json.decoder.JSONDecodeError:
            raise ApiError('Ошибка анализа возвращаемых данных, получена строка', response)
