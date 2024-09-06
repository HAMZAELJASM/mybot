import os
import time
import requests
import pandas as pd
import logging
from typing import Optional, Tuple
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler
import asyncio

# Define the token for the Telegram bot
TOKEN: str = '7506759112:AAFTN1BRl_wn1k91HRKILGC1slCCcBIYPA0'

# Path for saving images
BASE_PHOTO_DIR: str = 'photos'
os.makedirs(BASE_PHOTO_DIR, exist_ok=True)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Function to capture a detailed screenshot of the BTC chart from Binance
def capture_btc_chart_screenshot() -> Optional[str]:
    """Capture a detailed screenshot of the BTC chart from Binance."""
    try:
        options = Options()
        options.headless = True  # Run in headless mode for efficiency
        options.add_argument("--window-size=1920x1080")  # Set window size to ensure full capture

        # Set up WebDriver
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get('https://www.binance.com/en/trade/BTC_USDT')

        # Allow time for the page to load fully
        time.sleep(15)

        # Capture the screenshot
        file_path = os.path.join(BASE_PHOTO_DIR, 'btc_chart.png')
        driver.save_screenshot(file_path)
        driver.quit()
        return file_path
    except Exception as e:
        logger.error(f"Error capturing BTC chart screenshot: {e}")
        return None

# Fetch data functions
def fetch_data(symbol: str, interval: str = '15m') -> Optional[list]:
    """Fetch market data from Binance API."""
    try:
        url = 'https://api.binance.com/api/v3/klines'
        params = {'symbol': symbol, 'interval': interval, 'limit': 100}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching data: {e}")
        return None

def fetch_order_book(symbol: str) -> Optional[dict]:
    """Fetch order book data from Binance API."""
    try:
        url = 'https://api.binance.com/api/v3/depth'
        params = {'symbol': symbol, 'limit': 100}
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.error(f"Error fetching order book data: {e}")
        return None

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period, min_periods=1).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period, min_periods=1).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series: pd.Series, short_window: int = 12, long_window: int = 26, signal_window: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD indicators."""
    short_ema = series.ewm(span=short_window, adjust=False).mean()
    long_ema = series.ewm(span=long_window, adjust=False).mean()
    macd = short_ema - long_ema
    macd_signal = macd.ewm(span=signal_window, adjust=False).mean()
    return macd, macd_signal, macd - macd_signal

def identify_support_resistance(df: pd.DataFrame) -> Tuple[float, float]:
    """Identify support and resistance levels."""
    return df['low'].min(), df['high'].max()

def scalping_strategy(df: pd.DataFrame) -> Tuple[str, str, str]:
    """Identify scalping opportunities based on price action."""
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    if latest['close'] > latest['open']:
        entry_zone = latest['low'] * 0.99
        stop_loss = latest['low'] * 0.98
        take_profit = latest['high'] * 1.01
        return 'BUY', entry_zone, stop_loss, take_profit
    elif latest['close'] < latest['open']:
        entry_zone = latest['high'] * 1.01
        stop_loss = latest['high'] * 1.02
        take_profit = latest['low'] * 0.99
        return 'SELL', entry_zone, stop_loss, take_profit
    return 'HOLD', 'N/A', 'N/A', 'N/A'

def identify_candle_patterns(df: pd.DataFrame) -> str:
    """Identify Japanese candlestick patterns."""
    latest = df.iloc[-1]

    # Check for Doji
    if abs(latest['open'] - latest['close']) < 0.01 * (latest['high'] - latest['low']):
        return "Doji: Indicates a potential reversal or indecision in the market."

    # Check for red candle
    if latest['close'] < latest['open']:
        return "Red Candle: Indicates selling pressure and a downtrend."

    return "No significant pattern identified."

def analyze_data(data: list) -> str:
    """Analyze market data and generate a simplified report."""
    try:
        # Convert data to DataFrame
        df = pd.DataFrame(data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        
        # Process data
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

        # Calculate indicators
        df['rsi'] = calculate_rsi(df['close'])
        df['macd'], df['macd_signal'], df['macd_diff'] = calculate_macd(df['close'])

        # Identify support and resistance
        support, resistance = identify_support_resistance(df)

        # Determine recommendation based on scalping strategy
        scalping_rec, entry_zone, stop_loss, take_profit = scalping_strategy(df)

        # Identify candle patterns
        candle_patterns = identify_candle_patterns(df)

        # Create the final report with entry and exit points
        analysis = (
            f"**Recommendation**: {scalping_rec}\n"
            f"**Entry Zone**: {entry_zone}\n"
            f"**Stop Loss**: {stop_loss}\n"
            f"**Take Profit**: {take_profit}\n"
            f"**Support Level**: {support}\n"
            f"**Resistance Level**: {resistance}\n"
            f"**Candlestick Pattern**: {candle_patterns}\n"
        )
        return analysis

    except Exception as e:
        logger.error(f"Error in analyze_data: {e}")
        return "حدث خطأ أثناء تحليل البيانات."

def strategy_data_integration(symbol: str, interval: str = '15m') -> str:
    """Integrate strategy with data fetching and analysis."""
    data = fetch_data(symbol, interval)
    if data:
        analysis = analyze_data(data)
        return analysis
    return 'لم أتمكن من الحصول على بيانات السوق. حاول مرة أخرى لاحقًا.'

async def start(update: Update, context: CallbackContext) -> None:
    """Handle the /start command."""
    await update.message.reply_text(
        "مرحبا! أنا بوت تحليل سوق العملات الرقمية. استخدم الأزرار أدناه للحصول على معلومات.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("توليد تحليل السوق", callback_data='generate_analysis')],
            [InlineKeyboardButton("أرسل لقطة شاشة للسوق BTC", callback_data='send_screenshot')],
            [InlineKeyboardButton("حاسبة الربح والخسارة", callback_data='profit_calculator')]
        ])
    )

async def button(update: Update, context: CallbackContext) -> None:
    """Button callback handler."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'generate_analysis':
        # Generate market analysis
        analysis = strategy_data_integration('BTCUSDT')
        await query.edit_message_text(analysis)
    
    elif data == 'send_screenshot':
        # Capture and send BTC chart screenshot
        file_path = capture_btc_chart_screenshot()
        if file_path:
            await query.edit_message_text('يرجى الانتظار قليلاً، أرسل لقطة الشاشة لمخطط BTC الآن.')
            with open(file_path, 'rb') as photo:
                await query.message.reply_photo(photo=photo, caption='لقطة شاشة لمخطط BTC')
        else:
            await query.edit_message_text('حدث خطأ أثناء التقاط لقطة الشاشة.')

    elif data == 'profit_calculator':
        # Placeholder for profit calculator functionality
        await query.edit_message_text('أداة حساب الربح والخسارة قيد التطوير. شكرًا على صبرك.')

if __name__ == '__main__':
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))

    # Run the bot
    asyncio.run(application.run_polling())
