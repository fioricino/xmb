import json
import logging
import os.path
import time

from exmo_api_proxy import ExmoApiProxy

FOLDER = 'trades-2018-02-15'
TRADES_PER_FILE = 1000

if __name__ == '__main__':
    api = ExmoApiProxy('localhost', 9050)
    trades = {}
    os.makedirs(FOLDER, exist_ok=True)
    while True:
        try:
            deals = api.get_trades('BTC', 'USD')
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
