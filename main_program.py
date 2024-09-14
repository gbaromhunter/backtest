import random
from deap import base, creator, tools, algorithms
import backtrader as bt
from Strat import MyStrategy
from support import define_data_alphavantage, FixedRiskSizer, CommissionAnalyzer
import quantstats
import os

# Define the fitness function: maximize returns and minimize drawdown
creator.create("FitnessMulti", base.Fitness, weights=(1.0, -1.0))  # Maximize returns, minimize drawdown
creator.create("Individual", list, fitness=creator.FitnessMulti)

starting_capital = 10000
commission = 0.00035

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


# Fitness function
def evaluate(individual):
    cerebro = bt.Cerebro()
    data, _ = define_data_alphavantage('AMZN', start_year=2023, start_month=5, months=15, interval='1min')
    cerebro.adddata(data)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Minutes, compression=15)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Minutes, compression=60)

    cerebro.addstrategy(MyStrategy,
                        Donchian_Period=individual[0],
                        order_factor=individual[1],
                        ichimoku_trend_factor=individual[2],
                        risk_per_trade=individual[3],
                        stop_distance_factor=individual[4],
                        take_profit_distance_factor=individual[5],
                        take_profit_trigger_factor=individual[6])

    cerebro.broker.setcash(starting_capital)
    cerebro.broker.setcommission(commission=commission)
    cerebro.addsizer(FixedRiskSizer)
    cerebro.addanalyzer(CommissionAnalyzer)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

    result = cerebro.run()

    # Get results from analyzers
    drawdown = result[0].analyzers.drawdown.get_analysis().max.drawdown
    returns = result[0].broker.getvalue() - starting_capital

    # Print parameters and results
    print("\nEvaluation Result:")
    print(f"Parameters:")
    print(f"  Donchian_Period: {individual[0]}")
    print(f"  Order Factor: {individual[1]}")
    print(f"  Ichimoku Trend Factor: {individual[2]}")
    print(f"  Risk per Trade: {individual[3]}")
    print(f"  Stop Distance Factor: {individual[4]}")
    print(f"  Take Profit Distance Factor: {individual[5]}")
    print(f"  Take Profit Trigger Factor: {individual[6]}")
    print(f"Returns: ${returns:.2f}")
    print(f"Drawdown: {drawdown:.2f}%\n")

    # Return as a tuple (returns, -drawdown) since DEAP minimizes the fitness function
    return (returns, -drawdown)


toolbox.register("evaluate", evaluate)
toolbox.register("mate", tools.cxBlend, alpha=0.5)
toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=1, indpb=0.2)
toolbox.register("select", tools.selTournament, tournsize=3)


def main():
    pop = toolbox.population(n=10)  # Population size
    hof = tools.HallOfFame(1)  # Hall of Fame to keep track of best individual

    # Evolve the population
    algorithms.eaSimple(pop, toolbox, cxpb=0.7, mutpb=0.3, ngen=10, halloffame=hof, verbose=True)

    # Best individual found
    print(f"Best individual: {hof[0]}")

    # Optionally, save best parameters to a file or use them for further analysis
    with open('best_parameters.txt', 'w') as f:
        f.write(f"Best individual: {hof[0]}\n")

    # Generate and save QuantStats report for the best result
    best_params = hof[0]
    cerebro = bt.Cerebro()
    data, _ = define_data_alphavantage('AMZN', start_year=2023, start_month=5, months=15, interval='1min')
    cerebro.adddata(data)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Minutes, compression=15)
    cerebro.resampledata(data, timeframe=bt.TimeFrame.Minutes, compression=60)

    cerebro.addstrategy(MyStrategy,
                        Donchian_Period=best_params[0],
                        order_factor=best_params[1],
                        ichimoku_trend_factor=best_params[2],
                        risk_per_trade=best_params[3],
                        stop_distance_factor=best_params[4],
                        take_profit_distance_factor=best_params[5],
                        take_profit_trigger_factor=best_params[6])

    cerebro.broker.setcash(starting_capital)
    cerebro.broker.setcommission(commission=commission)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

    result = cerebro.run()

    portfolio_stats = result[0].analyzers.getbyname('returns')
    ret, positions, transactions, gross_lev = portfolio_stats.get_pf_items()
    ret.index = ret.index.tz_convert(None)

    report_dir = 'quantstats_reports'
    if not os.path.exists(report_dir):
        os.makedirs(report_dir)

    report_filename = os.path.join(report_dir, "quantstats_best_report.html")
    quantstats.reports.html(ret, output=report_filename, title='Backtest results')
    print(f"QuantStats report saved: {report_filename}")


if __name__ == "__main__":
    main()
