import json
import logging
import os.path
import time

from binance_api import BinanceApi

FOLDER = 'trades-binance'
TRADES_PER_FILE = 1000

if __name__ == '__main__':
    api = BinanceApi()
    trades = {}
    os.makedirs(FOLDER, exist_ok=True)
    while True:
        try:
            deals = api.get_trades('BTC', 'USDT')
            for d in deals:
                trades[d['trade_id']] = d
            if len(trades) >= TRADES_PER_FILE:
                with open(os.path.join(FOLDER, '{}.json'.format(int(time.time()))), 'w') as f:
                    json.dump(trades, f)
                trades.clear()
            time.sleep(3)
        except:
            logging.exception('Cannot get deals')
            pass
