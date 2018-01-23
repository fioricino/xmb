import json
import os.path
import time

from exmo_api import ExmoApi

if __name__ == '__main__':
    api = ExmoApi()
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
            pass
