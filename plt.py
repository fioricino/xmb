import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# import mpld3
from collections import defaultdict
import os
import json

from sqlite_api import SQLiteStorage
from trend_analyze import TrendAnalyzer

deals_folder = r'C:\Users\ozavorot\Documents\GitHub\xmb\real_data_test\datasets'
run_folder = r'C:\Users\ozavorot\Documents\GitHub\xmb\real_data_test\test_month2\c1ds_0' \
             r'.001_it_1517574194_kb_150_kd_7_km_0_ld_100_lpd_0.03_mpod_100_mpou_100_mpp_16_pcd_BTC_pcu_USD_pm_0' \
             r'.01_spopd_0.05_sf_0.002_'
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
    fig1 = plt.figure()
    ax1 = fig1.add_subplot(111)
    ax1.plot(deals_df['date'], deals_df['price'])
    orders = None
    min_date = min(deals_df['date'])
    max_date = max(deals_df['date'])
    days = range(min_date, max_date, 3600 * 24)
    if run_folder:
        orders = get_orders_from_json(run_folder)
    if db_file:
        orders = get_orders_from_db(db_file)
    if orders:
        for order in orders:
            if int(order['created']) < max_date:
                plot_order(order, colors, max_date, deals_df)

    # print('Completed profit orders: {}'.format(orders['profit']['completed']))
    # print('Created profit orders: {}'.format(orders['profit']['created']))
    min_price = min(deals_df['price']) - 100
    max_price = max(deals_df['price']) + 100
    # plt.ylim(ymin=min_price, ymax=max_price)
    plt.xlim(xmin=min_date, xmax=max(deals_df['date']))

    for day in days:
        ax1.axvline(day, color='lightgray', linestyle=':')
    window = 2000
    current_trend = 1
    order_price = None
    current_price = 12000
    limit_price = None
    deals_df['mean'] = deals_df['price'].rolling(window).mean()
    plt.plot(deals_df['date'], deals_df['mean'], color='black')
    # for i in range(20000, len(deals_df) - 1, 100):
    #     print(i)
    #     df = pd.DataFrame(deals_df[i-20000:i])
    #     df['mean'] = df['price'].rolling(window).mean()
    #     # df['sg'] = sg.savgol_filter(df['price'], 19999, 3)
    #     #
    #     # plt.plot(deals_df['date'], deals_df['sg'], color='yellow')
    #     # derivative = df['sg'].diff(periods=100)
    #     # df['derivative'] = derivative
    #     # for i, row in deals_df.iterrows():
    #     #     der = row['derivative']
    #     row = df.iloc[-1]
    #     der = row['mean'] - current_price
    #     if np.sign(current_trend) != np.sign(der):
    #         if limit_price is None:
    #             limit_price = row['mean']
    #         else:
    #             if abs(row['mean'] - limit_price) > 50:
    #                 if order_price is None or np.sign(row['price'] - order_price) == np.sign(current_trend):
    #                     ax1.axvline(row['date'], color='green' if der > 0 else 'orange', linestyle=':')
    #                     order_price = row['price']
    #                     limit_price = None
    #                     current_trend = der
    #     else:
    #         limit_price = None
    #     current_der = der
    #     current_price = row['mean']
    # ax2 = ax1.twinx()

    # ax2.plot(mean_func['date'], derivative, color='bisque')
    # ax2.axhline(0)
    # for day in days:
    #     ax2.axvline(day, color='lightgray', linestyle=':')
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
