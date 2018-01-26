import json
import logging
import os

logging.basicConfig(level=logging.DEBUG)

from exmo_general import Worker
from json_api import JsonStorage
from real_data_test.market_simulator import MarketSimulator
from trend_analyze import TrendAnalyzer
from logging.handlers import RotatingFileHandler

import shutil

# create logger with 'spam_application'
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


INITIAL_BTC_BALANCE = 0.01
INITIAL_USD_BALANCE = 150
ROLLING_WINDOW = 6
PROFIT_MULTIPLIER = 64
MEAN_PRICE_PERIOD = 4
PROFIT_ORDER_PRICE_DEVIATION = 0.025
PROFIT_MARKUP = 0.001

class InstantAdvisor:
    def __init__(self, deal_provider, trend_analyzer):
        self._ta = trend_analyzer
        self._deal_provider = deal_provider
        self.period = 5
        self.timestamp = 0
        self.last_update_ts = 0

    def get_advice(self):
        return self.profile, self.profit_markup, self.avg_price

    def update_timestamp(self, timestamp):
        if timestamp - self.last_update_ts > self.period:
            self.profile, self.profit_markup, self.avg_price = self._ta.get_profile(
                self._deal_provider.get_trades(None, None))
            self.last_update_ts = timestamp


PROFIT_MULTIPLIERS = [16, 32, 48, 64, 96, 128]
MEAN_PRICE_PERIODS = [4]
PROFIT_MARKUPS = [0.001]


def get_theor_balances(storage, market, stock_fee):
    balances = dict(market.get_balances())
    open_orders = [o for o in storage.get_open_orders() if o['status'] == 'OPEN']
    for order in open_orders:
        quantity = float(order['order_data']['quantity'])
        price = float(order['order_data']['price'])
        if order['order_type'] == 'RESERVE':
            if order['profile'] == 'UP':
                # return USD to balance
                balances['USD'] += quantity * price
            elif order['profile'] == 'DOWN':
                balances['BTC'] += quantity
        elif order['order_type'] == 'PROFIT':
            if order['profile'] == 'UP':
                balances['USD'] += quantity * price * (1 - stock_fee)
            elif order['profile'] == 'DOWN':
                balances['BTC'] += quantity * (1 - stock_fee)
    return balances


def get_stats():
    stat = {'USD': sim.balances['USD'], 'BTC': sim.balances['BTC'], 'BTC_ord': sim.get_balances_with_orders()['BTC'],
            'USD_ORD': sim.get_balances_with_orders()['USD'],
            'USD_prof': storage.get_stats()['UP'], 'BTC_prof': storage.get_stats()['DOWN'],
            'USD_theor': get_theor_balances(storage, sim, 0.002)['USD'],
            'BTC_theor': get_theor_balances(storage, sim, 0.002)['BTC']}
    return stat


if __name__ == '__main__':
    base_dir = 'results'
    handlers = []
    for mean_price_period in MEAN_PRICE_PERIODS:
        mean_price_dir = os.path.join(base_dir, 'mean_price_period_{}'.format(mean_price_period))
        os.makedirs(mean_price_dir, exist_ok=True)
        for profit_markup in PROFIT_MARKUPS:
            profit_markup_dir = os.path.join(mean_price_dir, 'profit_markup_{}'.format(profit_markup))
            os.makedirs(profit_markup_dir, exist_ok=True)
            for profit_multiplier in PROFIT_MULTIPLIERS:
                profit_multiplier_dir = os.path.join(profit_markup_dir,
                                                     'profit_multiplier_{}'.format(profit_multiplier))
                shutil.rmtree(profit_multiplier_dir, ignore_errors=True)
                os.makedirs(profit_multiplier_dir)
                for h in handlers:
                    logger.removeHandler(h)

                logs_dir = os.path.join(profit_multiplier_dir, 'logs')
                os.makedirs(logs_dir)
                handlers = create_handlers(logs_dir)
                archive_dir = os.path.join(profit_multiplier_dir, 'archive')
                os.makedirs(archive_dir)
                sim = MarketSimulator('deals', initial_btc_balance=INITIAL_BTC_BALANCE,
                                      initial_usd_balance=INITIAL_USD_BALANCE,
                                      stock_fee=0.002)
                storage = JsonStorage(os.path.join(profit_multiplier_dir, 'orders.json'), archive_dir)

                ta = TrendAnalyzer(rolling_window=ROLLING_WINDOW, profit_multiplier=profit_multiplier,
                                   mean_price_period=mean_price_period)
                ta._current_time = lambda: sim.timestamp

                advisor = InstantAdvisor(sim, ta)
                timestamp = sim.get_timestamp()
                last_timestamp = sim.get_max_timestamp()
                worker = Worker(sim, storage, advisor, profit_order_price_deviation=PROFIT_ORDER_PRICE_DEVIATION,
                                profit_markup=PROFIT_MARKUP)
                worker._get_time = lambda: sim.timestamp
                last_stat_timestamp = timestamp
                while timestamp < last_timestamp:
                    timestamp += 1
                    logger.debug('Update timestamp: {}'.format(timestamp))
                    sim.update_timestamp(timestamp)
                    advisor.update_timestamp(timestamp)
                    worker.main_flow()
                    if timestamp - last_stat_timestamp >= 1000:
                        logger.info('Stats: {}'.format(get_stats()))
                        last_stat_timestamp = timestamp

                stat = get_stats()
                logger.info('Finished.\n{}'.format(stat))
                with open(os.path.join(profit_multiplier_dir, 'stats.json'), 'w') as f:
                    json.dump(stat, f, indent=4)
