import math
from backtrader.utils.py3 import itervalues
from backtrader import Analyzer, TimeFrame, Sizer, Indicator
from backtrader.mathsupport import average, standarddev
from backtrader.analyzers import TimeReturn, AnnualReturn
import backtrader as bt


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