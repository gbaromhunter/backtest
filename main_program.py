import backtrader as bt
from atreyu_backtrader_api import IBData
from Strat import MyStrategy
import datetime as dt
from support import FixedRiskSizer
from support import SortinoRatio, CommissionAnalyzer

# Create the Data object
data = IBData(host='127.0.0.1', port=7497, clientId=35,
               name="data",     # Data name
               dataname='AMZN', # Symbol name
               secType='STK',   # SecurityType is STOCK
               exchange='SMART',# Trading exchange IB's SMART exchange
               currency='USD',  # Currency of SecurityType
               fromdate=dt.datetime(2024, 2, 1),
               todate=dt.datetime(2024, 8, 30),
               historical=True,
               what='TRADES',  # Update this parameter to select data type
               timeframe=bt.TimeFrame.Minutes,
               compression=15  # The timeframe size
               )

data1 = IBData(host='127.0.0.1', port=7497, clientId=35,
               name="data1",     # Data name
               dataname='AMZN', # Symbol name
               secType='STK',   # SecurityType is STOCK
               exchange='SMART',# Trading exchange IB's SMART exchange
               currency='USD',  # Currency of SecurityType
               fromdate=dt.datetime(2024, 2, 1),
               todate=dt.datetime(2024, 8, 30),
               historical=True,
               what='TRADES',  # Update this parameter to select data type
               timeframe=bt.TimeFrame.Days,
               compression=1  # The timeframe size
               )

# Instantiate parameters
cerebro = bt.Cerebro()
starting_cash = 10000
# Specify the strategy
cerebro.addstrategy(MyStrategy)
cerebro.adddata(data)
cerebro.adddata(data1)
cerebro.broker.setcash(starting_cash)
cerebro.broker.setcommission(commission=0.00035)

# Add Analyzers
cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_analyzer')
cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
cerebro.addanalyzer(bt.analyzers.VWR, _name='vwr')

# Add Custom Analyzers
cerebro.addanalyzer(SortinoRatio, _name='sortino')
cerebro.addanalyzer(CommissionAnalyzer, _name='commissions')
cerebro.addsizer(FixedRiskSizer)

# Add Observers (e.g., log cash value, portfolio value)
cerebro.addobserver(bt.observers.Value)
cerebro.addobserver(bt.observers.Trades)
cerebro.addobserver(bt.observers.DrawDown)

# Print starting cash
print(f'Starting Portfolio Value: {cerebro.broker.getvalue():.2f}')

# Run the backtest
results = cerebro.run()
# cerebro.plot()

# Print ending cash
print(f'\nEnding Portfolio Value: {cerebro.broker.getvalue():.2f}')

# Access and print metrics from analyzers
sharpe = results[0].analyzers.sharpe.get_analysis()
drawdown = results[0].analyzers.drawdown.get_analysis()
returns = results[0].analyzers.returns.get_analysis()
trade_analyzer = results[0].analyzers.trade_analyzer.get_analysis()

# Access and print metrics from custom analyzers
sortino = results[0].analyzers.sortino.get_analysis()
commission_analysis = results[0].analyzers.commissions.get_analysis()

# Print metrics
print(f"\nSharpe Ratio: {sharpe.get('sharperatio', 'N/A')}")
print(f"Sortino Ratio: {sortino.get('sortinoratio', 'N/A')}") # Custom metric
print(f"Max Drawdown Percentage: {drawdown['max']['drawdown']:.2f}")
print(f"Max Drawdown Value: {drawdown['max']['moneydown']:.2f}")
print(f"Max Drawdown Duration: {drawdown['max']['len']:.2f}")
print(f"Total Return: {returns['rtot'] * 100:.2f}%")

# Accessing trade details
print('\n--- Trade Analyzer Detailed Results ---')
print(f"Total Trades: {trade_analyzer.total.total}")
print(f"Total Won: {trade_analyzer.won.total} / Total Lost: {trade_analyzer.lost.total}")
print(f"Win Rate: {trade_analyzer.won.total / trade_analyzer.total.total * 100:.2f}%")
print(f"Net Profit: {trade_analyzer.pnl.net.total:.2f} / Net Profit Percentage: {(trade_analyzer.pnl.net.total / starting_cash * 100):.2f}%")
print(f"Total Commission Costs: {commission_analysis['total_commission']:.2f}")
print(f"Max Win Amount: {trade_analyzer.won.pnl.max:.2f} / Average Win Amount: {trade_analyzer.won.pnl.average:.2f}")
print(f"Max Loss Amount: {trade_analyzer.lost.pnl.max:.2f} / Average Loss Amount: {trade_analyzer.lost.pnl.average:.2f}")
print(f"Average Trade Duration Bars: {trade_analyzer.len.average:.2f}")
