import ccxt.async_support as ccxt
import asyncio
import requests
from decimal import Decimal
import json

# Constants
MAKER_FEE = Decimal('0')#Decimal('0.0002')  # 0.0200%
TAKER_FEE = Decimal('0')#Decimal('0.0005')  # 0.0500%
MIN_OPEN_SPREAD = Decimal('0.01')  # 1%
CLOSE_SPREAD = Decimal('0.002')  # 0.2%
LEVERAGE = 20
INITIAL_BALANCE = Decimal('1000')  # Total balance across all exchanges

def is_connected():
    try:
        response = requests.get('https://www.google.com', timeout=5)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False

def load_exchanges_and_symbols(filename='config.json'):
    try:
        with open(filename, 'r') as file:
            data = json.load(file)
            exchanges = data.get('exchanges', [])
            symbols = data.get('symbols', [])
        return exchanges, symbols
    except FileNotFoundError:
        print(f"Config file {filename} not found. Using default values.")
        return ['binance', 'bybit', 'okex', 'bitget', 'bitmart', 'bitmex', 'bybit', 'coinex', 'gate', 'kucoinfutures'], \
               ['BTC', 'ETH', "BNB", "SOL", "XRP", "TON", "DOGE", "ADA", "TRX", "SHIB", "DOT", "LINK", "BCH", "NEAR", "LTC", "MATIC", "PEPE", "UNI", "ICP", "KAS", "FET", "ETC", "APT", "XLM", "XMR", "MNT", "STX", "MKR", "HBAR", "OKB", "RNDR", "FIL", "CRO", "ARB", "VET", "WIF", "ATOM", "INJ", "TAO", "IMX", "SUI", "OP", "FDUSD", "AR", "GRT", "BONK", "FLOKI", "LDO", "NOT", "BGB", "RUNE", "THETA", "ONDO", "AAVE", "HNT"]
    except json.JSONDecodeError:
        print(f"Error decoding JSON from {filename}. Using default values.")
        return ['binance', 'bybit', 'okex', 'bitget', 'bitmart', 'bitmex', 'bybit', 'coinex', 'gate', 'kucoinfutures'], \
               ['BTC', 'ETH', "BNB", "SOL", "XRP", "TON", "DOGE", "ADA", "TRX", "SHIB", "DOT", "LINK", "BCH", "NEAR", "LTC", "MATIC", "PEPE", "UNI", "ICP", "KAS", "FET", "ETC", "APT", "XLM", "XMR", "MNT", "STX", "MKR", "HBAR", "OKB", "RNDR", "FIL", "CRO", "ARB", "VET", "WIF", "ATOM", "INJ", "TAO", "IMX", "SUI", "OP", "FDUSD", "AR", "GRT", "BONK", "FLOKI", "LDO", "NOT", "BGB", "RUNE", "THETA", "ONDO", "AAVE", "HNT"]

def send_telegram_message(message, chat_id="2046354806"):
    token = "7233582567:AAEGQy728PIGUL7H2fmIYve4FGFdtrpSJOM"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message
    }
    response = requests.post(url, data=payload)

async def fetch_perpetual_futures_price(exchange_id, symbol):
    exchange = None
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({
            'enableRateLimit': True,
        })
        await exchange.load_markets()
        
        market = exchange.market(f"{symbol}/USDT:USDT")
        ticker = await exchange.fetch_ticker(market['symbol'])
        return Decimal(str(ticker['last']))
    except Exception as e:
        return None
    finally:
        if exchange:
            await exchange.close()

def calculate_spread(price1, price2):
    return abs(price1 - price2) / ((price1 + price2) / 2)

class ArbitrageSimulator:
    def __init__(self, initial_balance):
        self.initial_balance = Decimal(str(initial_balance))
        self.cash_balance = self.initial_balance
        self.open_trades = {}
        self.trade_history = []

    def open_trade(self, symbol, long_exchange, short_exchange, long_price, short_price, amount):
        if self.has_open_trade(symbol, long_exchange, short_exchange):
            send_telegram_message(f"Trade already exists for {symbol} between {long_exchange} and {short_exchange}")
            return False

        trade_size = (self.calculate_total_balance() * 2) / LEVERAGE
        position_size = trade_size / 2

        if position_size > self.cash_balance:
            send_telegram_message(f"Insufficient balance to open trade for {symbol}")
            return False

        long_fee = position_size * TAKER_FEE
        short_fee = position_size * TAKER_FEE

        trade = {
            'symbol': symbol,
            'long': {'exchange': long_exchange, 'price': long_price, 'amount': amount},
            'short': {'exchange': short_exchange, 'price': short_price, 'amount': amount},
            'fees': long_fee + short_fee,
            'position_size': position_size
        }

        self.open_trades[symbol] = trade
        self.cash_balance -= position_size + long_fee + short_fee
        
        self.trade_history.append({
            'action': 'open',
            'trade': trade,
            'cash_balance': self.cash_balance,
            'total_balance': self.calculate_total_balance()
        })
        
        return True

    def close_trade(self, symbol, long_price, short_price):
        if symbol not in self.open_trades:
            return

        trade = self.open_trades[symbol]
        long_pnl = (long_price - trade['long']['price']) * trade['long']['amount']
        short_pnl = (trade['short']['price'] - short_price) * trade['short']['amount']

        close_long_fee = trade['long']['amount'] * long_price * TAKER_FEE
        close_short_fee = trade['short']['amount'] * short_price * TAKER_FEE

        total_pnl = long_pnl + short_pnl - close_long_fee - close_short_fee - trade['fees']

        self.cash_balance += trade['position_size'] + total_pnl
        
        closed_trade = {
            'symbol': symbol,
            'open': trade,
            'close': {
                'long_price': long_price,
                'short_price': short_price,
                'pnl': total_pnl
            }
        }
        
        self.trade_history.append({
            'action': 'close',
            'trade': closed_trade,
            'cash_balance': self.cash_balance,
            'total_balance': self.calculate_total_balance()
        })

        del self.open_trades[symbol]

    def evaluate_open_trade(self, symbol, prices):
        if symbol not in self.open_trades:
            return False

        trade = self.open_trades[symbol]
        long_exchange = trade['long']['exchange']
        short_exchange = trade['short']['exchange']

        if long_exchange not in prices or short_exchange not in prices:
            return False

        current_long_price = prices[long_exchange]
        current_short_price = prices[short_exchange]
        current_spread = calculate_spread(current_long_price, current_short_price)

        if current_spread < CLOSE_SPREAD:
            self.close_trade(symbol, current_long_price, current_short_price)
            return True

        return False

    def has_open_trade(self, symbol, exchange1, exchange2):
        if symbol in self.open_trades:
            trade = self.open_trades[symbol]
            if (trade['long']['exchange'] == exchange1 and trade['short']['exchange'] == exchange2) or \
               (trade['long']['exchange'] == exchange2 and trade['short']['exchange'] == exchange1):
                return True
        return False

    def calculate_total_balance(self, current_prices=None):
        total = self.cash_balance
        for symbol, trade in self.open_trades.items():
            if current_prices and symbol in current_prices:
                long_exchange = trade['long']['exchange']
                short_exchange = trade['short']['exchange']
                if long_exchange in current_prices[symbol] and short_exchange in current_prices[symbol]:
                    current_long_price = current_prices[symbol][long_exchange]
                    current_short_price = current_prices[symbol][short_exchange]
                    
                    long_value = trade['long']['amount'] * current_long_price
                    short_value = trade['short']['amount'] * current_short_price

                    current_position_value = long_value - short_value + trade['position_size']
                    
                    total += current_position_value
                else:
                    total += trade['position_size']
            else:
                total += trade['position_size']
        return total

    def print_current_status(self, current_prices):
        total_balance = self.calculate_total_balance(current_prices)
        send_telegram_message(f"\nCurrent Status:")
        send_telegram_message(f"Initial Balance: {self.initial_balance}")
        send_telegram_message(f"Cash Balance: {self.cash_balance}")
        send_telegram_message(f"Open Positions:")
        for symbol, trade in self.open_trades.items():
            long_exchange = trade['long']['exchange']
            short_exchange = trade['short']['exchange']
            if symbol in current_prices and long_exchange in current_prices[symbol] and short_exchange in current_prices[symbol]:
                current_long_price = current_prices[symbol][long_exchange]
                current_short_price = current_prices[symbol][short_exchange]
                
                long_value = trade['long']['amount'] * current_long_price
                short_value = trade['short']['amount'] * current_short_price

                original_position_size = trade['position_size']

                current_position_value = long_value - short_value + original_position_size
    
                pnl = current_position_value - original_position_size
                
                send_telegram_message(f"  {symbol}: Original Size: {original_position_size:.4f}, "
                    f"Current Value: {current_position_value:.4f}, "
                    f"P/L: {pnl:.4f}")
            else:
                send_telegram_message(f"  {symbol}: Position Value: Unable to calculate (missing current prices)")
        send_telegram_message(f"Total Balance: {total_balance}")
        send_telegram_message(f"Profit/Loss: {total_balance - self.initial_balance}")

    def print_trade_history(self):
        send_telegram_message("\nTrade History:")
        for entry in self.trade_history:
            if entry['action'] == 'open':
                trade = entry['trade']
                send_telegram_message(f"Opened {trade['symbol']} - Long: {trade['long']['exchange']} @ {trade['long']['price']}, "
                      f"Short: {trade['short']['exchange']} @ {trade['short']['price']}, "
                      f"Amount: {trade['long']['amount']}, Cash Balance: {entry['cash_balance']}, "
                      f"Total Balance: {entry['total_balance']}")
            elif entry['action'] == 'close':
                trade = entry['trade']
                send_telegram_message(f"Closed {trade['symbol']} - PnL: {trade['close']['pnl']}, "
                      f"Cash Balance: {entry['cash_balance']}, Total Balance: {entry['total_balance']}")

async def main(simulator):
    assert is_connected(), "No internet connection detected"

    exchanges, symbols = load_exchanges_and_symbols()
    
    current_prices = {symbol: {} for symbol in symbols}

    for symbol in symbols:
        tasks = [fetch_perpetual_futures_price(exchange_id, symbol) for exchange_id in exchanges]
        results = await asyncio.gather(*tasks)

        prices = {}
        for exchange_id, price in zip(exchanges, results):
            if price:
                prices[exchange_id] = price
                current_prices[symbol][exchange_id] = price
                #print(f"{exchange_id} -> {price}")

        # Evaluate and potentially close existing trade
        trade_closed = simulator.evaluate_open_trade(symbol, prices)
        if trade_closed:
            send_telegram_message(f"Closed trade for {symbol}. New cash balance: {simulator.cash_balance}")
        else:
            # Look for new trading opportunity
            sorted_prices = sorted(prices.items(), key=lambda x: x[1])
            lowest = sorted_prices[0]
            highest = sorted_prices[-1]
            spread = calculate_spread(lowest[1], highest[1])

            send_telegram_message(f"{symbol} -> Spread: {spread:.4f} (long: {lowest[0]} {lowest[1]}, short: {highest[0]} {highest[1]})")

            if spread >= MIN_OPEN_SPREAD and not simulator.has_open_trade(symbol, lowest[0], highest[0]):
                trade_size = (simulator.calculate_total_balance() * 2) / LEVERAGE
                amount = trade_size / 2 / lowest[1]
                if simulator.open_trade(symbol, lowest[0], highest[0], lowest[1], highest[1], amount):
                    send_telegram_message(f"Opened trade for {symbol}. New cash balance: {simulator.cash_balance}")
                else:
                    send_telegram_message(f"Failed to open trade for {symbol}.")

            if spread > Decimal('0.01'):
                send_telegram_message(f"Spread for {symbol} is {spread*100:.2f}%")
                send_telegram_message(f"Highest: {highest[0].capitalize()} ${highest[1]:.2f}")
                send_telegram_message(f"Lowest: {lowest[0].capitalize()} ${lowest[1]:.2f}")

    simulator.print_current_status(current_prices)
    simulator.print_trade_history()

if __name__ == "__main__":
    simulator = ArbitrageSimulator(INITIAL_BALANCE)
    while True:
        try:
            asyncio.run(main(simulator))
        except Exception as e:
            send_telegram_message(f"Error: {str(e)}")