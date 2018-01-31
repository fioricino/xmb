import logging
import os
from logging.handlers import RotatingFileHandler
from threading import Thread

from advisor import BackgroundStatAdvisor
from exmo_api import ExmoApi
from exmo_api_proxy import ExmoApiProxy
from exmo_general import Worker

# run period in seconds
from json_api import JsonStorage
from trend_analyze import TrendAnalyzer

logger = logging.getLogger('xmb')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
# fh = logging.FileHandler('xmb.log')
# fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
# logger.addHandler(fh)
logger.addHandler(ch)


def create_handlers(dr):
    debug_handler = RotatingFileHandler(os.path.join(dr, 'xmb_debug.log'), maxBytes=10000000, backupCount=1000)
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(formatter)
    logger.addHandler(debug_handler)
    info_handler = RotatingFileHandler(os.path.join(dr, 'xmb_info.log'), maxBytes=10000000, backupCount=1000)
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    logger.addHandler(info_handler)
    error_handler = RotatingFileHandler(os.path.join(dr, 'xmb_error.log'), maxBytes=10000000, backupCount=1000)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    return [debug_handler, info_handler, error_handler]


create_handlers(os.path.join('real_run', 'logs'))
args = {
    'profit_price_avg_price_deviation': 0.001,
    'profit_order_lifetime': 64,
    'period': 1,
    'currency_1': 'BTC',
    'currency_2': 'USD',
    'stock_fee': 0.002,
    'profit_markup': 0.001,
    'reserve_price_avg_price_deviation': 0.002,
    'profit_price_prev_price_deviation': 0.0001,
    'currency_1_deal_size': 0.001,
    'max_profit_orders_up': 3,
    'max_profit_orders_down': 3,
    'same_profile_order_price_deviation': 0.01
}

stat_args = {
    'rolling_window': 6,
    'profit_multiplier': 64,
    'mean_price_period': 4,
    'interpolation_degree': 20,
    'profit_free_weight': 0.0008,
    'reserve_multiplier': 0,
}


if __name__ == '__main__':
    exmo_api = ExmoApi()
    exmo_public_api = ExmoApiProxy(proxy_host='localhost', proxy_port=9050)

    storage = JsonStorage(order_file=os.path.join('real_run', 'orders.json'),
                          archive_folder=os.path.join('real_run', 'archive'))

    trend_analyzer = TrendAnalyzer(**stat_args)

    advisor = BackgroundStatAdvisor(trend_analyzer, exmo_public_api, period=1)
    worker = Worker(exmo_api,
                    storage,
                    advisor,
                    **args)
    t = Thread(target=worker.run)
    t.run()
