from threading import Thread

from exmo_api import ExmoApi
from exmo_general import Worker, Profiles

# run period in seconds
PERIOD = 1
CURRENCY_1 = 'BTC'
CURRENCY_1_DEAL_SIZE = 0.0011
CURRENCY_2 = 'USD'
CURRENCY_2_DEAL_SIZE = 15.9  # Сколько тратить CURRENCY_2 каждый раз при покупке CURRENCY_1
PROFILE = Profiles.UP
STOCK_TIME_OFFSET = 0
ORDER_LIFE_TIME = 0
AVG_PRICE_PERIOD = 60
RESERVE_PRICE_DISTRIBUTION = 0.001
RESERVE_PROFIT_MARKUP = 0.001
SPEND_PROFIT_MARKUP = 0.001

if __name__ == '__main__':
    exmo_api = ExmoApi()
    worker = Worker(exmo_api,
                    period=PERIOD,
                    profile=Profiles.UP,
                    order_life_time=ORDER_LIFE_TIME,
                    avg_price_period=AVG_PRICE_PERIOD,
                    reserve_price_distribution=RESERVE_PRICE_DISTRIBUTION,
                    currency_1_deal_size=CURRENCY_1_DEAL_SIZE,
                    currency_2_deal_size=CURRENCY_2_DEAL_SIZE,
                    reserve_profit_markup=RESERVE_PROFIT_MARKUP,
                    spend_profit_markup=SPEND_PROFIT_MARKUP)
    t = Thread(target=worker.run)
    t.run()
