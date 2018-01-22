import hashlib
import hmac
import http.client
import json
import logging
import time
import urllib
import urllib.parse

from exceptions import ApiError

API_KEY = ''
API_SECRET = b''

API_URL = 'api.exmo.me'
API_VERSION = 'v1'


class ExmoApi:
    def get_open_orders(self, currency_1, currency_2):
        try:
            return ExmoApi._call_api('user_open_orders')[currency_1 + '_' + currency_2]
        except KeyError:
            logging.debug('Открытых ордеров нет')
            return []

    def is_order_partially_completed(self, order_id):
        try:
            trades = ExmoApi._call_api('order_trades', order_id=order_id)
        except ApiError as e:
            if 'Error 50304' in str(e):
                return False
            else:
                raise e
        return True

    def cancel_order(self, order_id):
        return ExmoApi._call_api('order_cancel', order_id)

    def get_balances(self):
        return ExmoApi._call_api('user_info')['balances']

    def create_order(self, currency_1, currency_2, quantity, price, type):
        return ExmoApi._call_api(
            'order_create',
            pair=currency_1 + '_' + currency_2,
            quantity=quantity,
            price=price,
            type=type
        )

    def get_trades(self, currency_1, currency_2):
        return ExmoApi._call_api('trades', pair=currency_1 + '_' + currency_2)[currency_1 + '_' + currency_2]

    @staticmethod
    def _call_api(api_method, http_method="POST", **kwargs):
        payload = {'nonce': int(round(time.time() * 1000))}

        if kwargs:
            payload.update(kwargs)
        payload = urllib.parse.urlencode(payload)

        H = hmac.new(key=API_SECRET, digestmod=hashlib.sha512)
        H.update(payload.encode('utf-8'))
        sign = H.hexdigest()

        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Key": API_KEY,
                   "Sign": sign}
        conn = http.client.HTTPSConnection(API_URL, timeout=60)
        conn.request(http_method, "/" + API_VERSION + "/" + api_method, payload, headers)
        response = conn.getresponse().read()
        conn.close()
        try:
            obj = json.loads(response.decode('utf-8'))
            if 'error' in obj and obj['error']:
                raise ApiError(obj['error'])
            return obj
        except json.decoder.JSONDecodeError:
            raise ApiError('Ошибка анализа возвращаемых данных, получена строка', response)
