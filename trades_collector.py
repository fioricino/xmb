import json
import logging
import os.path
import time

from exmo_api_proxy import ExmoApiProxy

FOLDER = 'trades-2018-02-15'
TRADES_PER_FILE = 1000
TRADES_TO_SAVE = 100


def save_trades(trades, filename):
    with open(os.path.join(FOLDER, '{}.json'.format(filename)), 'w') as f:
        json.dump(trades, f)


if __name__ == '__main__':
    api = ExmoApiProxy('localhost', 9050)
    trades = {}
    os.makedirs(FOLDER, exist_ok=True)
    last_saved = 0
    filename = str(int(time.time()))
    while True:
        try:
            deals = api.get_trades('BTC', 'USD')
            for d in deals:
                trades[d['trade_id']] = d
            if len(trades) - last_saved > TRADES_TO_SAVE:
                save_trades(trades, filename)
                last_saved = len(trades)
            if len(trades) >= TRADES_PER_FILE:
                save_trades(trades, filename)
                trades.clear()
                last_saved = 0
                filename = str(int(time.time()))
            time.sleep(3)
        except:
            logging.exception('Cannot get deals')
            pass
