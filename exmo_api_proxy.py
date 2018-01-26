import json
import logging
import time

import requests

from exceptions import ApiError

API_URL = 'api.exmo.me'
API_VERSION = 'v1'

logger = logging.getLogger('xmb')


class ExmoApiProxy:
    def __init__(self, proxy_host, proxy_port):
        self._proxy_host = proxy_host
        self._proxy_port = proxy_port

    def get_trades(self, currency_1, currency_2):
        return self._call_api('trades', pair=currency_1 + '_' + currency_2)[currency_1 + '_' + currency_2]

    @staticmethod
    def _call_api(api_method, **kwargs):
        logger.debug('Call api via proxy: {}'.format(api_method))
        payload = {'nonce': int(round(time.time() * 1000))}

        if kwargs:
            payload.update(kwargs)
        response = requests.get('http://' + API_URL + "/" + API_VERSION + "/" + api_method, params=payload,
                                proxies=dict(http='socks5://localhost:9050'))

        try:
            obj = json.loads(response.content.decode('utf-8'))
            if 'error' in obj and obj['error']:
                raise ApiError(obj['error'])
            return obj
        except json.decoder.JSONDecodeError:
            raise ApiError('Ошибка анализа возвращаемых данных, получена строка', response)
