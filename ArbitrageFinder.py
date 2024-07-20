import ccxt.async_support as ccxt
import asyncio
import requests
import json


def is_connected():
    try:
        response = requests.get('https://www.google.com', timeout=5)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False

def send_telegram_message(message, chat_id="2046354806"):
    token = "7233582567:AAEGQy728PIGUL7H2fmIYve4FGFdtrpSJOM"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message
    }
    response = requests.post(url, data=payload)

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
        return ticker['last']
    except Exception as e:
        return None
    finally:
        if exchange:
            await exchange.close()

# return tooples of exchange_id and price
def get_highest_and_lowest(prices):
    if not prices:
        return None, None, None
    
    highest = max(prices.items(), key=lambda x: x[1])
    lowest = min(prices.items(), key=lambda x: x[1])

    spread = round((highest[1] - lowest[1]) / ((highest[1] + lowest[1]) / 2 ) * 100, 2)
    return highest, lowest, spread

async def main():
    assert is_connected(), "No internet connection detected"

    exchanges, symbols = load_exchanges_and_symbols()

    for symbol in symbols:

        print(f"{symbol}: ")

        tasks = [fetch_perpetual_futures_price(exchange_id, symbol) for exchange_id in exchanges]
        results = await asyncio.gather(*tasks)

        prices = {}
        for exchange_id, price in zip(exchanges, results):
            if price:
                prices[exchange_id] = price
                print(f"{exchange_id} -> {price}")

        highest, lowest, spread = get_highest_and_lowest(prices)

        print(f"{spread} -> long: {lowest}, short: {highest}")

        if not spread:
            continue

        if spread > 1:
            send_telegram_message(f"Spread for {symbol} is {spread}%")
            send_telegram_message(f"Highest: {highest[0].capitalize()} ${highest[1]:.2f}")
            send_telegram_message(f"Lowest: {lowest[0].capitalize()} ${lowest[1]:.2f}")

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except Exception as e:
            print(e)
            send_telegram_message(f"Error: {str(e)}")