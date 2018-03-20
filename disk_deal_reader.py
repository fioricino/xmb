import datetime
import json
import os
import time


class DiskDealReader:
    def __init__(self, deals_folder, **kwargs):
        self._deals_folder = deals_folder
        if 'deal_read_days' in kwargs:
            self._deal_read_days = kwargs['deal_read_days']
        else:
            self._deal_read_days = None

    def get_deals(self):
        if self._deal_read_days is None:
            start_date = 0
        else:
            start_date = self._get_time() - datetime.timedelta(days=self._deal_read_days).total_seconds()
        files = [f for f in os.listdir(self._deals_folder) if int(os.path.splitext(f)[0]) > start_date]
        deals = {}
        for filename in files:
            with open(os.path.join(self._deals_folder, filename)) as f:
                try:
                    d = json.load(f)
                    deals.update(d)
                except:
                    pass
        return sorted(deals.values(), key=lambda v: (int(v['date']), int(v['trade_id'])))

    def _get_time(self):
        return int(time.time())
