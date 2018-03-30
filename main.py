import argparse
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from threading import Thread

from advisor import BackgroundStatAdvisor
from disk_deal_reader import DiskDealReader
from exmo_api import ExmoApi
from exmo_api_proxy import ExmoApiProxy
from exmo_general import Worker

# run period in seconds
from sqlite_api import SQLiteStorage
from trend_deal_sizer import TrendDealSizer

logger = logging.getLogger('xmb')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
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
    'period': 1,
    'currency_1': 'BTC',
    'currency_2': 'USD',
    'stock_fee': 0.002,
    'profit_markup': 0.05,
    'reserve_price_avg_price_deviation': 0.002,
    'currency_1_deal_size': 0.002,
    'max_profit_orders_up': 100,
    'max_profit_orders_down': 100,
    'same_profile_order_price_deviation': 0.01,
    'same_profile_order_same_direction_price_deviation': 0.01,
    'profit_currency_down': 'BTC',
    'profit_currency_up': 'USD',
    'profit_multiplier': 0,
    'mean_price_period': 16,
    'deal_read_days': 4,
    'trend_diff_hours': 2,
    'trend_rolling_window': 4000,
    'trend_days': 3,
    'trend_multiplier': 60,
    'currency_1_min_deal_size': 0.001,
    'suspend_price_deviation': 0.05,
    'suspend_price_up_down_deviation': 0.01,
    'trend_max_deal_size': 0.0025,
    'trend_min_deal_size': 0.0025
}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-k', '--key', type=str, help='Api key')
    parser.add_argument('-s', '--secret', type=str, help='Api secret')
    sysargs = parser.parse_args(sys.argv[1:])

    exmo_api = ExmoApi(sysargs.key, sysargs.secret)
    exmo_public_api = ExmoApiProxy(proxy_host='localhost', proxy_port=9050)

    # storage = JsonStorage(order_file=os.path.join('real_run', 'orders.json'),
    #                       archive_folder=os.path.join('real_run', 'archive'))

    storage = SQLiteStorage(os.path.join('real_run', 'orders.db'))

    dp = DiskDealReader(r'C:\Users\ozavorot\Documents\GitHub\xmb\trades-2018-02-15', **args)
    ds = TrendDealSizer(dp, **args)

    advisor = BackgroundStatAdvisor(ds, exmo_public_api, period=300)

    worker = Worker(exmo_api,
                    storage,
                    advisor,
                    **args)
    t = Thread(target=worker.run)
    t.run()
