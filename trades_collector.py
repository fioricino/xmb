import json
import logging
import os.path
import time

from exmo_api_proxy import ExmoApiProxy

if __name__ == '__main__':
    api = ExmoApiProxy('localhost', 9050)
    trades = {}
    counter = -1
    while True:
        try:
            deals = api.get_trades('BTC', 'USD')
            for d in deals:
                trades[d['trade_id']] = d
            counter += 1
            if counter % 10 == 0:
                with open(os.path.join('history', 'trades.json'), 'w') as f:
                    json.dump(trades, f)
            time.sleep(3)
        except:
            logging.exception('Cannot get deals')
            pass
