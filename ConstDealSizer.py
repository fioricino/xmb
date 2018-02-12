class ConstDealSizer:
    def __init__(self, **kwargs):
        if 'currency_1_deal_size' in kwargs:
            self._currency_1_deal_size = kwargs['currency_1_deal_size']
        else:
            self._currency_1_deal_size = 0.001

    def get_deal_size(self):
        return self._currency_1_deal_size
