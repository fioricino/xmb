import itertools
import json
import logging
import os

logging.basicConfig(level=logging.INFO)

from exmo_general import Worker
from json_api import JsonStorage
from real_data_test.market_simulator import MarketSimulator
from trend_analyze import TrendAnalyzer
from logging.handlers import RotatingFileHandler

import shutil

# create logger with 'spam_application'
logger = logging.getLogger('xmb')
logger.setLevel(logging.INFO)
# create file handler which logs even debug messages
# fh = logging.FileHandler('xmb.log')
# fh.setLevel(logging.DEBUG)
# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
# logger.addHandler(fh)
logger.addHandler(ch)


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


def get_stats(sim, storage):
    stat = {'USD': sim.balances['USD'], 'BTC': sim.balances['BTC'], 'BTC_ord': sim.get_balances_with_orders()['BTC'],
            'USD_ORD': sim.get_balances_with_orders()['USD'],
            'USD_prof': storage.get_stats()['UP'], 'BTC_prof': storage.get_stats()['DOWN'],
            'USD_theor': get_theor_balances(storage, sim, 0.002)['USD'],
            'BTC_theor': get_theor_balances(storage, sim, 0.002)['BTC']}
    return stat


def run(cfg, base_folder, handlers):
    folder = ''
    for k in sorted(cfg):
        names = k.split('_')
        for n in names:
            folder += n[0]
        folder += '_'
        folder += str(cfg[k])
        folder += '_'
    run_folder = os.path.join(base_folder, folder)
    shutil.rmtree(run_folder, ignore_errors=True)
    os.makedirs(run_folder, exist_ok=True)

    # run
    for h in handlers:
        logger.removeHandler(h)

    logs_dir = os.path.join(run_folder, 'logs')
    os.makedirs(logs_dir)
    handlers = create_handlers(logs_dir)
    archive_dir = os.path.join(run_folder, 'archive')
    os.makedirs(archive_dir)
    sim = MarketSimulator('deals_5day', initial_btc_balance=cfg['max_profit_orders_down'] * 0.0011,
                          initial_usd_balance=cfg['max_profit_orders_up'] * 13,
                          stock_fee=cfg['stock_fee'], last_deals=cfg['last_deals'])
    storage = JsonStorage(os.path.join(run_folder, 'orders.json'), archive_dir)

    ta = TrendAnalyzer(**cfg)
    ta._current_time = lambda: sim.timestamp

    advisor = InstantAdvisor(sim, ta)
    timestamp = sim.get_timestamp()
    last_timestamp = sim.get_max_timestamp()
    worker = Worker(sim, storage, advisor,
                    **cfg)
    worker._get_time = lambda: sim.timestamp
    last_stat_timestamp = timestamp
    while timestamp < last_timestamp:
        try:
            timestamp += 1
            logger.debug('Update timestamp: {}'.format(timestamp))
            sim.update_timestamp(timestamp)
            advisor.update_timestamp(timestamp)
            worker.main_flow()
            if timestamp - last_stat_timestamp >= 1000:
                logger.info('Stats: {}'.format(get_stats(sim, storage)))
                last_stat_timestamp = timestamp
        except:
            break

    stat = get_stats(sim, storage)
    logger.info('Finished.\n{}'.format(stat))
    with open(os.path.join(run_folder, 'stats.json'), 'w') as f:
        json.dump(stat, f, indent=4)
    return handlers


def create_handlers(dr):
    debug_handler = RotatingFileHandler(os.path.join(dr, 'xmb_debug.log'), maxBytes=10000000, backupCount=1000)
    debug_handler.setLevel(logging.INFO)
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

class InstantAdvisor:
    def __init__(self, deal_provider, trend_analyzer):
        self._ta = trend_analyzer
        self._deal_provider = deal_provider
        self.period = 5
        self.timestamp = 0
        self.last_update_ts = 0

    def get_advice(self):
        return self.profile, self.profit_markup, self.reserve_markup, self.avg_price

    def update_timestamp(self, timestamp):
        if timestamp - self.last_update_ts > self.period:
            self.profile, self.profit_markup, self.reserve_markup, self.avg_price = self._ta.get_profile(
                self._deal_provider.get_trades(None, None))
            self.last_update_ts = timestamp


args = {
    'profit_price_avg_price_deviation': [0.001],
    'profit_order_lifetime': [128],
    'period': [1],
    'currency_1': ['BTC'],
    'currency_2': ['USD'],
    'stock_fee': [0.002],
    'profit_markup': [0.002],
    'reserve_price_avg_price_deviation': [0.002],
    'profit_price_prev_price_deviation': [0.0001],
    'currency_1_deal_size': [0.001],
    'max_profit_orders_up': [10],
    'max_profit_orders_down': [10],
    'same_profile_order_price_deviation': [0.01],

    'rolling_window': [6],
    'profit_multiplier': [192],
    'mean_price_period': [4],
    'interpolation_degree': [20],
    'profit_free_weight': [0.0016],
    'reserve_multiplier': [0],

    'last_deals': [100]
}

d = [list(zip(itertools.repeat(arg, len(values)), values)) for arg, values in args.items()]
product = list(itertools.product(*d))
configs = [dict(cfg) for cfg in product]
handlers = []
for cfg in configs:
    try:
        handlers = run(cfg, 'test_5day', handlers)
    except:
        logger.exception('Error')









#
# if __name__ == '__main__':
#     base_dir = os.path.join('results', 'fixarchive')
#     os.makedirs(base_dir, exist_ok=True)
#     handlers = []
#     for last_deals in LAST_DEALS:
#         last_deals_dir = os.path.join(base_dir, 'last_deals_{}'.format(last_deals))
#         os.makedirs(last_deals_dir, exist_ok=True)
#         for rolling_window in ROLLING_WINDOWS:
#             rolling_window_dir = os.path.join(last_deals_dir, 'rolling_window_{}'.format(rolling_window))
#             os.makedirs(rolling_window_dir, exist_ok=True)
#
#             for new_order_price_deviation in NEW_ORDER_PRICE_DISTRIBUTIONS:
#                 price_deviation_dir = os.path.join(rolling_window_dir,
#                                                    'price_deviation_{}'.format(new_order_price_deviation))
#                 os.makedirs(price_deviation_dir, exist_ok=True)
#                 for profit_lifetime in PROFIT_LIFETIMES:
#                     profit_lifetime_dir = os.path.join(price_deviation_dir,
#                                                        'profit_lifetime_{}'.format(profit_lifetime))
#                     os.makedirs(profit_lifetime_dir, exist_ok=True)
#                     for profit_price_dev in PROFIT_PRICE_DEVIATIONS:
#                         profit_price_dev_dir = os.path.join(profit_lifetime_dir,
#                                                             'profit_price_dev_{}'.format(profit_price_dev))
#                         os.makedirs(profit_price_dev_dir, exist_ok=True)
#                         for profit_free_weight in PROFIT_FREE_WEIGHTS:
#                             profit_free_weight_dir = os.path.join(profit_price_dev_dir,
#                                                                   'profit_free_weight_{}'.format(profit_free_weight))
#                             os.makedirs(profit_free_weight_dir, exist_ok=True)
#                             for profit_multiplier in PROFIT_MULTIPLIERS:
#                                 profit_multiplier_dir = os.path.join(profit_free_weight_dir,
#                                                                      'profit_multiplier_{}'.format(profit_multiplier))
#                                 shutil.rmtree(profit_multiplier_dir, ignore_errors=True)
#                                 os.makedirs(profit_multiplier_dir)
#                                 for h in handlers:
#                                     logger.removeHandler(h)
#
#                                 logs_dir = os.path.join(profit_multiplier_dir, 'logs')
#                                 os.makedirs(logs_dir)
#                                 handlers = create_handlers(logs_dir)
#                                 archive_dir = os.path.join(profit_multiplier_dir, 'archive')
#                                 os.makedirs(archive_dir)
#                                 sim = MarketSimulator('deals_2day', initial_btc_balance=INITIAL_BTC_BALANCE,
#                                                       initial_usd_balance=INITIAL_USD_BALANCE,
#                                                       stock_fee=0.002, last_deals=last_deals)
#                                 storage = JsonStorage(os.path.join(profit_multiplier_dir, 'orders.json'), archive_dir)
#
#                                 ta = TrendAnalyzer(rolling_window=rolling_window, profit_multiplier=profit_multiplier,
#                                                    reserve_multiplier=0,
#                                                    mean_price_period=4, profit_free_weight=profit_free_weight)
#                                 ta._current_time = lambda: sim.timestamp
#
#                                 advisor = InstantAdvisor(sim, ta)
#                                 timestamp = sim.get_timestamp()
#                                 last_timestamp = sim.get_max_timestamp()
#                                 worker = Worker(sim, storage, advisor,
#                                                 same_profile_order_price_deviation=new_order_price_deviation,
#                                                 profit_order_lifetime=profit_lifetime,
#                                                 profit_markup=PROFIT_MARKUP, max_profit_orders_down=5,
#                                                 max_profit_orders_up=5,
#                                                 profit_price_prev_price_deviation=profit_price_dev,
#                                                 reserve_price_avg_price_deviation=0.002)
#                                 worker._get_time = lambda: sim.timestamp
#                                 last_stat_timestamp = timestamp
#                                 while timestamp < last_timestamp:
#                                     timestamp += 1
#                                     logger.debug('Update timestamp: {}'.format(timestamp))
#                                     sim.update_timestamp(timestamp)
#                                     advisor.update_timestamp(timestamp)
#                                     worker.main_flow()
#                                     if timestamp - last_stat_timestamp >= 1000:
#                                         logger.info('Stats: {}'.format(get_stats()))
#                                         last_stat_timestamp = timestamp
#
#                                 stat = get_stats()
#                                 logger.info('Finished.\n{}'.format(stat))
#                                 with open(os.path.join(profit_multiplier_dir, 'stats.json'), 'w') as f:
#                                     json.dump(stat, f, indent=4)
