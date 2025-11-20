import ccxt.async_support as ccxt
import asyncio
import time
import sys

# -------------------------------
# CONFIGURATION
# -------------------------------
# Use the lowest possible Taker fee (e.g., 0.075% for Binance if paying with BNB)
# This maximizes the chance of capturing tiny profits.
FEE_RATE = 0.00075 
INITIAL_USDT = 100.0  # Starting capital for the simulation
CHECK_INTERVAL_SECONDS = 0.5 # Fast checking is crucial for small profits

# Define the three legs of the triangle:
# We need prices for: BTC/USDT, SOL/BTC, SOL/USDT
SYMBOL_TRIANGLE = ['BTC/USDT', 'SOL/BTC', 'SOL/USDT']
BASE_CURRENCY = 'USDT' # The starting/ending currency
# -------------------------------

def calculate_path_profit(initial_amount, leg1_price, leg2_price, leg3_price):
    """
    Calculates the final amount after three trades, accounting for fees.
    Fee is applied three times (one for each leg).
    """
    # Trade 1: initial_amount -> intermediate_currency_A
    amount_a = (initial_amount / leg1_price) * (1 - FEE_RATE)
    
    # Trade 2: intermediate_currency_A -> intermediate_currency_B
    # Note: leg2_price is the price of B in terms of A (1/price if it's a quote/base swap)
    amount_b = (amount_a / leg2_price) * (1 - FEE_RATE)
    
    # Trade 3: intermediate_currency_B -> BASE_CURRENCY (USDT)
    final_amount = (amount_b * leg3_price) * (1 - FEE_RATE)
    
    profit = final_amount - initial_amount
    return final_amount, profit

def check_arbitrage(prices):
    """
    Checks two possible triangular paths and returns the most profitable one.
    """
    # Ensure all required prices are available
    if not all(k in prices for k in SYMBOL_TRIANGLE):
        return 0, "No Data", "N/A"

    # Extract required bid (sell) and ask (buy) prices
    p_btc_usdt_ask = prices['BTC/USDT'].get('ask') # Buy BTC with USDT
    p_btc_usdt_bid = prices['BTC/USDT'].get('bid') # Sell BTC for USDT
    p_sol_btc_ask = prices['SOL/BTC'].get('ask')   # Buy SOL with BTC
    p_sol_btc_bid = prices['SOL/BTC'].get('bid')   # Sell SOL for BTC
    p_sol_usdt_ask = prices['SOL/USDT'].get('ask') # Buy SOL with USDT
    p_sol_usdt_bid = prices['SOL/USDT'].get('bid') # Sell SOL for USDT

    if not all([p_btc_usdt_ask, p_btc_usdt_bid, p_sol_btc_ask, p_sol_btc_bid, p_sol_usdt_ask, p_sol_usdt_bid]):
        return 0, "Missing Price Data", "N/A"
        
    best_profit = 0
    best_path = "N/A"
    
    # ----------------------------------------------------
    # PATH 1: USDT -> BTC -> SOL -> USDT
    # 1. Buy BTC: price = p_btc_usdt_ask (USDT/BTC)
    # 2. Buy SOL: price = p_sol_btc_ask (BTC/SOL)
    # 3. Sell SOL: price = p_sol_usdt_bid (SOL/USDT)
    # ----------------------------------------------------
    # NOTE: The second trade is a BTC/SOL trade, so we divide by ask price
    final_usdt_1, profit_1 = calculate_path_profit(
        INITIAL_USDT, 
        p_btc_usdt_ask, # 1. USDT -> BTC (Buy BTC)
        p_sol_btc_ask,  # 2. BTC -> SOL (Buy SOL)
        p_sol_usdt_bid  # 3. SOL -> USDT (Sell SOL)
    )

    if profit_1 > best_profit:
        best_profit = profit_1
        best_path = "USDT -> BTC -> SOL -> USDT"

    # ----------------------------------------------------
    # PATH 2: USDT -> SOL -> BTC -> USDT (The Reverse Triangle)
    # 1. Buy SOL: price = p_sol_usdt_ask (USDT/SOL)
    # 2. Sell SOL: price = p_sol_btc_bid (SOL/BTC)
    # 3. Sell BTC: price = p_btc_usdt_bid (BTC/USDT)
    # ----------------------------------------------------
    # NOTE: The second trade is a SOL/BTC trade, so we multiply by bid price
    final_usdt_2, profit_2 = calculate_path_profit(
        INITIAL_USDT, 
        p_sol_usdt_ask, # 1. USDT -> SOL (Buy SOL)
        (1 / p_sol_btc_bid), # 2. SOL -> BTC (Sell SOL is equivalent to 1/P_BTC_SOL, where P_BTC_SOL is BTC/SOL ask)
        p_btc_usdt_bid  # 3. BTC -> USDT (Sell BTC)
    )

    if profit_2 > best_profit:
        best_profit = profit_2
        best_path = "USDT -> SOL -> BTC -> USDT"
        
    return best_profit, final_usdt_1, final_usdt_2, best_path

async def run_arbitrage():
    """Main loop to continuously check for arbitrage opportunities."""
    
    # Initialize the asynchronous CCXT client
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'timeout': 5000,
        'rateLimit': 50 # Increase rate limit for rapid polling
    })
    
    print("------------------------------------------------------------------")
    print(f"Starting Arbitrage Monitor (Triangular: BTC, SOL, USDT) on {exchange.id}")
    print(f"Initial Capital: {INITIAL_USDT:.2f} USDT | Fee Rate (per trade): {FEE_RATE * 100:.3f}%")
    print("------------------------------------------------------------------")

    while True:
        try:
            # Fetch all ticker data in a single, fast request (if supported by exchange)
            # This minimizes the risk of stale prices across the three legs.
            tickers = await exchange.fetch_tickers(SYMBOL_TRIANGLE)
            
            prices = {
                'BTC/USDT': tickers['BTC/USDT'],
                'SOL/BTC': tickers['SOL/BTC'],
                'SOL/USDT': tickers['SOL/USDT'],
            }

            # Check both arbitrage directions
            best_profit, final_usdt_1, final_usdt_2, path = check_arbitrage(prices)

            # Print status update
            sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] P1 End: {final_usdt_1:.6f} | P2 End: {final_usdt_2:.6f} | Best Profit: {best_profit:.6f} USDT \r")
            sys.stdout.flush()

            # The only condition is strictly greater than zero
            if best_profit > 0:
                print(f"\n\n=======================================================")
                print(f"🚀 OPPORTUNITY DETECTED! Profit: {best_profit:.6f} USDT")
                print(f"Path: {path}")
                print(f"Final USDT: {INITIAL_USDT + best_profit:.6f}")
                print(f"=======================================================\n")
                
                # In a REAL trading bot, the triple-trade execution sequence would go here.
                # Since this is a simulation, we just log and continue.

        except ccxt.NetworkError as e:
            # print(f"\n[Error] Network error: {e}. Retrying...")
            await asyncio.sleep(1) # Wait longer on network errors
        except ccxt.ExchangeError as e:
            # print(f"\n[Error] Exchange error: {e}. Checking again...")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"\n[Critical Error] An unexpected error occurred: {e}")
            break

        # Sleep for a fraction of a second to respect rate limits and keep fast polling
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)

# Entry point of the script
if __name__ == '__main__':
    try:
        asyncio.run(run_arbitrage())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
    except Exception as e:
        print(f"Exiting due to main error: {e}")
        
    # Close the exchange connection gracefully
    async def close_exchange():
        exchange = ccxt.binance()
        await exchange.close()
    
    asyncio.run(close_exchange())
