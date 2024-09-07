from support import *
import backtrader as bt
from Strat import MyStrategy
import quantstats
import warnings
import time
warnings.simplefilter(action='ignore', category=FutureWarning)
# from test import TestStrategy


# Create the Data object

data, total_candles = define_data_alphavantage(ticker='AMZN',
                                start_year=2024,
                                start_month=1,
                                months=4,
                                interval='1min',
                                )

# data = define_data_ib(ticker="AMZN",
#                    )

# data = define_data_yahoo("AMZN",
#                    "2024-01-01",
#                    "2024-08-31",
#                    )


def runstrat():
    start_time = time.time()
    args = parse_args()
    # Instantiate parameters
    cerebro = bt.Cerebro()
    # Specify the strategy
    cerebro.addstrategy(MyStrategy, total_candles=total_candles)

    # Add the data
    cerebro.adddata(data)
    # Resample the first smaller timeframe into a bigger timeframe
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Minutes, compression=15)

    # Set the initial cash amount and the commission costs
    starting_cash = 10000
    cerebro.broker.setcash(starting_cash)
    cerebro.broker.setcommission(commission=0.00035)

    # Add Analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_analyzer')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

    # Add Custom Analyzers
    cerebro.addanalyzer(SortinoRatio, _name='sortino')
    cerebro.addanalyzer(CommissionAnalyzer, _name='commissions')
    cerebro.addsizer(FixedRiskSizer)
    cerebro.addanalyzer(bt.analyzers.PyFolio, _name='PyFolio')

    # Add Observers (e.g., log cash value, portfolio value)
    cerebro.addobserver(bt.observers.Value)
    cerebro.addobserver(bt.observers.Trades)

    # Print starting cash
    print(f'Starting Portfolio Value: {cerebro.broker.getvalue():.2f}')

    # Run the backtest
    if args.plot:
        cerebro.plot(style='bar')

    results = cerebro.run(runonce=False)
    strat = results[0]

    # Record the end time
    end_time = time.time()

    # Calculate the elapsed time
    elapsed_time = end_time - start_time

    # Convert elapsed time to minutes and seconds
    minutes, seconds = divmod(elapsed_time, 60)

    # Print the elapsed time
    print(f"Backtest completed in {int(minutes)} minutes and {int(seconds)} seconds")

    # Print ending cash
    print(f'\nEnding Portfolio Value: {cerebro.broker.getvalue():.2f}')

    # Access and print metrics from analyzers
    returns = results[0].analyzers.returns.get_analysis()
    trade_analyzer = results[0].analyzers.trade_analyzer.get_analysis()

    # Access and print metrics from custom analyzers
    commission_analysis = results[0].analyzers.commissions.get_analysis()
    portfolio_stats = strat.analyzers.getbyname('PyFolio')
    ret, positions, transactions, gross_lev = portfolio_stats.get_pf_items()
    ret.index = ret.index.tz_convert(None)
    quantstats.reports.html(ret, output='stats.html', title='Backtest results')


    print_end(returns, trade_analyzer, starting_cash, commission_analysis)


if __name__ == '__main__':
    runstrat()
