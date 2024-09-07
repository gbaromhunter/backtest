import math
from backtrader.utils.py3 import itervalues
from backtrader import Analyzer, TimeFrame, Sizer, Indicator
from backtrader.mathsupport import average, standarddev
from backtrader.analyzers import TimeReturn, AnnualReturn
import backtrader as bt
import argparse
from atreyu_backtrader_api import IBData
import os
import pandas as pd
import yfinance as yf
from datetime import datetime
from ib_insync import *
import requests
import csv
from io import StringIO



class DonchianChannels(Indicator):
    '''
    Params Note:
      - `lookback` (default: -1)
        If `-1`, the bars to consider will start 1 bar in the past and the
        current high/low may break through the channel.
        If `0`, the current prices will be considered for the Donchian
        Channel. This means that the price will **NEVER** break through the
        upper/lower channel bands.
    '''

    alias = ('DCH', 'DonchianChannel',)

    lines = ('dcm', 'dch', 'dcl',)  # dc middle, dc high, dc low
    params = dict(
        period=20,
        lookback=-1,  # consider current bar or not
    )

    plotinfo = dict(subplot=False)  # plot along with data
    plotlines = dict(
        dcm=dict(ls='--'),  # dashed line
        dch=dict(_samecolor=True),  # use same color as prev line (dcm)
        dcl=dict(_samecolor=True),  # use same color as prev line (dch)
    )

    def __init__(self):
        hi, lo = self.data.high, self.data.low
        if self.p.lookback:  # move backwards as needed
            hi, lo = hi(self.p.lookback), lo(self.p.lookback)

        self.l.dch = bt.ind.Highest(hi, period=self.p.period)
        self.l.dcl = bt.ind.Lowest(lo, period=self.p.period)
        self.l.dcm = (self.l.dch + self.l.dcl) / 2.0  # avg of the above

class SortinoRatio(Analyzer):

    params = (
        ('timeframe', TimeFrame.Years),
        ('compression', 1),
        ('riskfreerate', 0.01),
        ('factor', None),
        ('convertrate', True),
        ('annualize', False),
        ('stddev_sample', False),

        # old behavior
        ('daysfactor', None),
        ('legacyannual', False),
        ('fund', None),
    )

    RATEFACTORS = {
        TimeFrame.Days: 252,
        TimeFrame.Weeks: 52,
        TimeFrame.Months: 12,
        TimeFrame.Years: 1,
    }

    def __init__(self):
        if self.p.legacyannual:
            self.anret = AnnualReturn()
        else:
            self.timereturn = TimeReturn(
                timeframe=self.p.timeframe,
                compression=self.p.compression,
                fund=self.p.fund)

    def stop(self):
        super(SortinoRatio, self).stop()
        if self.p.legacyannual:
            rate = self.p.riskfreerate
            retavg = average([r - rate for r in self.anret.rets])
            downside_deviation = self._calculate_downside_deviation(self.anret.rets)
            if downside_deviation != 0:
                self.ratio = retavg / downside_deviation
            else:
                self.ratio = None
        else:
            # Get the returns from the subanalyzer
            returns = list(itervalues(self.timereturn.get_analysis()))

            if not returns:
                self.ratio = None
                self.rets['sortinoratio'] = self.ratio
                return

            rate = self.p.riskfreerate

            factor = self.p.factor or self.RATEFACTORS.get(self.p.timeframe)

            if factor is not None:
                if self.p.convertrate:
                    rate = pow(1.0 + rate, 1.0 / factor) - 1.0
                else:
                    returns = [pow(1.0 + x, factor) - 1.0 for x in returns]

            lrets = len(returns) - self.p.stddev_sample

            if lrets:
                ret_free = [r - rate for r in returns]
                ret_free_avg = average(ret_free)
                downside_deviation = self._calculate_downside_deviation(ret_free)
                if downside_deviation != 0:
                    try:
                        ratio = ret_free_avg / downside_deviation

                        if factor is not None and \
                                self.p.convertrate and self.p.annualize:
                            ratio = math.sqrt(factor) * ratio
                    except (ValueError, TypeError, ZeroDivisionError):
                        ratio = None
                else:
                    ratio = None
            else:
                ratio = None

            self.ratio = ratio
        self.rets['sortinoratio'] = self.ratio


    def _calculate_downside_deviation(self, returns):
        """Calculate the downside deviation (only considers negative returns)."""
        downside_returns = [r for r in returns if r < 0]
        if downside_returns:
            return standarddev(downside_returns, bessel=self.p.stddev_sample)
        return 0.0

class CommissionAnalyzer(Analyzer):
    def __init__(self):
        self.commissions = []  # To store all commission costs

    def notify_trade(self, trade):
        # Track commissions only for completed trades
        if trade.isclosed:
            self.commissions.append(trade.commission)

    def get_analysis(self):
        # Return the sum of all commissions
        return {'total_commission': sum(self.commissions),
                'commissions': self.commissions}

class FixedRiskSizer(Sizer):
    params = (
        ('risk_per_trade', 0.01),  # 1% of capital at risk per trade
    )

    def _getsizing(self, comminfo, cash, data, isbuy):
        if isbuy:
            stop_loss_distance = data.close[0] - self.strategy.stop_price  # Assuming stop_price is set in strategy
            capital_at_risk = self.broker.getvalue() * self.params.risk_per_trade  # Capital at risk for this trade
            position_size = capital_at_risk / stop_loss_distance
            return position_size  # Return position size as an integer
        return 0  # If it's not a buy order, return 0

def parse_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description='Sample for pivot point and cross plotting')

    parser.add_argument('--data', required=False,
                        default='../../datas/2005-2006-day-001.txt',
                        help='Data to be read in')

    parser.add_argument('--multi', required=False, action='store_true',
                        help='Couple all lines of the indicator')

    parser.add_argument('--plot', required=False, action='store_true',
                        help=('Plot the result'))

    return parser.parse_args()

def load_data(file_name):
    """Load data from CSV file."""
    data = pd.read_csv(file_name, index_col='Date', parse_dates=True)
    data = bt.feeds.PandasData(
        dataname=data,
        datetime=None,  # Backtrader will use the index as datetime
        open=0,
        high=1,
        low=2,
        close=3,
        volume=4
    )
    return data

def fetch_data_from_yahoo(ticker, start_date, end_date, file_name):
    """Download data from Yahoo Finance and save it as a CSV."""
    data = yf.download(ticker, start=start_date, end=end_date)
    data = data.drop(columns=['Adj Close'])
    data.index.name = 'Date'  # Ensure the index is named 'Date'
    data.to_csv(file_name)
    data = bt.feeds.PandasData(
        dataname=data,
        datetime=None,  # Backtrader will use the index as datetime
        open=0,
        high=1,
        low=2,
        close=3,
        volume=4
    )
    return data

def define_data_yahoo(ticker, start_date, end_date):
    ticker = ticker  # Stock ticker
    start_date = start_date  # Start date for fetching data
    end_date = datetime.today().strftime('%Y-%m-%d') if end_date == None else end_date  # Today's date as the end date
    file_name = f"{ticker}_data.csv"  # File name for saving the data

    # Convert pandas dataframe to Backtrader data feed

    # Check if CSV exists, otherwise download the data
    if not os.path.exists(file_name):
        print(f"CSV file not found. Downloading data for {ticker} from Yahoo Finance...")
        data = fetch_data_from_yahoo(ticker, start_date, end_date, file_name)
    else:
        print(f"CSV file found. Loading data from {file_name}...")
        data = load_data(file_name)

    return data

def fetch_data_from_IB(ticker, file_name): # Broken
    util.startLoop()

    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=35)
    contract = Stock(ticker=ticker, exchange='SMART', currency='USD')

    data = ib.reqHistoricalData(
        contract,
        endDateTime='',
        barSizeSetting='1 min',
        durationStr='7 D',
        whatToShow='TRADES',
        useRTH=True,
        formatDate=1,
        keepUpToDate=True)

    data = pd.DataFrame(data, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
    data.to_csv(file_name)
    data = bt.feeds.PandasData(
        dataname=data,
        datetime=None,  # Backtrader will use the index as datetime
        open=0,
        high=1,
        low=2,
        close=3,
        volume=4
    )
    return data

    # def fetch_data_from_IB(ticker, start_date, end_date, file_name, timeframe, compression):
    # timeframes = {'minutes': bt.TimeFrame.Minutes,
    #               'days': bt.TimeFrame.Days,
    #               'weeks': bt.TimeFrame.Weeks,
    #               'months': bt.TimeFrame.Months,}
    # data = IBData(host='127.0.0.1', port=7497, clientId=35,
    #                name="data",     # Data name
    #                dataname=ticker, # Symbol name
    #                secType='STK',   # SecurityType is STOCK
    #                exchange='SMART',# Trading exchange IB's SMART exchange
    #                currency='USD',  # Currency of SecurityType
    #                fromdate=start_date,
    #                todate=end_date,
    #                what='TRADES',  # Update this parameter to select data type
    #                timeframe=timeframes[timeframe],
    #                compression=compression,  # The timeframe size
    #                # latethrough=True,
    #                )
    # data = util.df(data)
    #
    # data = data.drop(columns=['Adj Close'])
    # data.index.name = 'Date'  # Ensure the index is named 'Date'
    # data.to_csv(file_name)
    # data = bt.feeds.PandasData(
    #     dataname=data,
    #     datetime=None,  # Backtrader will use the index as datetime
    #     open=0,
    #     high=1,
    #     low=2,
    #     close=3,
    #     volume=4
    # )
    # return data

def define_data_ib(ticker):
    file_name = f"{ticker}_data.csv"  # File name for saving the data

    # Convert pandas dataframe to Backtrader data feed

    # Check if CSV exists, otherwise download the data
    if not os.path.exists(file_name):
        print(f"CSV file not found. Downloading data for {ticker} from IBKR...")
        data = fetch_data_from_IB(ticker, file_name)
    else:
        print(f"CSV file found. Loading data from {file_name}...")
        data = load_data(file_name)

    return data


def define_data_alphavantage(ticker, start_year, start_month, months, interval):
    file_name = f"{ticker}_data.csv"

    if not os.path.exists(file_name):
        print(f"CSV file not found. Downloading data for {ticker} from Alphavantage...")
        fetch_intraday_data_from_alphavantage(ticker, start_year, start_month, months, interval)
        print(f"CSV file found. Loading data from {file_name}...")
        data = load_data(file_name)
    else:
        print(f"CSV file found. Loading data from {file_name}...")
        data = load_data(file_name)

    return data


# def fetch_intraday_data_from_alphavantage(ticker, interval='1min', month=''):
#     """
#     Download 1-minute intraday historical data from Alpha Vantage API and save it to a CSV file.
#
#     Parameters:
#     - symbol (str): Stock symbol to fetch data for (e.g., 'AAPL')
#     - api_key (str): Your Alpha Vantage API key
#     - output_file (str): The name of the CSV file to save the data to (default is 'intraday_data.csv')
#     - interval (str): Interval for intraday data ('1min', '5min', '15min', '30min', '60min')
#     """
#     output_file = f'{ticker}_data.csv'
#     api_key = '5BAAAUMO47W9TG46'
#
#     url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={ticker}&interval={interval}&apikey={api_key}&month={month}&outputsize=full&datatype=csv'
#
#     response = requests.get(url)
#
#     if response.status_code == 200:
#
#         # Load the CSV data into a pandas DataFrame
#         data = pd.read_csv(StringIO(response.text))
#
#         # Rename the first column to 'date'
#         data.rename(columns={data.columns[0]: 'Date'}, inplace=True)
#
#         # Set the 'date' column as the index
#         data.set_index('Date', inplace=True)
#
#         # if you need to reverse the data
#         data = data[::-1]
#
#         # Save the DataFrame to a CSV file
#         data.to_csv(output_file)
#
#         print(f"Data successfully saved to {output_file}")
#     else:
#         print(f"Failed to retrieve data: {response.status_code}")


def fetch_intraday_data_from_alphavantage(ticker, start_year, start_month, months, interval):
    """
    Download 1-minute intraday historical data from Alpha Vantage API for multiple months and save it to a CSV file.

    Parameters:
    - ticker (str): Stock symbol to fetch data for (e.g., 'AAPL')
    - interval (str): Interval for intraday data ('1min', '5min', '15min', '30min', '60min')
    - months (list of str): List of months to fetch data for in 'YYYY-MM' format (e.g., ['2024-01', '2024-02'])
    """
    api_key = '5BAAAUMO47W9TG46'
    all_data = []
    for _ in range(months):
        if start_month > 12:
            start_year = start_year + 1
            start_month = 1
        month = f'{start_year}-{start_month:02d}'
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={ticker}&interval={interval}&apikey={api_key}&month={month}&outputsize=full&datatype=csv'
        start_month = start_month + 1
        response = requests.get(url)

        if response.status_code == 200:
            # Load the CSV data into a pandas DataFrame
            data = pd.read_csv(StringIO(response.text))

            # Rename the first column to 'Date'
            data.rename(columns={data.columns[0]: 'Date'}, inplace=True)

            # Set the 'Date' column as the index
            data.set_index('Date', inplace=True)

            # Reverse the data if needed
            data = data[::-1]

            # Append the data to the list
            all_data.append(data)
        else:
            print(f"Failed to retrieve data for {month}: {response.status_code}")


    if all_data:
        # Concatenate all data frames into a single DataFrame
        combined_data = pd.concat(all_data)

        # Save the combined DataFrame to a CSV file
        output_file = f'{ticker}_data.csv'
        combined_data.to_csv(output_file)

        print(f"Data successfully saved to {output_file}")
    else:
        print("No data was retrieved.")