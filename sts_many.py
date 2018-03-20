import json
import os

import pandas as pd
from tabulate import tabulate

base_folder = r'real_data_test\test_5_30_pm_003'

stat_file = 'stats.json'


def handle_folder(folder):
    data = {}
    try:
        with open(os.path.join(folder, stat_file)) as f:
            stats = json.load(f)
            data['BTC'] = float(stats['BTC'])
            data['USD'] = float(stats['USD'])
            data['BTC_max'] = float(stats['BTC_max'])
            data['USD_max'] = float(stats['USD_max'])
            data['BTC_rate'] = data['BTC'] / data['BTC_max']
            data['USD_rate'] = data['USD'] / data['USD_max']
            data['total_rate'] = (data['BTC_rate'] + data['USD_rate']) / 2
            # data['profit'] = np.mean((data['BTC'], data['USD']))

    except Exception as e:
        print(e)
        data['BTC'] = None
        data['USD'] = None
        # data['profit'] = None
    return data


def walk_dir(folder):
    result = []
    for subd in os.listdir(folder):
        res = handle_folder(os.path.join(folder, subd))
        result.append(res)
    return result


def get_run_stats(base_folder):
    result = walk_dir(base_folder)

    df = pd.DataFrame(result)
    dfm = pd.DataFrame()
    dfm['mean'] = df.mean()
    dfm['min'] = df.min()
    dfm['max'] = df.max()

    # dfm = dfm.sort_values('total_rate', ascending=False)
    return dfm


df = get_run_stats(base_folder)
# columns = ['ppapd', 'pol', 'pm', 'pm1', 'rpapd', 'ppppd', 'spopd', 'pfw', 'rm', 'mpp']

# base_columns.extend(columns)

df.to_csv(os.path.join(base_folder, 'df.csv'))

print(tabulate(df, headers='keys', tablefmt='psql'))
