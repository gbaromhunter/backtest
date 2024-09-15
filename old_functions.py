
import backtrader as bt
# from atreyu_backtrader_api import IBData
import os
import pandas as pd
import yfinance as yf
from datetime import datetime
from ib_insync import *




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
    end_date = datetime.today().strftime('%Y-%m-%d') if end_date is None else end_date  # Today's date as the end date
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

def fetch_data_from_ib(ticker, file_name): # Broken
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
        data = fetch_data_from_ib(ticker, file_name)
    else:
        print(f"CSV file found. Loading data from {file_name}...")
        data = load_data(file_name)

    return data
