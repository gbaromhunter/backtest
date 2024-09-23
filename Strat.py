import backtrader as bt
from support import DonchianChannels


class MyStrategy(bt.Strategy):


    # Parameters that can be optimized for best performance for different markets or candlestick timeframes
    params = (
        ('total_candles', 0),

        ('Donchian_Period', 40),
        ('Donchian_Lookback', -1),

        ('order_factor', 0.005),
        ('ichimoku_trend_factor', 0.01),

        ('risk_per_trade', 0.003),
        ('stop_distance_factor', 0.01),
        ('take_profit_distance_factor', 0.01),
        ('take_profit_trigger_factor', 0.4),
    )

    def __init__(self):
        """Initializes all variables to be used in this strategy"""

        self.starting_value = self.broker.getvalue()  # Store the initial value at the start
        self.order = None
        self.stop_price = None
        self.take_profit_price = None
        self.trailing_profit_price = None
        self.last_value = None
        self.risk_per_trade = self.params.risk_per_trade

        self.total_candles = self.params.total_candles

        # Set the indicators

        # Set the indicators for the secondary timeframe
        self.donchian = DonchianChannels(self.data1, plot=False)
        self.donchian1 = DonchianChannels(self.data2, plot=False)
        self.ichimoku = bt.indicators.Ichimoku(self.data1, plot=False)
        self.ichimoku1 = bt.indicators.Ichimoku(self.data2, plot=False)

        # Set Flags, Checks, Conditions
        self.uptrend = self.downtrend = self.notrend = False


    def total_pnl_percentage(self):
        pnl = self.broker.getvalue() - self.starting_value
        pnl_percentage = (pnl / self.starting_value) * 100
        return pnl, pnl_percentage

    def log(self, txt, doprint=True):
        """Logs any given text with the time and date as long as doprint=True"""
        date = self.data.datetime.date(0)
        time = self.data.datetime.time(0)
        if doprint:
            print(str(date) + ' ' + str(time) + '--' + txt)

    def notify_order(self, order):
        """Run on every next iteration. Checks order status and logs accordingly"""
        if order.status in [order.Submitted, order.Accepted]:
            # Order has been submitted or accepted but not yet completed
            return

        # Log only when order is completed or rejected/margin issue
        if order.status == order.Completed:
            if order.isbuy():
                self.log('BUY   price: {:.2f}, size: {:.2f}, commission: {:.2f}'.format(
                    order.executed.price, order.executed.size, order.executed.comm))
            elif order.issell():
                self.log('SELL  price: {:.2f}, size: {:.2f}, commission: {:.2f}'.format(
                    order.executed.price, order.executed.size, order.executed.comm))
        elif order.status in [order.Rejected, order.Margin]:
            # Log only for rejected or margin issues
            self.log('ORDER REJECTED/MARGIN ISSUE - {}'.format(order.status))

        # Update the last_value only if the order was completed
        if order.status == order.Completed:
            self.last_value = order.executed.value

        # Change the order variable back to None to indicate no pending order
        self.order = None

    def notify_trade(self, trade):
        """Run on every next iteration. Logs data on every trade when closed."""
        trade_pnl = (trade.pnlcomm / self.last_value) * 100
        if trade.isclosed:
            pnl, pnl_percentage = self.total_pnl_percentage()
            self.log('CLOSED   Gross P/L: {:.2f}, Net P/L: {:.2f}, P/L Percentage: {:.2f}%, Current Capital: {:.2f}, Total P/L: {:.2f}, Total P/L Percentage: {:.2f}%'.format(trade.pnl, trade.pnlcomm, trade_pnl, self.broker.getvalue(), pnl, pnl_percentage))
            if trade.pnlcomm > 0: self.log('TAKE PROFIT')
            if trade.pnlcomm <= 0: self.log('STOP LOSS')

    def stop(self):
        pass

    def define_trend(self):
        senkou_span_a = self.ichimoku1.lines.senkou_span_a[0]
        senkou_span_b = self.ichimoku1.lines.senkou_span_b[0]
        close_price = self.data0.close[0]

        max_senkou = max(senkou_span_a, senkou_span_b)
        minimum_distance = max_senkou * self.params.ichimoku_trend_factor

        if close_price > max_senkou + minimum_distance:
            self.uptrend, self.downtrend, self.notrend = True, False, False
        elif close_price < min(senkou_span_a, senkou_span_b) - minimum_distance:
            self.uptrend, self.downtrend, self.notrend = False, True, False
        else:
            self.uptrend, self.downtrend, self.notrend = False, False, True

    def check_long_condition(self):
        """Check if the Chikou Span has broken the Kumo upwards (long condition)."""
        chikou_span = self.ichimoku.lines.chikou_span[0]
        senkou_span_a = self.ichimoku.lines.senkou_span_a[-27]
        senkou_span_b = self.ichimoku.lines.senkou_span_b[-27]

        # Chikou Span crosses above the Kumo (upper cloud)
        if chikou_span > max(senkou_span_a, senkou_span_b):
            return True
        return False

    def check_short_condition(self):
        """Check if the Chikou Span has broken the Kumo downwards (short condition)."""
        chikou_span = self.ichimoku.lines.chikou_span[0]
        senkou_span_a = self.ichimoku.lines.senkou_span_a[-27]
        senkou_span_b = self.ichimoku.lines.senkou_span_b[-27]

        # Chikou Span crosses below the Kumo (lower cloud)
        if chikou_span < min(senkou_span_a, senkou_span_b):
            return True
        return False

    def open_an_order(self):
        """
        A helper function to calculate the stop-loss and take-profit prices
        based on the current position type (long or short) determined by conditions.

        :return: (stop_price, take_profit_price) tuple if valid, otherwise (None, None).
        """
        if self.check_long_condition():  # Long condition detected
            self.stop_price = self.donchian.lines.dcl[0] * (1 - self.params.stop_distance_factor)
            self.take_profit_price = self.donchian.lines.dch[0] * (1 + self.params.take_profit_distance_factor)
            self.order = self.buy()  # Place the buy order
            self.log('Long placed')
            return True
        elif self.check_short_condition():  # Short condition detected
            self.stop_price = self.donchian.lines.dch[0] * (1 + self.params.stop_distance_factor)
            self.take_profit_price = self.donchian.lines.dcl[0] * (1 - self.params.take_profit_distance_factor)
            self.order = self.sell()  # Place the sell order
            self.log('Short placed')
            return True
        return False


    def stop_loss_logic(self):
        # Long position stop loss logic
        if self.position.size > 0:
            # Close long position if price falls below or equal to the stop price
            if self.data0.close[0] <= self.stop_price:
                self.close()
                return True

        # Short position stop loss logic
        elif self.position.size < 0:
            # Close short position if price rises above or equal to the stop price
            if self.data0.close[0] >= self.stop_price:
                self.close()
                return True

        return False

    def take_profit_logic(self):
        # Long position logic
        if self.position.size > 0:
            if self.take_profit_price:
                # Adjust trailing stop if price moves above the take profit trigger factor
                if self.data0.close[0] >= self.take_profit_price * (1 - self.params.take_profit_trigger_factor):
                    self.take_profit_price = self.data0.close[0]
                    self.trailing_profit_price = self.take_profit_price - (
                                self.take_profit_price * self.params.take_profit_distance_factor)
            if self.trailing_profit_price:
                # Close position if price falls below trailing stop
                if self.data0.close[0] <= self.trailing_profit_price:
                    self.close()
                    self.trailing_profit_price = None
                    self.take_profit_price = None
                    return True
        # Short position logic
        elif self.position.size < 0:
            if self.take_profit_price:
                # Adjust trailing stop if price moves below the take profit trigger factor
                if self.data0.close[0] <= self.take_profit_price * (1 + self.params.take_profit_trigger_factor):
                    self.take_profit_price = self.data0.close[0]
                    self.trailing_profit_price = self.take_profit_price + (
                                self.take_profit_price * self.params.take_profit_distance_factor)
            if self.trailing_profit_price:
                # Close position if price rises above trailing stop
                if self.data0.close[0] >= self.trailing_profit_price:
                    self.close()
                    self.trailing_profit_price = None
                    self.take_profit_price = None
                    return True
        return False

    def next(self):
        """Runs for every candlestick. Checks conditions to enter and exit trades."""

        """Runs on each candle and handles the entire trading logic."""

        # Check if there is an active order
        if self.order: return

        if not self.position:
            # Calculate stop-loss and take-profit
            if self.open_an_order(): return

        # Handle stop-loss and take-profit logic if a position is already open
        if self.stop_loss_logic(): return
        if self.take_profit_logic(): return

        # Close the last trade to not influence final results with an open trade
        if len(self.data0) == self.total_candles -1:
            if self.position:
                self.order = self.close()
                self.log('Closing the last trade')