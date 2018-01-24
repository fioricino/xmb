import logging
import os
from threading import Thread

from exmo_api import ExmoApi
from exmo_general import Worker

# run period in seconds
from json_api import JsonStorage

PERIOD = 1
CURRENCY_1 = 'BTC'
CURRENCY_1_DEAL_SIZE = 0.001
CURRENCY_2 = 'USD'
PROFILE = 'UP'
AVG_PRICE_PERIOD = 60
RESERVE_PRICE_DISTRIBUTION = 0.001
PROFIT_MARKUP = 0.001

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exmo_api = ExmoApi()
    storage = JsonStorage(order_file=os.path.join('data', 'orders.json'), archive_folder='archive')
    worker = Worker(exmo_api,
                    storage,
                    period=PERIOD,
                    reserve_price_distribution=RESERVE_PRICE_DISTRIBUTION,
                    currency_1_deal_size=CURRENCY_1_DEAL_SIZE,
                    profit_markup=PROFIT_MARKUP)
    t = Thread(target=worker.run)
    t.run()
