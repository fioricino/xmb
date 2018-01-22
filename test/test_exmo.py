import time
import unittest

from exmo_general import Worker, Profiles


class TestWorker(unittest.TestCase):
    def test_get_avg_price(self):
        class ApiMock:
            def get_trades(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    return [{'date': str(int(time.time()) - 100), 'amount': 200, 'quantity': 1},
                            {'date': str(int(time.time()) - 200), 'amount': 400, 'quantity': 2},
                            {'date': str(int(time.time()) - 100), 'amount': 500, 'quantity': 4},
                            {'date': str(int(time.time()) - 100), 'amount': 300, 'quantity': 2},
                            {'date': str(int(time.time()) - 100), 'amount': 100, 'quantity': 1},
                            # must be ignored as outdated
                            {'date': str(int(time.time()) - 1000), 'amount': 1000, 'quantity': 1}]

        worker = Worker(ApiMock(), profile=Profiles.UP, avg_price_period=900)
        self.assertEqual(150, worker.get_avg_price())

    def test_get_desired_reserve_price_up(self):
        worker = Worker(None, profile=Profiles.UP, stock_fee=0.05, reserve_profit_markup=0.15, currency_2_deal_size=400)
        need_price = worker.calculate_desired_reserve_price(100)
        self.assertEqual(80, need_price)

    def test_get_desired_reserve_amount_up(self):
        worker = Worker(None, profile=Profiles.UP, stock_fee=0.05, reserve_profit_markup=0.15, currency_2_deal_size=400)
        amount = worker.calculate_desired_reserve_amount(80)
        self.assertEqual(5, amount)

    def test_get_desired_reserve_price_down(self):
        worker = Worker(None, profile=Profiles.DOWN, stock_fee=0.05, reserve_profit_markup=0.15, currency_1_deal_size=5)
        need_price = worker.calculate_desired_reserve_price(100)
        self.assertEqual(120, need_price)

    def test_get_desired_reserve_amount_down(self):
        worker = Worker(None, profile=Profiles.DOWN, stock_fee=0.05, reserve_profit_markup=0.15, currency_1_deal_size=5)
        amount = worker.calculate_desired_reserve_amount(120)
        self.assertEqual(5, amount)

    def test_main_flow_open_profit_order_up(self):
        # Проверяем, что процесс выходит, если игра на повышение и есть открытый ордер на продажу
        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return [{'type': 'sell'}]

        api = ApiMock()
        worker = Worker(api, profile=Profiles.UP)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)

    def test_main_flow_open_profit_order_down(self):
        # Проверяем, что процесс выходит, если игра на повышение и есть открытый ордер на продажу
        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return [{'type': 'buy'}]

        api = ApiMock()
        worker = Worker(api, profile=Profiles.DOWN)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)
        # worker.main_flow()
        self.assertEqual(1, api.get_open_orders_called)

    def test_main_flow_order_partially_completed_up(self):
        # Проверяем, что процесс выходит, если есть частично выполенный ордер на запас
        mock_order_id = '122'

        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return [{'type': 'buy', 'order_id': mock_order_id}]

            def is_order_partially_completed(self, order_id):
                if order_id == mock_order_id:
                    self.is_order_partially_completed_called += 1
                    return True
                return False

        api = ApiMock()
        worker = Worker(api, profile=Profiles.UP)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)
        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)

    def test_main_flow_order_partially_completed_down(self):
        # Проверяем, что процесс выходит, если есть частично выполенный ордер на запас
        mock_order_id = '122'

        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return [{'type': 'sell', 'order_id': mock_order_id}]

            def is_order_partially_completed(self, order_id):
                if order_id == mock_order_id:
                    self.is_order_partially_completed_called += 1
                    return True
                return False

        api = ApiMock()
        worker = Worker(api, profile=Profiles.DOWN)

        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)

    def test_main_flow_reserve_order_not_outdated_up(self):
        # Проверяем, что процесс выходит, если есть не истекший ордер на запас
        mock_order_id = '122'

        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return [{'type': 'buy', 'order_id': mock_order_id, 'created': str(int(time.time() - 10))}]

            def is_order_partially_completed(self, order_id):
                if order_id == mock_order_id:
                    self.is_order_partially_completed_called += 1
                    return False
                return True

        api = ApiMock()
        worker = Worker(api, profile=Profiles.UP)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)

    def test_main_flow_reserve_order_not_outdated_down(self):
        # Проверяем, что процесс выходит, если есть не истекший ордер на запас
        mock_order_id = '122'

        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return [{'type': 'sell', 'order_id': mock_order_id, 'created': str(int(time.time() - 10))}]

            def is_order_partially_completed(self, order_id):
                if order_id == mock_order_id:
                    self.is_order_partially_completed_called += 1
                    return False
                return True

        api = ApiMock()
        worker = Worker(api, profile=Profiles.DOWN)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)

    def test_main_flow_reserve_order_outdated_same_price_up(self):
        # Проверяем, что процесс выходит, если есть истекший ордер на запас, но цена не изменилась
        mock_order_id = '122'
        mock_order_price = 150

        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return [{'type': 'buy', 'order_id': mock_order_id, 'created': str(int(time.time() - 1000)),
                             'price': str(mock_order_price)}]

            def is_order_partially_completed(self, order_id):
                if order_id == mock_order_id:
                    self.is_order_partially_completed_called += 1
                    return False
                return True

        def get_desired_reserve_price():
            return mock_order_price - 1

        api = ApiMock()
        worker = Worker(api, profile=Profiles.UP, reserve_price_distribution=0.1, order_life_time=60)
        worker.get_desired_reserve_price = get_desired_reserve_price
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)

    def test_main_flow_reserve_order_outdated_same_price_down(self):
        # Проверяем, что процесс выходит, если есть истекший ордер на запас, но цена не изменилась
        mock_order_id = '122'
        mock_order_price = 150

        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return [{'type': 'sell', 'order_id': mock_order_id, 'created': str(int(time.time() - 1000)),
                             'price': str(mock_order_price)}]

            def is_order_partially_completed(self, order_id):
                if order_id == mock_order_id:
                    self.is_order_partially_completed_called += 1
                    return False
                return True

        def get_desired_reserve_price():
            return mock_order_price - 1

        api = ApiMock()
        worker = Worker(api, profile=Profiles.DOWN, reserve_price_distribution=0.1, order_life_time=60)
        worker.get_desired_reserve_price = get_desired_reserve_price
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)

    def test_main_flow_reserve_order_outdated_other_price_up(self):
        # Проверяем, что истекший ордер на запас отменяется, если цена изменилась
        mock_order_id = '122'
        mock_order_price = 150

        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0
                self.cancel_order_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return [{'type': 'buy', 'order_id': mock_order_id, 'created': str(int(time.time() - 1000)),
                             'price': str(mock_order_price)}]

            def is_order_partially_completed(self, order_id):
                if order_id == mock_order_id:
                    self.is_order_partially_completed_called += 1
                    return False
                return True

            def cancel_order(self, order_id):
                if order_id == mock_order_id:
                    self.cancel_order_called += 1

        def get_desired_reserve_price():
            return mock_order_price - 50

        api = ApiMock()
        worker = Worker(api, profile=Profiles.UP, reserve_price_distribution=0.1, order_life_time=60)
        worker.get_desired_reserve_price = get_desired_reserve_price
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)
        self.assertEqual(1, api.cancel_order_called)

    def test_main_flow_reserve_order_outdated_other_price_down(self):
        # Проверяем, что истекший ордер на запас отменяется, если цена изменилась
        mock_order_id = '122'
        mock_order_price = 150

        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.is_order_partially_completed_called = 0
                self.cancel_order_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return [{'type': 'sell', 'order_id': mock_order_id, 'created': str(int(time.time() - 1000)),
                             'price': str(mock_order_price)}]

            def is_order_partially_completed(self, order_id):
                if order_id == mock_order_id:
                    self.is_order_partially_completed_called += 1
                    return False
                return True

            def cancel_order(self, order_id):
                if order_id == mock_order_id:
                    self.cancel_order_called += 1

        def get_desired_reserve_price():
            return mock_order_price - 50

        api = ApiMock()
        worker = Worker(api, profile=Profiles.DOWN, reserve_price_distribution=0.1, order_life_time=60)
        worker.get_desired_reserve_price = get_desired_reserve_price
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.is_order_partially_completed_called)
        self.assertEqual(1, api.cancel_order_called)

    def test_main_flow_create_reserve_order_not_enough_money_up(self):
        # Проверяем создание ордера на резерв
        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.get_balances_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return []

            def get_balances(self):
                self.get_balances_called += 1
                return {'BTC': '0', 'USD': '120'}

        api = ApiMock()
        worker = Worker(api, profile=Profiles.UP, currency_1_deal_size=1, currency_2_deal_size=200)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.get_balances_called)

    def test_main_flow_create_reserve_order_not_enough_money_down(self):
        # Проверяем создание ордера на резерв
        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.get_balances_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return []

            def get_balances(self):
                self.get_balances_called += 1
                return {'BTC': '0', 'USD': '120'}

        api = ApiMock()
        worker = Worker(api, profile=Profiles.DOWN, currency_1_deal_size=1, currency_2_deal_size=200)
        self.assertRaises(Worker.ScriptQuitCondition, worker.main_flow)

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.get_balances_called)

    def test_main_flow_create_reserve_order_up(self):
        # Проверяем создание ордера на резерв
        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.get_balances_called = 0
                self.create_order_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return []

            def get_balances(self):
                self.get_balances_called += 1
                return {'BTC': '0', 'USD': '220'}

            def create_order(self, currency_1, currency_2, quantity, price, type):
                if currency_1 == 'BTC' and currency_2 == 'USD' and quantity == 5 and price == 40 and type == 'buy':
                    self.create_order_called += 1
                    return {'order_id': 122}

        api = ApiMock()

        def get_avg_price():
            return 50

        worker = Worker(api, profile=Profiles.UP, currency_1_deal_size=5, currency_2_deal_size=200, stock_fee=0.1,
                        reserve_profit_markup=0.1)
        worker.get_avg_price = get_avg_price
        worker.main_flow()

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.get_balances_called)
        self.assertEqual(1, api.create_order_called)

    def test_main_flow_create_reserve_order_down(self):
        # Проверяем создание ордера на резерв
        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.get_balances_called = 0
                self.create_order_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return []

            def get_balances(self):
                self.get_balances_called += 1
                return {'BTC': '6', 'USD': '0'}

            def create_order(self, currency_1, currency_2, quantity, price, type):
                if currency_1 == 'BTC' and currency_2 == 'USD' and quantity == 5 and price == 60 and type == 'sell':
                    self.create_order_called += 1
                    return {'order_id': 122}

        api = ApiMock()

        def get_avg_price():
            return 50

        worker = Worker(api, profile=Profiles.DOWN, currency_1_deal_size=5, stock_fee=0.1, reserve_profit_markup=0.1)
        worker.get_avg_price = get_avg_price
        worker.main_flow()

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.get_balances_called)
        self.assertEqual(1, api.create_order_called)

    def test_main_flow_create_profit_order_up(self):
        # Проверяем создание ордера на резерв
        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.get_balances_called = 0
                self.create_order_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return []

            def get_balances(self):
                self.get_balances_called += 1
                return {'BTC': '4', 'USD': '0'}

            def create_order(self, currency_1, currency_2, quantity, price, type):
                if currency_1 == 'BTC' and currency_2 == 'USD' and quantity == 4 and price == 60 and type == 'sell':
                    self.create_order_called += 1
                    return {'order_id': 122}

        api = ApiMock()
        worker = Worker(api, profile=Profiles.UP, currency_1_deal_size=4, currency_2_deal_size=200, stock_fee=0.1,
                        spend_profit_markup=0.1)
        worker.main_flow()

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.get_balances_called)
        self.assertEqual(1, api.create_order_called)

    def test_main_flow_create_profit_order_down(self):
        # Проверяем создание ордера на резерв
        class ApiMock:
            def __init__(self):
                self.get_open_orders_called = 0
                self.get_balances_called = 0
                self.create_order_called = 0

            def get_open_orders(self, currency_1, currency_2):
                if currency_1 == 'BTC' and currency_2 == 'USD':
                    self.get_open_orders_called += 1
                    return []

            def get_balances(self):
                self.get_balances_called += 1
                return {'BTC': '0', 'USD': '200'}

            def create_order(self, currency_1, currency_2, quantity, price, type):
                if currency_1 == 'BTC' and currency_2 == 'USD' and quantity == 5 and price == 40 and type == 'buy':
                    self.create_order_called += 1
                    return {'order_id': 122}

        api = ApiMock()
        worker = Worker(api, profile=Profiles.DOWN, currency_1_deal_size=4, currency_2_deal_size=200, stock_fee=0.1,
                        spend_profit_markup=0.15)
        worker.main_flow()

        self.assertEqual(1, api.get_open_orders_called)
        self.assertEqual(1, api.get_balances_called)
        self.assertEqual(1, api.create_order_called)


if __name__ == "__main__":
    unittest.main()
