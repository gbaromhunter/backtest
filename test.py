import backtrader as bt
import datetime as dt

class TestStrategy(bt.Strategy):
    def __init__(self):
        pass  # No indicators or variables needed for this simple test

    def next(self):
        # Log the closing price of the data on each bar
        self.log(f'Close data: {self.datas[0].close[0]}')
        self.log(f'Close data1: {self.datas[1].close[0]}')

    def log(self, txt):
        ''' Logging function for this strategy'''
        dt = self.datas[0].datetime.datetime(0)
        print(f'{dt.isoformat()} - {txt}')