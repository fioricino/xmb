import logging
import os

logging.basicConfig(level=logging.DEBUG)

from exmo_general import Worker
from json_api import JsonStorage
from real_data_test.market_simulator import MarketSimulator
from trend_analyze import TrendAnalyzer
from logging.handlers import RotatingFileHandler

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
debug_handler = RotatingFileHandler(os.path.join('logs', 'xmb_debug.log'), maxBytes=10000000, backupCount=1000)
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(formatter)
logger.addHandler(debug_handler)

info_handler = RotatingFileHandler(os.path.join('logs', 'xmb_info.log'), maxBytes=10000000, backupCount=1000)
info_handler.setLevel(logging.INFO)
info_handler.setFormatter(formatter)
logger.addHandler(info_handler)

error_handler = RotatingFileHandler(os.path.join('logs', 'xmb_error.log'), maxBytes=10000000, backupCount=1000)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(formatter)
logger.addHandler(error_handler)

INITIAL_BTC_BALANCE = 0.01
INITIAL_USD_BALANCE = 150
ROLLING_WINDOW = 6
PROFIT_MULTIPLIER = 32
MEAN_PRICE_PERIOD = 10


class InstantAdvisor:
    def __init__(self, deal_provider):
        self._ta = TrendAnalyzer(rolling_window=ROLLING_WINDOW, profit_multiplier=PROFIT_MULTIPLIER,
                                 mean_price_period=MEAN_PRICE_PERIOD)
        self._ta._current_time = lambda: self.timestamp
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





if __name__ == '__main__':

    sim = MarketSimulator('deals', initial_btc_balance=INITIAL_BTC_BALANCE, initial_usd_balance=INITIAL_USD_BALANCE,
                          stock_fee=0.002)
    storage = JsonStorage('orders.json', 'archive')
    advisor = InstantAdvisor(sim)
    timestamp = sim.get_timestamp()
    last_timestamp = sim.get_max_timestamp()
    worker = Worker(sim, storage, advisor)
    worker._get_time = lambda: sim.timestamp
    last_stat_timestamp = timestamp
    while timestamp < last_timestamp:
        timestamp += 1
        logger.debug('Update timestamp: {}'.format(timestamp))
        sim.update_timestamp(timestamp)
        advisor.update_timestamp(timestamp)
        worker.main_flow()
        if timestamp - last_stat_timestamp >= 3600:
            logger.info('Stats: {}'.format(storage.get_stats()))
            last_stat_timestamp = timestamp

logger.info('Finished. Balances: {}\nBalances (with orders): {}\nStats: {}\nOrders:\n{}'.format(sim.balances,
                                                                                                sim.balances_in_orders,
                                                                                                storage.get_stats(),
                                                                                                storage.orders))
