import json
import os

import pandas as pd
from tabulate import tabulate

base_folder = r'real_data_test\test_month1'

stat_file = 'stats.json'


def handle_folder(folder, data):
    completed_profit_orders = 0
    try:
        with open(os.path.join(folder, stat_file)) as f:
            stats = json.load(f)
            data['BTC'] = float(stats['BTC'])
            data['USD'] = float(stats['USD'])
            data['BTC_max'] = float(stats['BTC_max'])
            data['USD_max'] = float(stats['USD_max'])
            data['BTC_rate'] = data['BTC'] / data['BTC_max']
            data['USD_rate'] = data['USD'] / data['USD_max']
            data['total_rate'] = data['BTC_rate'] + data['USD_rate']
            # data['profit'] = np.mean((data['BTC'], data['USD']))
        arch_fold = os.path.join(folder, 'archive')
        for fl in os.listdir(arch_fold):
            with open(os.path.join(arch_fold, fl)) as f:
                o = json.load(f)
                if o['order_type'] == 'PROFIT' and o['status'] == 'COMPLETED':
                    completed_profit_orders += 1
        data['orders'] = completed_profit_orders
    except Exception as e:
        print(e)
        data['BTC'] = None
        data['USD'] = None
        # data['profit'] = None
        data['orders'] = None


def walk_dir(folder):
    result = []
    for subd in os.listdir(folder):
        parts = subd.split('_')
        attrs = []
        values = []
        for i, p in enumerate(parts):
            if i % 2 == 0:
                attrs.append(p if not p in attrs else p + '1')
            else:
                values.append(p)
        desc = dict(zip(attrs, values))
        handle_folder(os.path.join(folder, subd), desc)
        result.append(desc)
    return result


def get_run_stats(base_folder):
    result = walk_dir(base_folder)

    df = pd.DataFrame(result)
    df = df.sort_values('total_rate', ascending=False)
    return df


df = get_run_stats(base_folder)
base_columns = ['profit', 'orders']
# columns = ['ppapd', 'pol', 'pm', 'pm1', 'rpapd', 'ppppd', 'spopd', 'pfw', 'rm', 'mpp']

# base_columns.extend(columns)

df.to_csv(os.path.join(base_folder, 'df.csv'))
print(tabulate(df, headers='keys', tablefmt='psql'))
