import argparse
import sys
from datetime import datetime
from pprint import pprint

from calc import Calc
from exmo_api import ExmoApi
from sqlite_api import SQLiteStorage

FEE = 0.002

START_TIME = datetime(2018, 3, 1, 0, 0, 0)

ORDER_FILE = r'real_run\orders.db'

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-k', '--key', type=str, help='Api key')
    parser.add_argument('-s', '--secret', type=str, help='Api secret')
    sysargs = parser.parse_args(sys.argv[1:])

    exmo_api = ExmoApi(sysargs.key, sysargs.secret)

    st = SQLiteStorage(ORDER_FILE)

    calc = Calc(exmo_api, st, START_TIME, FEE)
    ok_deals, profit = calc.get_profit()
    pprint(ok_deals)
    pprint(profit)
