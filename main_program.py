from support import *
import backtrader as bt
from Strat import MyStrategy
import quantstats
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
# from test import TestStrategy


# Create the Data object

data = define_data_alphavantage(ticker='AMZN',
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
    args = parse_args()
    # Instantiate parameters
    cerebro = bt.Cerebro()
    # Specify the strategy
    cerebro.addstrategy(MyStrategy)

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

    # Print metrics
    print(f"Total Return: {returns['rtot'] * 100:.2f}%")

    # Accessing trade details
    print('\n--- Trade Analyzer Detailed Results ---')
    print(f"Total Trades: {trade_analyzer.total.total}")

    quantstats.reports.html(ret, output='stats.html', title='Backtest results')

    if trade_analyzer.total.total != 0:
        print(f"Total Won: {trade_analyzer.won.total} / Total Lost: {trade_analyzer.lost.total}")
        print(f"Net Profit: {trade_analyzer.pnl.net.total:.2f} / Net Profit Percentage: {(trade_analyzer.pnl.net.total / starting_cash * 100):.2f}%")
        print(f"Win Rate: {trade_analyzer.won.total / trade_analyzer.total.total * 100:.2f}%")
        print(f"Max Win Amount: {trade_analyzer.won.pnl.max:.2f} / Average Win Amount: {trade_analyzer.won.pnl.average:.2f}")
        print(f"Max Loss Amount: {trade_analyzer.lost.pnl.max:.2f} / Average Loss Amount: {trade_analyzer.lost.pnl.average:.2f}")
        print(f"Average Trade Duration Bars: {trade_analyzer.len.average:.2f} - {trade_analyzer.len.average / 60:.2f} Hours - {trade_analyzer.len.average / 3600:.2f} Days")
        print(f"Total Commission Costs: {commission_analysis['total_commission']:.2f}")
    else:
        print("No trade executed")








if __name__ == '__main__':
    runstrat()
