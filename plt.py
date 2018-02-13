import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# import mpld3
from collections import defaultdict
import os
import json

from sqlite_api import SQLiteStorage
from trend_analyze import TrendAnalyzer

deals_folder = r'C:\Users\ozavorot\Documents\GitHub\xmb\trades-2018-02-02'
run_folder = None  # r'C:\Users\ozavorot\Documents\GitHub\xmb\test'
db_file = None  # r'C:\Users\ozavorot\Documents\GitHub\xmb\datasets\orders.db'


def get_deals(deals_folder):
    deals = {}
    for filename in os.listdir(deals_folder):
        with open(os.path.join(deals_folder, filename)) as f:
            try:
                d = json.load(f)
                deals.update(d)
            except:
                pass
    dd = defaultdict(list)
    for d in deals.values():
        dd[int(d['date'])].append(float(d['price']))
    data = []
    for k, d in dd.items():
        data.append({'date': k, 'price': np.mean(d)})
    data = sorted(data, key=lambda d: d['date'])
    return data


def get_deals_df(deals_folder):
    deals = get_deals(deals_folder)
    df = pd.DataFrame(deals)
    return df


def get_orders_from_db(db_file):
    st = SQLiteStorage(db_file)
    arch = st.get_archive_orders()
    arch.extend(st.get_open_orders())
    return arch


def get_orders_from_json(run_folder):
    arch = []
    arch_folder = os.path.join(run_folder, 'archive')
    for filename in os.listdir(arch_folder):
        with open(os.path.join(arch_folder, filename)) as f:
            d = json.load(f)
            arch.append(d)

    with open(os.path.join(run_folder, 'orders.json')) as f:
        d = json.load(f)
        arch.extend(d.values())
    return arch


ta = TrendAnalyzer()


def get_last_deals(deals_df, time):
    index = -1
    for i, d in enumerate(deals_df['date']):
        if d >= time:
            index = i
            break
    if index > 0:
        return deals_df[max(0, index - 100): index]
    return []


def get_mean_price_func(deals_df, time):
    last_deals = get_last_deals(deals_df, time)
    last_deals_df = pd.DataFrame([p for p in last_deals])
    price_func, step, x_lin = ta._get_interpolated_func([d for d in last_deals_df['time']],
                                                        [p for p in last_deals_df['price']])
    mean_func = ta._get_rolling_mean_func(price_func)
    norm_func = ta._normalize_func(price_func)
    mean_norm_func = ta._get_rolling_mean_func(norm_func)
    derivative_func = ta._get_der_func(mean_norm_func, step)
    rolling_mean_derivative_func = ta._get_rolling_mean_func(derivative_func)
    return x_lin, mean_func, rolling_mean_derivative_func
    # plt.plot(x_lin[6:-6], mean_func)
    # plt.plot(last_deals_df['time'], last_deals_df['price'])


def plot_lines(xcoord, color):
    if color is None:
        return
    for x in xcoord:
        xs = np.repeat(x, 20)
        ys = np.arange(11000, 13000, 100)
        plt.plot(xs, ys, color=color)


def plot_order(order, colors, max_time, deals_df):
    order_color = colors[order['profile']][order['order_type']][order['status']]
    if order_color is None:
        return
    create_time = int(order['created'])
    price = float(order['price'])
    plt.plot(create_time, price, color=order_color, marker='s')

    if order['status'] == 'COMPLETED':
        if order['completed'] is not None:
            complete_time = int(order['completed'])
            plt.plot(complete_time, price, color=order_color, marker='o')
            x = np.arange(create_time, complete_time, 1)
            y = np.repeat(price, len(x))
            plt.plot(x, y, color=order_color)
    elif order['status'] == 'CANCELED':
        if order['completed'] is not None:
            cancel_time = int(order['completed'])
            plt.plot(cancel_time, price, color=order_color, marker='x')
            x = np.arange(create_time, cancel_time, 100)
            y = np.repeat(price, len(x))
            plt.plot(x, y, ':', color=order_color)
    elif order['status'] == 'OPEN':
        plt.plot(max_time, price, color=order_color, marker='>')
        x = np.arange(create_time, max_time, 1)
        y = np.repeat(price, len(x))
        plt.plot(x, y, '--', color=order_color)
    if order['order_type'] == 'PROFIT' and order['base_order'] is not None:
        price = float(order['price'])
        base_price = float(order['base_order']['price'])
        base_create_time = int(order['base_order']['created'])
        y = np.arange(min(base_price, price), max(base_price, price), 1)
        x = np.repeat(base_create_time, len(y))
        plt.plot(x, y, color=order_color, linestyle=':')
        base_time = int(order['base_order']['completed'])
        x = np.arange(base_create_time, create_time, 1)
        y = np.repeat(price, len(x))
        plt.plot(x, y, color=order_color, linestyle=':')


# elif order['order_type'] == 'RESERVE':
#         x_lin, mean_price_func, der_func = get_mean_price_func(deals_df, int(order['created']))
#         plt.plot(x_lin, mean_price_func, color=order_color)
#         print(der_func)
#         der = der_func.iloc[-2]
#         plt.text(int(order['created'] - 50), float(order['order_data']['price']) + 10, der, color=order_color)


def analyze_run(deals_folder, run_folder, colors, offset=None, limit=None):
    deals_df = get_deals_df(deals_folder)
    if offset is not None:
        deals_df = deals_df[offset:limit]
        # print(deals_df)
    plt.plot(deals_df['date'], deals_df['price'])
    orders = None
    if run_folder:
        orders = get_orders_from_json(run_folder)
    if db_file:
        orders = get_orders_from_db(db_file)
    if orders:
        max_time = max(deals_df['date'])
        for order in orders:
            if int(order['created']) < max_time:
                plot_order(order, colors, max_time, deals_df)

    # print('Completed profit orders: {}'.format(orders['profit']['completed']))
    # print('Created profit orders: {}'.format(orders['profit']['created']))
    plt.ylim(ymin=min(deals_df['price']) - 100, ymax=max(deals_df['price']) + 100)
    plt.xlim(xmin=min(deals_df['date']), xmax=max(deals_df['date']))
    plt.show()


colors = {
    'UP':
        {
            'RESERVE':
                {
                    'COMPLETED': 'ORANGE',
                    'CANCELED': 'YELLOW',
                    'OPEN': None,
                    'WAIT_FOR_PROFIT': 'ORANGE',
                    'PROFIT_ORDER_CANCELED': 'ORANGE'
                },
            'PROFIT':
                {
                    'COMPLETED': 'RED',
                    'CANCELED': 'FIREBRICK',
                    'OPEN': 'RED',
                    'WAIT_FOR_PROFIT:': None,
                    'PROFIT_ORDER_CANCELED': None

                }
        },
    'DOWN':
        {
            'RESERVE':
                {
                    'COMPLETED': 'MAGENTA',
                    'CANCELED': 'PINK',
                    'OPEN': None,
                    'WAIT_FOR_PROFIT': 'MAGENTA',
                    'PROFIT_ORDER_CANCELED': 'MAGENTA'
                },
            'PROFIT':
                {
                    'COMPLETED': 'PURPLE',
                    'CANCELED': 'BLACK',
                    'OPEN': 'PURPLE',
                    'WAIT_FOR_PROFIT': None,
                    'PROFIT_ORDER_CANCELED': None,
                }
        },
}
analyze_run(deals_folder, run_folder, colors)
