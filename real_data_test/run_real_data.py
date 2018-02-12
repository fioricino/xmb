import itertools
import json
import logging
import os
from datetime import datetime

from KDEDealSizer import KDEDealSizer
from calc import Calc
from json_api import JsonStorage

logging.basicConfig(level=logging.INFO)

from exmo_general import Worker
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


# def get_theor_balances(storage, market, stock_fee):
#     balances = dict(market.get_balances())
#     open_orders = [o for o in storage.get_open_orders() if o['status'] == 'OPEN']
#     for order in open_orders:
#         quantity = float(order['order_data']['quantity'])
#         price = float(order['order_data']['price'])
#         if order['order_type'] == 'RESERVE':
#             if order['profile'] == 'UP':
#                 # return USD to balance
#                 balances['USD'] += quantity * price
#             elif order['profile'] == 'DOWN':
#                 balances['BTC'] += quantity
#         elif order['order_type'] == 'PROFIT':
#             if order['profile'] == 'UP':
#                 balances['USD'] += quantity * price * (1 - stock_fee)
#             elif order['profile'] == 'DOWN':
#                 balances['BTC'] += quantity * (1 - stock_fee)
#     return balances


def get_stats(sim, storage, stock_fee):
    calc = Calc(sim, storage, datetime(2000, 1, 1, 0, 0, 0), stock_fee)
    return calc.get_profit()
    # stat = {'USD': sim.balances['USD'], 'BTC': sim.balances['BTC'],
    #         # 'BTC_ord': sim.get_balances_with_orders()['BTC'],
    #         # 'USD_ORD': sim.get_balances_with_orders()['USD'],
    #         'USD_prof': sim.get_profit()['USD'], 'BTC_prof': sim.get_profit()['BTC']
    #         }
    # # 'USD_theor': get_theor_balances(storage, sim, 0.002)['USD'],
    # # 'BTC_theor': get_theor_balances(storage, sim, 0.002)['BTC']}
    # return stat


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
    sim = MarketSimulator('datasets', initial_btc_balance=0.024,
                          initial_usd_balance=200,
                          stock_fee=cfg['stock_fee'], last_deals=cfg['last_deals'],
                          initial_timestamp=cfg['initial_timestamp'])
    # storage = SQLiteStorage(os.path.join(run_folder, 'test.db'))
    storage = JsonStorage(os.path.join(run_folder, 'orders.json'), archive_dir)

    ta = TrendAnalyzer(**cfg)
    ta._current_time = lambda: sim.timestamp

    advisor = InstantAdvisor(sim, ta)
    # ds = ConstDealSizer(**cfg)

    deal_provider = DealsProvider(sim.deals)
    ds = KDEDealSizer(deal_provider, advisor, **cfg)

    timestamp = sim.get_timestamp()
    last_timestamp = sim.get_max_timestamp()
    worker = Worker(sim, storage, advisor, ds,
                    **cfg)
    worker._get_time = lambda: sim.timestamp
    worker._is_order_partially_completed = lambda x, y: False
    worker._is_order_in_trades = lambda x, y: True
    last_stat_timestamp = timestamp
    while timestamp < last_timestamp:
        try:
            timestamp += 1
            logger.debug('Update timestamp: {}'.format(timestamp))
            sim.update_timestamp(timestamp)
            advisor.update_timestamp(timestamp)
            deal_provider.update_timestamp(timestamp)
            worker.main_flow()
            # if timestamp - last_stat_timestamp >= 1000:
            #     logger.info('Stats: {}'.format(get_stats(sim, storage, worker._stock_fee)))
            #     last_stat_timestamp = timestamp
        except:
            logger.exception('Exception')
            break

    ok_deals, stat = get_stats(sim, storage, worker._stock_fee)
    logger.info('Finished.\n{}'.format(stat))
    with open(os.path.join(run_folder, 'stats.json'), 'w') as f:
        json.dump(stat, f, indent=4)
    with open(os.path.join(run_folder, 'ok_deals.json'), 'w') as f:
        json.dump(ok_deals, f, indent=4)
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

    def get_avg_price(self):
        return self.avg_price

    def update_timestamp(self, timestamp):
        if timestamp - self.last_update_ts > self.period:
            self.profile, self.profit_markup, self.reserve_markup, self.avg_price = self._ta.get_profile(
                self._deal_provider.get_trades(None, None))
            self.last_update_ts = timestamp


class DealsProvider:
    def __init__(self, all_deals):
        self.all_deals = all_deals
        self.timestamp = 0
        self.period = 300
        self.last_update_ts = 0
        self.cur_deals = []
        self.index = 0

    def update_timestamp(self, timestamp):
        self.timestamp = timestamp
        if self.timestamp - self.last_update_ts >= self.period:
            self.last_update_ts = timestamp
            while int(self.all_deals[self.index]['date']) < timestamp:
                self.index += 1

    def get_deals(self):
        return self.all_deals[:self.index]


args = {
    'profit_price_avg_price_deviation': [0.001],
    'profit_order_lifetime': [64],
    'stock_fee': [0.002],
    'profit_markup': [0.01],
    'reserve_price_avg_price_deviation': [0.002],
    'profit_price_prev_price_deviation': [0.0001],
    'currency_1_deal_size': [0.001],
    'max_profit_orders_up': [100],
    'max_profit_orders_down': [100],
    'same_profile_order_price_deviation': [0.01],

    'profit_multiplier': [128],
    'mean_price_period': [16],
    'profit_free_weight': [0.01],
    # 'derivative_step': [2, 3, 4, 5],
    'profit_currency_down': ['USD'],
    'profit_currency_up': ['USD'],
    'initial_timestamp': [1518038789],
    # 'target_currency': ['USD'],
    # 'target_profit': [0.5],
    # 'target_period': [2],
    # 'currency_1_max_deal_size': [0.002],
    # 'suspend_order_deviation': [None, 0.03],

    'kde_multiplier': [1],
    'kde_bandwith': [150],
    'kde_days': [7],
    'last_deals': [100]
}

d = [list(zip(itertools.repeat(arg, len(values)), values)) for arg, values in args.items()]
product = list(itertools.product(*d))
configs = [dict(cfg) for cfg in product]
handlers = []
for cfg in configs:
    try:
        handlers = run(cfg, 'test1', handlers)
    except:
        logger.exception('Error')



