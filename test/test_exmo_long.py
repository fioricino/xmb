import unittest

from exmo_general import Worker, Profiles


class InstantApi:
    def __init__(self, btc_balance, usd_balance, stock_fee, trades):
        self.balances = {'BTC': btc_balance, 'USD': usd_balance}
        self.stock_fee = stock_fee
        self.trades = trades
        self.trades_index = -1;

    def get_open_orders(self, currency_1, currency_2):
        return []

    def is_order_partially_completed(self, order_id):
        return False

    def cancel_order(self, order_id):
        print('Cancel order')

    def get_balances(self):
        return self.balances

    def create_order(self, currency_1, currency_2, quantity, price, type):
        if type == 'buy':
            print('Buy {} BTC for price {}'.format(quantity, price))
            self.balances['BTC'] += quantity * (1 - self.stock_fee)
            self.balances['USD'] -= quantity * price
        elif type == 'sell':
            print('Sell {} BTC for price {}'.format(quantity, price))
            self.balances['BTC'] -= quantity
            self.balances['USD'] += quantity * price * (1 - self.stock_fee)
        return {'order_id': 'test'}

    def get_trades(self, currency_1, currency_2):
        for trade in self.trades:
            yield [trade]


class TestExmoLong(unittest.TestCase):
    def test_instant_api(self):
        api = InstantApi(btc_balance=0.00116486, usd_balance=18.52,
                         stock_fee=0.002, trades=None)
        api.create_order('BTC', 'USD', type='buy', quantity=0.001, price=13450)
        api.create_order('BTC', 'USD', type='sell', quantity=0.001, price=13508.30527)
        self.assertAlmostEqual(0.00116286, api.balances['BTC'], 8)
        self.assertAlmostEqual(18.55, api.balances['USD'], 2)

    def test_up(self):
        initial_usd_balance = 100
        api = InstantApi(btc_balance=0, usd_balance=initial_usd_balance, stock_fee=0.1, trades=None)
        worker = Worker(api, profile=Profiles.UP, stock_fee=0.1, reserve_profit_markup=0.1,
                        spend_profit_markup=0.1, currency_2_deal_size=100, currency_1_min_deal_size=1)
        current_price = 10

        def get_avg_price():
            nonlocal current_price
            current_price += 1
            return current_price

        worker.get_avg_price = get_avg_price

        for i in range(100):
            worker.main_flow()
        print(api.balances)
        self.assertTrue(api.balances['USD'] > initial_usd_balance)

    def test_down(self):
        initial_btc_balance = 10
        api = InstantApi(btc_balance=initial_btc_balance, usd_balance=0, stock_fee=0.1, trades=None)
        worker = Worker(api, profile=Profiles.DOWN, stock_fee=0.1, reserve_profit_markup=0.1,
                        spend_profit_markup=0.1, currency_1_deal_size=10, currency_1_min_deal_size=1)
        current_price = 100

        def get_avg_price():
            nonlocal current_price
            current_price -= 1
            return current_price

        worker.get_avg_price = get_avg_price

        for i in range(100):
            worker.main_flow()
        print(api.balances)
        self.assertTrue(api.balances['BTC'] > initial_btc_balance)

    def test_up_natural(self):
        initial_usd_balance = 100
        api = InstantApi(btc_balance=0, usd_balance=initial_usd_balance, stock_fee=0.002, trades=None)
        worker = Worker(api, profile=Profiles.UP, stock_fee=0.002, reserve_profit_markup=0.001,
                        spend_profit_markup=0.001, currency_2_deal_size=100, currency_1_min_deal_size=0.001)
        current_price = 10000

        def get_avg_price():
            nonlocal current_price
            current_price *= 1.0035
            return current_price

        worker.get_avg_price = get_avg_price

        for i in range(100):
            worker.main_flow()
        print(api.balances)
        self.assertTrue(api.balances['USD'] > initial_usd_balance)

    def test_down_natural(self):
        initial_btc_balance = 0.01
        api = InstantApi(btc_balance=initial_btc_balance, usd_balance=0, stock_fee=0.002, trades=None)
        worker = Worker(api, profile=Profiles.DOWN, stock_fee=0.002, reserve_profit_markup=0.001,
                        spend_profit_markup=0.001, currency_1_deal_size=0.01, currency_1_min_deal_size=0.001)
        current_price = 15000

        def get_avg_price():
            nonlocal current_price
            current_price *= 0.9965
            return current_price

        worker.get_avg_price = get_avg_price

        for i in range(100):
            worker.main_flow()
        print(api.balances)
        self.assertTrue(api.balances['BTC'] > initial_btc_balance)


if __name__ == '__main__':
    unittest.main()
