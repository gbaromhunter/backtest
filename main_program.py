import random, csv
from deap import base, creator, tools, algorithms
import backtrader as bt
import warnings
from Strat import MyStrategy
from support import define_data_alphavantage, FixedRiskSizer, CommissionAnalyzer
import quantstats
import multiprocessing
warnings.simplefilter(action='ignore', category=FutureWarning)
import sys
import time


data, total_candles = define_data_alphavantage('AMZN', start_year=2023, start_month=5, months=15, interval='1min')


def create_data():
    cerebro = bt.Cerebro()
    cerebro.adddata(data)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Minutes, compression=15)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Minutes, compression=60)

    cerebro.broker.setcash(starting_capital)
    cerebro.broker.setcommission(commission=commission)
    cerebro.addsizer(FixedRiskSizer)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(CommissionAnalyzer, _name='commissions')
    cerebro.addanalyzer(bt.analyzers.PyFolio, _name='PyFolio')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_analyzer')

    return cerebro

# Fitness function
def evaluate(individual):
    cerebro = create_data()

    donchian_period = max(20, min(individual[0], 50))  # Clamped between 20 and 50
    order_factor = max(0.01, min(individual[1], 0.05))  # Clamped between 0.01 and 0.05
    ichimoku_trend_factor = max(0.01, min(individual[2], 0.05))  # Clamped between 0.01 and 0.05
    risk_per_trade = max(0.001, min(individual[3], 0.01))  # Clamped between 0.001 and 0.01
    stop_distance_factor = max(0.01, min(individual[4], 0.05))  # Clamped between 0.01 and 0.05
    take_profit_distance_factor = max(0.01, min(individual[5], 0.05))  # Clamped between 0.01 and 0.05
    take_profit_trigger_factor = max(0.2, min(individual[6], 0.7))  # Clamped between 0.2 and 0.7

    cerebro.addstrategy(MyStrategy,
                        total_candles=total_candles,
                        Donchian_Period=donchian_period,
                        order_factor=order_factor,
                        ichimoku_trend_factor=ichimoku_trend_factor,
                        risk_per_trade=risk_per_trade,
                        stop_distance_factor=stop_distance_factor,
                        take_profit_distance_factor=take_profit_distance_factor,
                        take_profit_trigger_factor=take_profit_trigger_factor,
                        )

    result = cerebro.run()

    # Get results from analyzers
    drawdown = result[0].analyzers.drawdown.get_analysis().max.drawdown
    returns = result[0].broker.getvalue() - starting_capital

    # Print parameters and results
    print(f"\nParameters:")
    print(f"  donchian_period: {individual[0]}")
    print(f"  Order Factor: {individual[1]}")
    print(f"  Ichimoku Trend Factor: {individual[2]}")
    print(f"  Risk per Trade: {individual[3]}")
    print(f"  Stop Distance Factor: {individual[4]}")
    print(f"  Take Profit Distance Factor: {individual[5]}")
    print(f"  Take Profit Trigger Factor: {individual[6]}")
    print(f"Returns: ${returns:.2f}")
    print(f"Drawdown: {-drawdown:.2f}%\n")

    # Return as a tuple since DEAP minimizes the fitness function
    return returns, -drawdown


starting_capital = 10000
commission = 0.00035
n_population = 2
n_gen = 2

# Define the fitness function: maximize returns and minimize drawdown
creator.create("FitnessMulti", base.Fitness, weights=(1.0, -1.0))  # Maximize returns, minimize drawdown
creator.create("Individual", list, fitness=creator.FitnessMulti)

toolbox = base.Toolbox()

# Define ranges for each parameter
toolbox.register("attr_Donchian_Period", random.randint, 20, 50)
toolbox.register("attr_order_factor", random.uniform, 0.01, 0.05)
toolbox.register("attr_ichimoku_trend_factor", random.uniform, 0.01, 0.05)
toolbox.register("attr_risk_per_trade", random.uniform, 0.001, 0.01)
toolbox.register("attr_stop_distance_factor", random.uniform, 0.01, 0.05)
toolbox.register("attr_take_profit_distance_factor", random.uniform, 0.01, 0.05)
toolbox.register("attr_take_profit_trigger_factor", random.uniform, 0.2, 0.7)

toolbox.register("individual", tools.initCycle, creator.Individual,
                 (toolbox.attr_Donchian_Period, toolbox.attr_order_factor, toolbox.attr_ichimoku_trend_factor,
                  toolbox.attr_risk_per_trade, toolbox.attr_stop_distance_factor,
                  toolbox.attr_take_profit_distance_factor, toolbox.attr_take_profit_trigger_factor), n=1)

toolbox.register("population", tools.initRepeat, list, toolbox.individual)
toolbox.register("evaluate", evaluate)
toolbox.register("mate", tools.cxBlend, alpha=0.5)
toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=0.1, indpb=0.2)
toolbox.register("select", tools.selNSGA2)  # Multi-objective selection

def main():
    pop = toolbox.population(n_population)  # Population size
    hof = tools.HallOfFame(1)  # Hall of Fame to keep track of best individual

    # Evolve the population
    algorithms.eaSimple(pop, toolbox, cxpb=0.7, mutpb=0.3, ngen=n_gen, halloffame=hof, verbose=True)

    # Generate and save QuantStats report for the best result
    best_params = hof[0]
    cerebro = create_data()

    cerebro.addstrategy(MyStrategy,
                        total_candles=total_candles,
                        Donchian_Period=best_params[0],
                        order_factor=best_params[1],
                        ichimoku_trend_factor=best_params[2],
                        risk_per_trade=best_params[3],
                        stop_distance_factor=best_params[4],
                        take_profit_distance_factor=best_params[5],
                        take_profit_trigger_factor=best_params[6])

    result = cerebro.run()

    trade_analyzer = result[0].analyzers.trade_analyzer.get_analysis()
    drawdown = result[0].analyzers.drawdown.get_analysis().max.drawdown

    # Access and print metrics from custom analyzers
    portfolio_stats = result[0].analyzers.getbyname('PyFolio')
    ret, positions, transactions, gross_lev = portfolio_stats.get_pf_items()
    ret.index = ret.index.tz_convert(None)


    total_trades = trade_analyzer.total.total or 0
    won_trades = trade_analyzer.won.total or 0
    lost_trades = trade_analyzer.lost.total or 0
    net_profit = trade_analyzer.pnl.net.total or 0
    win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0
    max_win = trade_analyzer.won.pnl.max or 0
    avg_win = trade_analyzer.won.pnl.average or 0
    max_loss = trade_analyzer.lost.pnl.max or 0
    avg_loss = trade_analyzer.lost.pnl.average or 0
    avg_duration = trade_analyzer.len.average or 0

    print('---Best run---')
    print(f"Net Profit: {net_profit:.2f} / Net Profit Percentage: {(net_profit / starting_capital * 100):.2f}%")
    print(f"Drawdown: {-drawdown:.2f}")
    print(f"Total Won: {won_trades} / Total Lost: {lost_trades}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Max Win Amount: {max_win:.2f} / Average Win Amount: {avg_win:.2f}")
    print(f"Max Loss Amount: {max_loss:.2f} / Average Loss Amount: {avg_loss:.2f}")
    print(f"Average Trade Duration Bars: {avg_duration:.2f} - {avg_duration / 60:.2f} Hours - {avg_duration / 3600:.2f} Days")

    # Save metrics to CSV
    with open('best_metrics.csv', mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['Parameter', 'Value'])
        writer.writerow(['Donchian_Period', best_params[0]])
        writer.writerow(['order_factor', best_params[1]])
        writer.writerow(['ichimoku_trend_factor', best_params[2]])
        writer.writerow(['risk_per_trade', best_params[3]])
        writer.writerow(['stop_distance_factor', best_params[4]])
        writer.writerow(['take_profit_distance_factor', best_params[5]])
        writer.writerow(['take_profit_trigger_factor', best_params[6]])
        writer.writerow(['Total Trades', total_trades])
        writer.writerow(['Won Trades', won_trades])
        writer.writerow(['Lost Trades', lost_trades])
        writer.writerow(['Net Profit', net_profit])
        writer.writerow(['Net Profit Percentage', f"{(net_profit / starting_capital * 100):.2f}%"])
        writer.writerow(['Drawdown', f"{(-drawdown)}%"])
        writer.writerow(['Win Rate', f"{win_rate:.2f}%"])
        writer.writerow(['Max Win Amount', max_win])
        writer.writerow(['Average Win Amount', avg_win])
        writer.writerow(['Max Loss Amount', max_loss])
        writer.writerow(['Average Loss Amount', avg_loss])
        writer.writerow(['Average Trade Duration (Minutes)', avg_duration])
        writer.writerow(['Average Trade Duration (Hours)', avg_duration / 60])
        writer.writerow(['Average Trade Duration (Days)', avg_duration / 3600])

    quantstats.reports.html(ret, output='stats.html', title='Backtest results')

    pool.close()
    pool.join()
    # cerebro.plot()

if __name__ == "__main__":
    if sys.platform.startswith("win"):
        multiprocessing.freeze_support()  # Required on Windows
    start_time = time.time()  # Start tracking time

    # Use multiprocessing pool for parallel evaluations
    pool = multiprocessing.Pool()
    toolbox.register("map", pool.map)

    main()

    pool.close()
    pool.join()

    end_time = time.time()  # End time after process finishes
    total_runs = n_population * n_gen  # Calculate total runs based on population and generations
    elapsed_time = end_time - start_time  # Calculate elapsed time in seconds

    # Print the summary
    print(f"Total Runs: {total_runs}")
    print(f"Elapsed Time: {elapsed_time:.2f} seconds")