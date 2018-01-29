import hashlib
import http.client
import json
import urllib.parse

import requests
import hmac

import time

from binance_api import BinanceApi

API_URL = 'api.binance.com'

API_KEY = 'HegeFPcysaLj8SMJYvEt5oE0gbJucrymRo91bnw8c5xRQ0pGotwn7Y58EPlF4KrZ'
API_SECRET = b'htTDnjZNJUroN7WydpP7OdKaQd95CywKHsWUMGEkVLuR8SK3VZJOHreOp2ilp0kM'

if __name__ == '__main__':
    api = BinanceApi()

    # api.prices()
    # api.get_open_orders('ETC','ETH')
    # for x in range(1,10):
    # api.get_canceled_orders('LTC','BTC')
    # api.is_order_partially_completed('ETC','ETH',7117404)
    # api.cancel_order('ETC','ETH',7119929)
    # api.get_balances()
    # api.create_order('ETC','ETH',0.08,0.5,'SELL')
    api.get_trades('ETC','ETH')
    # api.get_user_trades('BTC','USDT',0,500)

# def prices(self):
#     """Get latest prices for all symbols."""

# payload = {'nonce': int(round(time.time() * 1000))}
# payload = urllib.parse.urlencode(payload)
# H = hmac.new(key=API_SECRET, digestmod=hashlib.sha512)
# sign = H.hexdigest()
#
# headers = {"Content-type": "application/x-www-form-urlencoded",
#            "Key": API_KEY,
#            "Sign": sign}
# conn = http.client.HTTPSConnection(API_URL, timeout=60)
# # data = conn.request("GET", "/api/v1/ticker/allPrices", payload, headers)
# conn.request("GET", "/api/v1/ticker/allPrices")
# data = conn.getresponse().read()
# conn.close()
# return {d["symbol"]: d["price"] for d in data}


# r = requests.get('https://api.binance.com/api/v1/ticker/allPrices')
# obj = json.loads(r.text)
# print(obj)
