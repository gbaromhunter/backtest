import backtrader as bt
from support import DonchianChannels


class MyStrategy(bt.Strategy):


    # Parameters that can be optimized for best performance for different markets or candlestick timeframes
    params = (
        ('Donchian_Period', 20),
        ('Donchian_Lookback', -1),
        ('RSI_Period', 14),

        ('buy_treshold', 0.10),
        ('stop_distance_factor', 0.03),
        ('take_profit_distance_factor', 0.03),

    )

    def __init__(self):
        '''Initializes all variables to be used in this strategy'''

        self.starting_value = self.broker.getvalue()  # Store the initial value at the start
        self.order = None
        self.stop_price = None
        self.take_profit_price = None
        self.trailing_profit_price = None
        self.last_value = None

        self.total_candles = len(self.data.array)

        # Set the indicators
        self.donchian = DonchianChannels()
        self.rsi = bt.indicators.RelativeStrengthIndex()

        # Set the indicators for the secondary timeframe
        self.donchian1 = DonchianChannels()
        self.rsi1 = bt.indicators.RelativeStrengthIndex()


        # Set Flags, Checks, Conditions
        self.trend = None


    def total_pnl_percentage(self):
        pnl = self.broker.getvalue() - self.starting_value
        pnl_percentage = (pnl / self.starting_value) * 100
        return pnl, pnl_percentage

    def log(self, txt, doprint=True):
        '''Logs any given text with the time and date as long as doprint=True'''
        date = self.data.datetime.date(0)
        time = self.data.datetime.time(0)
        if doprint:
            print(str(date) + ' ' + str(time) + '--' + txt)

    def notify_order(self, order):
        '''Run on every next iteration. Checks order status and logs accordingly'''
        if order.status in [order.Submitted, order.Accepted]:
            return
        elif order.status == order.Completed:
            if order.isbuy():
                self.log('BUY   price: {:.2f}, value: {:.2f}, commission: {:.2f}'.format(order.executed.price, order.executed.value, order.executed.comm))
            if order.issell():
                self.log('SELL   price: {:.2f}, commission: {:.2f}'.format(order.executed.price, order.executed.comm))
        elif order.status in [order.Rejected, order.Margin]:
            self.log('Order Rejected/Margin')

        self.last_value = order.executed.value

        # change order variable back to None to indicate no pending order
        self.order = None

    def notify_trade(self, trade):
        '''Run on every next iteration. Logs data on every trade when closed.'''
        trade_pnl = (trade.pnlcomm / (self.last_value)) * 100
        if trade.isclosed:
            pnl, pnl_percentage = self.total_pnl_percentage()
            self.log('CLOSED   Gross P/L: {:.2f}, Net P/L: {:.2f}, P/L Percentage: {:.2f}%, Current Capital: {:.2f}, Total P/L: {:.2f}, Total P/L Percentage: {:.2f}%'.format(trade.pnl, trade.pnlcomm, trade_pnl, self.broker.getvalue(), pnl, pnl_percentage))
            if trade.pnlcomm > 0: self.log('TAKE PROFIT')
            if trade.pnlcomm <= 0: self.log('STOP LOSS')

    def stop(self):
        pass

    def buy_condition(self):
        # Check that no position is opened
        if self.position.size == 0:
            if self.rsi[0] <= 30:
                # Check if price is within percentage of the lower Donchian
                if self.data.close[0] <= self.donchian.lines.dcl[0] * (1 + self.params.buy_treshold):
                    self.stop_price = self.donchian.lines.dcl[0] * (1 - self.params.stop_distance_factor)
                    self.take_profit_price = self.donchian.lines.dch[0] * (1 + self.params.take_profit_distance_factor)
                    self.order = self.buy()
                    self.log(f'Lower donchian line: {self.donchian.lines.dcl[0]}, stop loss: {self.stop_price}, take_profit: {self.take_profit_price}')
                    return True

    def stop_loss_logic(self):
        if self.position.size > 0:
            if self.data.close[0] <= self.stop_price:
                self.close()
                return True

    def take_profit_logic(self):
        if self.position.size > 0:
            if self.take_profit_price:
                if self.data.close[0] >= self.take_profit_price:
                    self.take_profit_price = self.data.close[0]
                    self.trailing_profit_price = self.take_profit_price * (1 - self.params.take_profit_distance_factor)
            if self.trailing_profit_price:
                if self.data.close[0] <= self.trailing_profit_price:
                    self.close()
                    self.trailing_profit_price = None
                    self.take_profit_price = None
                    return True

    def next(self):
        '''Runs for every candlestick. Checks conditions to enter and exit trades.'''
        # Check if there is already an order

        if self.order:
            return

        # BUY
        self.buy_condition()

        # STOP LOSS
        if self.stop_loss_logic():
            return

        # TAKE PROFIT
        self.take_profit_logic()


        # Close the last trade to not influence final results with an open trade
        if  len(self.data) == self.total_candles - 1:  # Check if the last few data points
            if self.position:
                self.order = self.close()