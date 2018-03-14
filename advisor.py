import logging
import time
from threading import Thread

logger = logging.getLogger('xmb')

class BackgroundStatAdvisor:
    def __init__(self, trend_analyzer, market_api, period=300, currency_1='BTC', currency_2='USD'):
        self._trend_analyzer = trend_analyzer
        self._market_api = market_api
        self._period = period
        self._currency_1 = currency_1
        self._currency_2 = currency_2
        self._data = None
        self.run_in_new_thread()

    def run(self):
        self._interrupted = False
        while not self._interrupted:
            try:
                self.update_advice()
                time.sleep(self._period)
            except Exception as e:
                logger.error(str(e))

    def stop_background_process(self):
        self._interrupted = True

    def update_advice(self):
        # deals = self._market_api.get_trades(self._currency_1, self._currency_2)
        self._data = (self._trend_analyzer.get_deal_size())
        i = 0

    def get_advice(self):
        return self._data

    def run_in_new_thread(self):
        thread = Thread(target=self.run)
        thread.start()
