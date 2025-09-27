import os
import asyncio
from datetime import datetime
from datetime import datetime
from typing import Dict, List, Optional, Any
from aiogram import Bot, Dispatcher, types, Router
from telethon.errors import SessionPasswordNeededError, AuthKeyError
from aiogram.client.session import aiohttp
from aiogram.fsm.storage.memory import MemoryStorage
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, AuthKeyError, ApiIdInvalidError
from aiogram.filters import Command
from dotenv import load_dotenv
import sqlite3
import random
import textwrap
import re
import base64
import binascii
from PIL import Image, ImageDraw, ImageFont
from aiogram.utils.keyboard import InlineKeyboardBuilder
from deep_translator import GoogleTranslator
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, message
import qrcode
from aiogram.fsm.context import FSMContext
from telethon import TelegramClient
from aiogram.types import InputFile
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.channels import (
    CreateChannelRequest,
)
from telethon.tl.types import ChatAdminRights
from telethon.tl.functions.messages import ExportChatInviteRequest
 
import telethon.tl.functions.channels
from telethon.tl.types import ChatAdminRights
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest
from telethon.tl.types import ChatAdminRights
from aiogram import Bot
import time
from aiogram.filters import Command
import logging
from telethon.errors import SessionPasswordNeededError, FloodWaitError, RPCError

# Configure logging for detailed debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



# Load environment variables
load_dotenv()

# Initialize bot
bot = Bot(token=os.getenv("BOT_TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Telethon credentials
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
# TELEGRAM_SESSION removed - now using string sessions
BOT_USERNAME = os.getenv("BOT_USERNAME")
# Connect to SQLite DB
DB_PATH = os.path.join(os.path.dirname(__file__), "escrow_bot.db")



# ========================
# CONSTANTS
# ========================
MIN_BTC_DEPOSIT = 0.0001
MAX_GROUP_MEMBERS = 2  # Only buyer and seller allowed
SUPPORTED_LANGUAGES = {
    'en': 'English',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'it': 'Italian',
    'pt': 'Portuguese',
    'ru': 'Russian',
    'ar': 'Arabic',
    'sw': 'Swahili',
    'rw': 'Kinyarwanda'
}
DEFAULT_LANGUAGE = 'en'

# ========================
# BANNER DESIGNS
# ========================
BANNERS = {
    "welcome": "https://i.imgur.com/J5q7W3N.png",
    "escrow_created": "https://i.imgur.com/V7GZQzP.png",
    "payment_verified": "https://i.imgur.com/P9W3XKk.png",
    "funds_released": "https://i.imgur.com/L8M9R2H.png",
    "qr_code": "https://i.imgur.com/K9jJY7F.png",
    "admin": "https://i.imgur.com/F5G8WX9.png",
    "error": "https://i.imgur.com/9JQZ2Y7.png",
    "stats": "https://i.imgur.com/X8QZ2Y7.png",
    "dispute": "https://i.imgur.com/D8M9R2H.png",
    "rating": "https://i.imgur.com/R8M9R2H.png"
}


# Coin mapping for different APIs
COIN_MAPPING = {
    'BTC': {
        'coinbase': 'BTC',
        'binance': 'BTCUSDT',
        'kraken': 'XXBTZUSD'
    },
    'ETH': {
        'coinbase': 'ETH', 
        'binance': 'ETHUSDT',
        'kraken': 'XETHZUSD'
    },
    'LTC': {
        'coinbase': 'LTC',
        'binance': 'LTCUSDT', 
        'kraken': 'XLTCZUSD'
    },
    'USDT': {
        'coinbase': 'USDT',
        'binance': 'USDTUSD',
        'kraken': 'USDTZUSD'
    },
    'USD': {
        'coinbase': 'USD',
        'binance': 'USDT',  # Binance doesn't have direct USD pairs for some coins
        'kraken': 'ZUSD'
    }
}

router = Router()




# Cache implementation
conversion_cache = {}
CACHE_DURATION = 300  # 5 minutes cache

# Cache implementation
conversion_cache = {}
CACHE_DURATION = 300  # 5 minutes cache
# ========================
# CONFIGURATION
# ========================


conn = sqlite3.connect('escrow_bot.db')
cursor = conn.cursor()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# ========================
# DATABASE SETUP
# ========================
def init_db():
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        tx_id TEXT PRIMARY KEY,
        user_id INTEGER,
        buyer_id INTEGER,
        seller_id INTEGER,
        amount REAL,
        coin TEXT,
        amount_received REAL,
        wallet TEXT,
        fee REAL,
        status TEXT,
        tx_hash TEXT,
        description TEXT,
        created_at INTEGER,
        verified_at INTEGER,
        released_at INTEGER,
        dispute_opened BOOLEAN DEFAULT 0,
        dispute_resolved BOOLEAN DEFAULT 0
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stats (
        date TEXT PRIMARY KEY,
        total_transactions INTEGER,
        total_amount REAL,
        total_fees REAL
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY,
        language TEXT DEFAULT 'en',
        wallet_address TEXT,
        is_seller BOOLEAN DEFAULT 0,
        referral_code TEXT,
        referred_by TEXT,
        rating REAL DEFAULT 5.0,
        ratings_count INTEGER DEFAULT 0
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS referrals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        referral_code TEXT,
        referred_user_id INTEGER,
        reward_amount REAL DEFAULT 0,
        transaction_id TEXT,
        created_at INTEGER,
        paid_out BOOLEAN DEFAULT 0,
        paid_at INTEGER
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rater_id INTEGER,
        rated_id INTEGER,
        transaction_id TEXT,
        rating INTEGER,
        comment TEXT,
        created_at INTEGER
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS disputes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id TEXT,
        user_id INTEGER,
        admin_id INTEGER,
        reason TEXT,
        status TEXT DEFAULT 'open',
        created_at INTEGER,
        resolved_at INTEGER
    )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS escrow_groups (
            group_id TEXT PRIMARY KEY,
            chat_id INTEGER,
            creator_id INTEGER,
            invite_link TEXT,
            created_at INTEGER,
            buyer_id INTEGER,
            seller_id INTEGER,
            transaction_id TEXT,
            status TEXT DEFAULT 'active',
            with_admins INTEGER DEFAULT 0  -- Add this column
        )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS group_users (
        chat_id INTEGER,
        user_id INTEGER,
        role TEXT,
        crypto_address TEXT,
        PRIMARY KEY (chat_id, user_id)
    )
    ''')
    conn.commit()
    conn.close()

    # Add this after your init_db() function
    def migrate_db():
        conn = sqlite3.connect('escrow_bot.db')
        cursor = conn.cursor()

        # Check if with_admins column exists
        cursor.execute("PRAGMA table_info(escrow_groups)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'with_admins' not in columns:
            print("Adding with_admins column to escrow_groups table...")
            cursor.execute('ALTER TABLE escrow_groups ADD COLUMN with_admins INTEGER DEFAULT 0')
            conn.commit()
            print("Migration completed successfully!")

        conn.close()

    # Call this function after init_db()
    init_db()
    migrate_db()


# ========================
# DEPOSIT MONITORING SYSTEM
# ========================

class DepositMonitor:
    def __init__(self):
        self.is_monitoring = False
        self.monitoring_tasks = {}
        self.conn = sqlite3.connect('escrow_bot.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    async def start_monitoring(self):
        """Start the deposit monitoring system"""
        self.is_monitoring = True
        while self.is_monitoring:
            try:
                await self.check_all_pending_deposits()
                await asyncio.sleep(60)  # Check every 60 seconds
            except Exception as e:
                print(f"Error in deposit monitoring: {e}")
                await asyncio.sleep(30)

    async def check_all_pending_deposits(self):
        """Check all pending transactions for deposits"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM transactions 
            WHERE status = 'pending' AND escrow_address IS NOT NULL
        ''')
        transactions = cursor.fetchall()
        
        for tx in transactions:
            if tx['tx_id'] not in self.monitoring_tasks:
                self.monitoring_tasks[tx['tx_id']] = asyncio.create_task(
                    self.monitor_transaction_deposit(tx)
                )

    async def monitor_transaction_deposit(self, transaction):
        """Monitor a specific transaction for deposits"""
        tx_id = transaction['tx_id']
        escrow_address = transaction['escrow_address']
        coin_type = transaction['coin']
        chat_id = transaction.get('group_id')  # You'll need to store group_id in transactions
        
        print(f"Starting monitoring for transaction {tx_id}")
        
        # Check for deposits immediately
        deposit_info = await self.check_deposit(escrow_address, coin_type)
        
        if deposit_info and deposit_info['confirmed']:
            await self.handle_deposit_received(transaction, deposit_info)
        elif deposit_info and not deposit_info['confirmed']:
            await self.handle_pending_deposit(transaction, deposit_info)
        else:
            # No deposit found yet, check periodically
            max_checks = 1440  # Check for 24 hours (1440 minutes)
            for check_count in range(max_checks):
                if not self.is_monitoring:
                    break
                    
                await asyncio.sleep(60)  # Check every minute
                
                deposit_info = await self.check_deposit(escrow_address, coin_type)
                if deposit_info and deposit_info['confirmed']:
                    await self.handle_deposit_received(transaction, deposit_info)
                    break
                elif deposit_info and not deposit_info['confirmed']:
                    await self.handle_pending_deposit(transaction, deposit_info)
                
                # Send periodic status updates
                if check_count % 30 == 0:  # Every 30 minutes
                    await self.send_status_update(transaction, deposit_info)
        
        # Clean up monitoring task
        if tx_id in self.monitoring_tasks:
            del self.monitoring_tasks[tx_id]

    async def check_deposit(self, address, coin_type):
        """Check for deposits to an address using blockchain explorers"""
        try:
            if coin_type == 'BTC':
                return await self.check_btc_deposit(address)
            elif coin_type == 'ETH':
                return await self.check_eth_deposit(address)
            elif coin_type == 'USDT':
                return await self.check_usdt_deposit(address)
            elif coin_type == 'LTC':
                return await self.check_ltc_deposit(address)
        except Exception as e:
            print(f"Error checking {coin_type} deposit: {e}")
            return None

    async def check_btc_deposit(self, address):
        """Check BTC deposits using BlockCypher API"""
        try:
            url = f"https://api.blockcypher.com/v1/btc/main/addrs/{address}/balance"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'balance': data.get('balance', 0) / 10**8,  # Convert satoshis to BTC
                            'unconfirmed_balance': data.get('unconfirmed_balance', 0) / 10**8,
                            'confirmed': data.get('unconfirmed_balance', 0) == 0,
                            'total_received': data.get('total_received', 0) / 10**8
                        }
        except Exception as e:
            print(f"Error checking BTC deposit: {e}")
            return None

    async def check_eth_deposit(self, address):
        """Check ETH deposits using Etherscan API"""
        try:
            api_key = Config.API_KEYS['ETH']
            url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={api_key}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        balance = int(data.get('result', 0)) / 10**18  # Convert wei to ETH
                        return {
                            'balance': balance,
                            'confirmed': True,  # Etherscan returns confirmed balance only
                            'total_received': balance  # For ETH, we can't easily get total received
                        }
        except Exception as e:
            print(f"Error checking ETH deposit: {e}")
            return None

    async def check_usdt_deposit(self, address):
        """Check USDT (TRC-20) deposits using Tronscan API"""
        try:
            url = f"https://apilist.tronscan.org/api/account?address={address}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Find USDT balance in tokens
                        usdt_balance = 0
                        for token in data.get('tokens', []):
                            if token.get('tokenId') == 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t':  # USDT token ID
                                usdt_balance = float(token.get('balance', 0)) / 10**6  # Convert to USDT
                                break
                        
                        return {
                            'balance': usdt_balance,
                            'confirmed': True,  # Tronscan returns confirmed balances
                            'total_received': usdt_balance  # Simplified for this example
                        }
        except Exception as e:
            print(f"Error checking USDT deposit: {e}")
            return None

    async def check_ltc_deposit(self, address):
        """Check LTC deposits using BlockCypher API"""
        try:
            url = f"https://api.blockcypher.com/v1/ltc/main/addrs/{address}/balance"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'balance': data.get('balance', 0) / 10**8,  # Convert litoshis to LTC
                            'unconfirmed_balance': data.get('unconfirmed_balance', 0) / 10**8,
                            'confirmed': data.get('unconfirmed_balance', 0) == 0,
                            'total_received': data.get('total_received', 0) / 10**8
                        }
        except Exception as e:
            print(f"Error checking LTC deposit: {e}")
            return None

    async def handle_deposit_received(self, transaction, deposit_info):
        """Handle a confirmed deposit"""
        tx_id = transaction['tx_id']
        amount = deposit_info['balance']
        coin_type = transaction['coin']
        
        # Update transaction in database
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE transactions 
            SET amount_received = ?, status = 'paid', verified_at = ?
            WHERE tx_id = ?
        ''', (amount, int(time.time()), tx_id))
        self.conn.commit()
        
        # Get chat ID from transaction (you'll need to store this)
        chat_id = transaction.get('group_id')
        if not chat_id:
            return
            
        # Format amount based on coin type
        if coin_type in ['BTC', 'LTC']:
            amount_str = f"{amount:.8f}"
        elif coin_type == 'ETH':
            amount_str = f"{amount:.6f}"
        else:
            amount_str = f"{amount:.2f}"
        
        # Create notification message
        notification = (
            "🎉 <b>DEPOSIT CONFIRMED!</b>\n\n"
            f"<b>Transaction ID:</b> <code>{tx_id}</code>\n"
            f"<b>Amount Received:</b> {amount_str} {coin_type}\n"
            f"<b>Status:</b> ✅ Confirmed on blockchain\n\n"
            "The funds have been securely deposited to the escrow address.\n"
            "The seller can now proceed with fulfilling their obligations.\n\n"
            "<i>Use /release to complete the transaction once the terms are met.</i>"
        )
        
        # Send notification to group
        try:
            await bot.send_message(chat_id, notification, parse_mode="HTML")
        except Exception as e:
            print(f"Error sending deposit notification: {e}")

    async def handle_pending_deposit(self, transaction, deposit_info):
        """Handle a pending deposit (unconfirmed)"""
        tx_id = transaction['tx_id']
        amount = deposit_info['unconfirmed_balance'] or deposit_info['balance']
        coin_type = transaction['coin']
        
        # Get chat ID from transaction
        chat_id = transaction.get('group_id')
        if not chat_id:
            return
            
        # Format amount based on coin type
        if coin_type in ['BTC', 'LTC']:
            amount_str = f"{amount:.8f}"
        elif coin_type == 'ETH':
            amount_str = f"{amount:.6f}"
        else:
            amount_str = f"{amount:.2f}"
        
        # Create notification message
        notification = (
            "⏳ <b>PENDING DEPOSIT DETECTED</b>\n\n"
            f"<b>Transaction ID:</b> <code>{tx_id}</code>\n"
            f"<b>Amount:</b> {amount_str} {coin_type}\n"
            f"<b>Status:</b> ⚠️ Waiting for blockchain confirmations\n\n"
            "A transaction has been broadcast to the network but is not yet confirmed.\n"
            "This usually takes 10-30 minutes depending on network congestion.\n\n"
            "<i>I'll notify you when the deposit is confirmed.</i>"
        )
        
        # Send notification to group
        try:
            await bot.send_message(chat_id, notification, parse_mode="HTML")
        except Exception as e:
            print(f"Error sending pending deposit notification: {e}")

    async def send_status_update(self, transaction, deposit_info):
        """Send periodic status updates"""
        tx_id = transaction['tx_id']
        coin_type = transaction['coin']
        escrow_address = transaction['escrow_address']
        chat_id = transaction.get('group_id')
        
        if not chat_id:
            return
            
        if deposit_info:
            status_msg = (
                "🔍 <b>DEPOSIT STATUS UPDATE</b>\n\n"
                f"<b>Transaction ID:</b> <code>{tx_id}</code>\n"
                f"<b>Escrow Address:</b> <code>{escrow_address}</code>\n"
                f"<b>Coin Type:</b> {coin_type}\n\n"
                "<b>Current Status:</b> ⚠️ Still waiting for deposit\n\n"
                "<i>Please send the agreed amount to the escrow address shown above.</i>"
            )
        else:
            status_msg = (
                "🔍 <b>DEPOSIT STATUS UPDATE</b>\n\n"
                f"<b>Transaction ID:</b> <code>{tx_id}</code>\n"
                f"<b>Escrow Address:</b> <code>{escrow_address}</code>\n"
                f"<b>Coin Type:</b> {coin_type}\n\n"
                "<b>Current Status:</b> ❌ No deposit detected yet\n\n"
                "<i>Please send the agreed amount to the escrow address shown above.</i>"
            )
        
        try:
            await bot.send_message(chat_id, status_msg, parse_mode="HTML")
        except Exception as e:
            print(f"Error sending status update: {e}")

# Initialize the deposit monitor
deposit_monitor = DepositMonitor()


class Config:
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]
    VERIFICATION_GROUP_PREFIX = "HoldEscrowBot Verification"
    MAX_VERIFICATION_GROUPS = 5  # Maximum verification groups per user
    # Load wallet addresses from environment variables
    # Telegram Bot
    BOT_TOKEN = os.getenv("BOT_TOKEN")
     
    BOT_USERNAME = os.getenv("BOT_USERNAME", "HoldEscrowBot")
    
    # Telethon (for group creation)
    TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
    TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
    TELETHON_SESSION_STRING = os.getenv("TELETHON_SESSION_STRING")
    WALLETS = {
        "USDT": [x.strip() for x in os.getenv("USDT_WALLETS", "").split(",") if x.strip()],
        "BTC": [x.strip() for x in os.getenv("BTC_WALLETS", "").split(",") if x.strip()],
        "LTC": [x.strip() for x in os.getenv("LTC_WALLETS", "").split(",") if x.strip()],
        "ETH": [x.strip() for x in os.getenv("ETH_WALLETS", "").split(",") if x.strip()],
    }
    # Add this to your Config class
    VERIFICATION_GROUP = os.getenv("VERIFICATION_GROUP", "@CoinHoldVerify")
    VERIFICATION_GROUP_ID = int(os.getenv("VERIFICATION_GROUP_ID", "0"))
    VOUCH_CHANNEL = os.getenv("VOUCH_CHANNEL", "@CoinHoldVouches")
    VOUCH_CHANNEL_ID = int(os.getenv("VOUCH_CHANNEL_ID", "0"))

    FEE_PERCENTAGE = float(os.getenv("FEE_PERCENTAGE", "1.5"))
    MIN_FEE = float(os.getenv("MIN_FEE", "0.0001"))
    MAX_FEE = float(os.getenv("MAX_FEE", "0.01"))
    ESCROW_TIMEOUT = int(os.getenv("ESCROW_TIMEOUT", "86400"))
    MIN_AMOUNTS = {
        "BTC": float(os.getenv("MIN_BTC", "0.0001")),
        "ETH": float(os.getenv("MIN_ETH", "0.01")),
        "USDT": float(os.getenv("MIN_USDT", "10")),
        "LTC": float(os.getenv("MIN_LTC", "0.1")),
    }
    SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "@YourSupportChat")
    VOUCH_CHANNEL = os.getenv("VOUCH_CHANNEL", "@CoinHoldVouches")
    BLOCKCHAIN_API = {
        "BTC": "https://blockchain.info/rawtx/{tx_hash}",
        "ETH": "https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={api_key}",
        "USDT": "https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={api_key}",
        "LTC": "https://api.blockcypher.com/v1/ltc/main/txs/{tx_hash}"
    }
    API_KEYS = {
    "ETH": os.getenv("ETHERSCAN_API_KEY", ""),
    "BLOCKCYPHER": "fdc4655d1dea4a7e953e53f64547a8dd",  # Your BlockCypher token
    }

    BLOCKCHAIN_API = {
    "BTC": "https://api.blockcypher.com/v1/btc/main/txs/{tx_hash}?token={api_key}",
    "ETH": "https://api.etherscan.io/api?module=proxy&action=eth_getTransactionByHash&txhash={tx_hash}&apikey={api_key}",
    "USDT": "https://api.etherscan.io/api?module=proxy&action=eth_getTransactionReceipt&txhash={tx_hash}&apikey={api_key}",
    "LTC": "https://api.blockcypher.com/v1/ltc/main/txs/{tx_hash}?token={api_key}"
}
    REFERRAL_REWARD = float(os.getenv("REFERRAL_REWARD", "0.00005"))
    REFERRAL_CODE_LENGTH = int(os.getenv("REFERRAL_CODE_LENGTH", "8"))
# ========================
# UTILITY FUNCTIONS
# ========================
def get_user_language(user_id: int) -> str:
    conn = sqlite3.connect('escrow_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT language FROM user_settings WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else DEFAULT_LANGUAGE

async def translate(text: str, target_lang: str, source_lang: str = 'en') -> str:
    if target_lang == source_lang:
        return text
    try:
        return GoogleTranslator(source=source_lang, target=target_lang).translate(text)
    except:
        return text

async def send_banner(chat_id: int, banner_type: str, caption: str = "", **kwargs):
    try:
        if banner_type in BANNERS:
            await bot.send_photo(
                chat_id=chat_id,
                photo=BANNERS[banner_type],
                caption=caption,
                parse_mode="HTML",
                **kwargs
            )
        else:
            await bot.send_message(chat_id, caption, parse_mode="HTML", **kwargs)
    except Exception as e:
        print(f"Error sending banner to {chat_id}: {e}")
        # Don't try to send again to avoid infinite loop

def generate_referral_code() -> str:
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(random.choice(chars) for _ in range(Config.REFERRAL_CODE_LENGTH))

def decode_render_session_string(encoded_string):
    """
    Decode a Render-safe encoded session string back to original format.
    
    Args:
        encoded_string (str): Hex-encoded session string from Render environment
        
    Returns:
        str: Original session string or None if decoding fails
    """
    try:
        # Check if it's already a regular session string (contains special chars)
        if any(char in encoded_string for char in ['-', '_', '+', '/', '=']):
            logger.info("Session string appears to be in regular format, using as-is")
            return encoded_string
            
        # Try to decode from hex format
        logger.info("Attempting to decode hex-encoded session string")
        hex_bytes = binascii.unhexlify(encoded_string)
        b64_decoded = base64.b64decode(hex_bytes)
        original_string = b64_decoded.decode('utf-8')
        logger.info("Successfully decoded session string from Render format")
        return original_string
        
    except (binascii.Error, base64.binascii.Error, UnicodeDecodeError) as e:
        logger.warning(f"Failed to decode session string: {e}")
        logger.info("Treating as regular session string")
        return encoded_string
    except Exception as e:
        logger.error(f"Unexpected error decoding session string: {e}")
        return None

# ========================
# DATABASE CLASSES
# ========================


class TelegramGroupManager:
    def __init__(self):
        self.client = None
        self.initialized = False
        self.session_string = None
        self.last_error = None
        
    async def initialize(self):
        """Initialize Telethon client with robust error handling"""
        try:
            # Get credentials from environment
            api_id = os.getenv("TELEGRAM_API_ID")
            api_hash = os.getenv("TELEGRAM_API_HASH")
            session_string = os.getenv("TELETHON_SESSION_STRING")
            
            if not all([api_id, api_hash, session_string]):
                self.last_error = "Missing Telethon credentials in environment variables"
                logger.error(self.last_error)
                return False
            
            # Clean and validate session string
            session_string = session_string.strip()
            if len(session_string) < 200:
                self.last_error = f"Session string too short ({len(session_string)} chars), expected 200+"
                logger.error(self.last_error)
                return False
            
            logger.info(f"Attempting to initialize Telethon with session string ({len(session_string)} chars)")
            
            # Create StringSession
            try:
                session = StringSession(session_string)
            except Exception as e:
                self.last_error = f"Invalid session string format: {e}"
                logger.error(self.last_error)
                return False
            
            # Create client
            self.client = TelegramClient(
                session=session,
                api_id=int(api_id),
                api_hash=api_hash
            )
            
            # Set longer timeouts for cloud environments
            self.client.session.set_dc(2, '149.154.167.40', 443)
            
            # Connect with timeout
            await asyncio.wait_for(self.client.connect(), timeout=10)
            
            if not await self.client.is_user_authorized():
                self.last_error = "Session not authorized. Please generate a new session string."
                logger.error(self.last_error)
                await self.client.disconnect()
                return False
            
            # Test connection
            me = await self.client.get_me()
            logger.info(f"✅ Telethon initialized successfully for user: {me.first_name} (@{me.username})")
            
            self.initialized = True
            self.last_error = None
            return True
            
        except ApiIdInvalidError as e:
            self.last_error = f"Invalid API ID/Hash: {e}"
            logger.error(self.last_error)
            return False
        except AuthKeyError as e:
            self.last_error = f"Auth key error: {e}. Generate new session string."
            logger.error(self.last_error)
            return False
        except SessionPasswordNeededError:
            self.last_error = "2FA password required. Use interactive session generation."
            logger.error(self.last_error)
            return False
        except asyncio.TimeoutError:
            self.last_error = "Connection timeout. Check network connectivity."
            logger.error(self.last_error)
            return False
        except Exception as e:
            self.last_error = f"Unexpected error during initialization: {e}"
            logger.error(self.last_error)
            return False
    
    async def create_escrow_group(self, creator_id, creator_name, with_admins=True):
        """Create escrow group with comprehensive error handling"""
        if not self.initialized:
            init_result = await self.initialize()
            if not init_result:
                return {
                    "success": False, 
                    "error": f"Telethon not initialized: {self.last_error}",
                    "fallback_instructions": self._get_fallback_instructions()
                }
        
        try:
            logger.info(f"Creating escrow group for user {creator_id} ({creator_name})")
            
            # Generate unique group name
            timestamp = int(time.time())
            group_id = f"escrow_{creator_id}_{timestamp}"
            group_name = f"HoldEscrow Escrow #{str(timestamp)[-6:]}"
            
            # Create supergroup
            result = await self.client(CreateChannelRequest(
                title=group_name,
                about=f"Secure escrow transaction • Created by {creator_name} • @HoldEscrowBot",
                megagroup=True
            ))
            
            chat = result.chats[0]
            chat_id = chat.id
            
            # Get invite link
            invite = await self.client(ExportChatInviteRequest(chat_id))
            invite_link = invite.link
            
            # Add bot to group
            bot_username = os.getenv("BOT_USERNAME", "HoldEscrowBot")
            try:
                bot_entity = await self.client.get_entity(bot_username)
                await self.client(telethon.tl.functions.channels.InviteToChannelRequest(
                    channel=chat,
                    users=[bot_entity]
                ))
                
                # Make bot admin
                rights = ChatAdminRights(
                    change_info=True,
                    post_messages=True,
                    edit_messages=True,
                    delete_messages=True,
                    ban_users=True,
                    invite_users=True,
                    pin_messages=True,
                    add_admins=False,
                    manage_call=True,
                    other=True
                )
                await self.client(telethon.tl.functions.channels.EditAdminRequest(
                    channel=chat,
                    user_id=bot_entity,
                    admin_rights=rights,
                    rank="Escrow Bot"
                ))
                logger.info("✅ Bot added and promoted successfully")
                
            except Exception as e:
                logger.warning(f"⚠️ Could not add bot as admin: {e}")
                # Continue anyway - user can add bot manually
            
            # Add creator to group
            try:
                creator_entity = await self.client.get_entity(creator_id)
                await self.client(telethon.tl.functions.channels.InviteToChannelRequest(
                    channel=chat,
                    users=[creator_entity]
                ))
            except Exception as e:
                logger.warning(f"⚠️ Could not add creator to group: {e}")
            
            # Send welcome message
            welcome_msg = f"""
🏢 **Welcome to {group_name}**

This is a secure escrow group created by @{creator_name}.

**Group Rules:**
• Only discuss the specific transaction
• Be respectful to all parties
• The escrow bot will monitor this conversation
• Do not share sensitive personal information

**To start:** Use /buyer or /seller commands to register.

🔒 Secured by @HoldEscrowBot
            """
            
            await self.client.send_message(chat_id, welcome_msg)
            
            return {
                "success": True,
                "group_name": group_name,
                "invite_link": invite_link,
                "chat_id": chat_id,
                "message": "Group created successfully! Share the invite link with the other party."
            }
            
        except Exception as e:
            error_msg = f"Error creating group: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "fallback_instructions": self._get_fallback_instructions()
            }
    
    def _get_fallback_instructions(self):
        """Get instructions for manual group creation"""
        return """
📋 **Manual Group Creation Instructions**

Since automated group creation is unavailable, please:

1. **Create a new group** in Telegram
2. **Add @HoldEscrowBot** to the group
3. **Make the bot an administrator** with these permissions:
   • Delete messages
   • Ban users  
   • Pin messages
   • Invite users

4. **Set group permissions** to restrict member adding
5. **Use these commands** in the group:
   • `/buyer [your_wallet_address]`
   • `/seller [your_wallet_address]`

Need help? Contact @HoldEscrowSupport
        """
    
    async def safe_shutdown(self):
        """Safely shutdown the Telethon client"""
        if self.client and self.client.is_connected():
            try:
                await self.client.disconnect()
                logger.info("✅ Telethon client disconnected safely")
            except Exception as e:
                logger.error(f"Error disconnecting Telethon client: {e}")
        self.initialized = False

# Global instance
group_manager = TelegramGroupManager()

# Simple rate limiting
class RateLimiter:
    def __init__(self, calls_per_second: float = 0.2):
        self.calls_per_second = calls_per_second
        self.last_call = datetime.min
        self.lock = asyncio.Lock()
    
    async def wait(self):
        async with self.lock:
            now = datetime.now()
            elapsed = (now - self.last_call).total_seconds()
            wait_time = max(0, (1 / self.calls_per_second) - elapsed)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_call = datetime.now()

# Create rate limiters for each API
rate_limiters = {
    'BLOCKCYPHER': RateLimiter(0.2),  # 5 calls per second max for free tier
    'ETHERSCAN': RateLimiter(0.2)     # 5 calls per second max for free tier
}

class EscrowTransaction:
    def __init__(self):
        self.conn = sqlite3.connect('escrow_bot.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    # Adding a function to create a group

escrow_db = EscrowTransaction()

# USER MANAGEMENT
# ========================
class UserManager:
    def __init__(self):
        self.conn = sqlite3.connect('escrow_bot.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        return dict(user) if user else None

    def create_user(self, user_id: int, language: str = DEFAULT_LANGUAGE) -> Dict[str, Any]:
        cursor = self.conn.cursor()
        referral_code = generate_referral_code()

        cursor.execute('''
            INSERT OR IGNORE INTO user_settings (user_id, language, referral_code)
            VALUES (?, ?, ?)
        ''', (user_id, language, referral_code))

        self.conn.commit()
        return self.get_user(user_id)

    def set_language(self, user_id: int, language: str) -> bool:
        if language not in SUPPORTED_LANGUAGES:
            return False

        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE user_settings 
            SET language = ?
            WHERE user_id = ?
        ''', (language, user_id))

        self.conn.commit()
        return cursor.rowcount > 0
user_manager = UserManager()


# ========================
# START COMMAND HANDLER
# ========================
# Update the start command to handle referrals
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    # Check if user exists, else create
    user = user_manager.get_user(message.from_user.id)
    if not user:
        user = user_manager.create_user(message.from_user.id)

    # Get command arguments
    args = message.text.split(maxsplit=1)
    referral_code = None
    if len(args) > 1:
        referral_code = args[1].strip()

    # Process referral code if provided
    if referral_code and len(referral_code) == Config.REFERRAL_CODE_LENGTH:
        # Check if user is trying to use their own code
        if user.get('referral_code') == referral_code:
            pass  # Don't allow self-referral
        else:
            # Check if referral code exists
            conn = sqlite3.connect('escrow_bot.db')
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM user_settings WHERE referral_code = ?', (referral_code,))
            referrer = cursor.fetchone()
            
            if referrer:
                referrer_id = referrer[0]
                # Update user's referred_by field
                cursor.execute('UPDATE user_settings SET referred_by = ? WHERE user_id = ?', 
                              (referral_code, message.from_user.id))
                conn.commit()
                
                # Notify referrer
                try:
                    referrer_msg = await translate(
                        "🎉 You've got a new referral!\n\n"
                        f"@{message.from_user.username or message.from_user.first_name} "
                        f"has joined using your referral code.\n\n"
                        "You'll earn rewards when they complete their first transaction.",
                        get_user_language(referrer_id)
                    )
                    await bot.send_message(referrer_id, referrer_msg)
                except:
                    pass  # Could not notify referrer
            
            conn.close()

    lang = user.get("language", DEFAULT_LANGUAGE)

    # Welcome message with clickable links
    welcome_msg = await translate(
        "🏆 Welcome @{username}! 🏆\n\n"
        "💠 <b>@HoldEscrow</b> – Your trusted escrow service for secure and hassle-free Telegram transactions.\n"
        "Keep your funds safe and trade with confidence!\n\n"
        "💵 <b>ESCROW FEE</b>\n"
        "• $5.0 if under $100\n"
        "• 5.0% if over $100\n\n"
        "✨ <b><a href='https://t.me/CoinHoldEscrow'>UPDATES</a> - <a href='https://t.me/CoinHoldVouches'>VOUCHES</a></b>\n"
        "• DEALS COMPLETED: <b>3660</b>\n"
        "• DISPUTES RESOLVED: <b>164</b>\n\n"
        "💡 Declare yourself as buyer or seller by dropping your crypto address (BTC, LTC, XMR, or USDT-TRC20) in the escrow group.\n\n"
        "<i>Use the buttons below to explore features and safety.</i>".format(
            username=message.from_user.username or "User"
        ),
        lang
    )

    # Create keyboard with group creation options
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛡️ CREATE ESCROW GROUP", callback_data="create_escrow_group")],
        [
            InlineKeyboardButton(text="📜 TERMS", callback_data="terms"),
            InlineKeyboardButton(text="📘 INSTRUCTIONS", callback_data="instructions")
        ],
        [InlineKeyboardButton(text="❓ WHAT IS ESCROW?", callback_data="what_is_escrow")],
        [InlineKeyboardButton(text="🎯 REFERRAL PROGRAM", callback_data="referral_program")]
    ])

    # Try to send image instead of video
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(BASE_DIR, "assets", "welcome.jpg")
        if os.path.exists(image_path):
            photo = FSInputFile(image_path)
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=photo,
                caption=welcome_msg,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Send follow-up message guiding users to create escrow group
            followup_msg = await translate(
                "🚀 <b>Ready to start your secure transaction?</b>\n\n"
                "👆 Click the <b>🛡️ CREATE ESCROW GROUP</b> button above\n"
                "OR\n"
                "💬 Type <b>/create</b> to get started!\n\n"
                "Both options will help you create a secure escrow group for your transaction. 🔒",
                lang
            )
            
            await bot.send_message(
                message.chat.id,
                followup_msg,
                parse_mode="HTML"
            )
            return
    except Exception as e:
        print(f"Could not send image: {e}")

    # Fallback to text message if image is not available
    await bot.send_message(
        message.chat.id,
        welcome_msg,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    # Send follow-up message guiding users to create escrow group
    followup_msg = await translate(
        "🚀 <b>Ready to start your secure transaction?</b>\n\n"
        "👆 Click the <b>🛡️ CREATE ESCROW GROUP</b> button above\n"
        "OR\n"
        "💬 Type <b>/create</b> to get started!\n\n"
        "Both options will help you create a secure escrow group for your transaction. 🔒",
        lang
    )
    
    await bot.send_message(
        message.chat.id,
        followup_msg,
        parse_mode="HTML"
    )

# New /create command - only works in private chats (not groups)
@dp.message(Command("create"))
async def cmd_create(message: types.Message, state: FSMContext):
    """
    Handle /create command - creates escrow group (private chats only)
    This command does the same as the "CREATE ESCROW GROUP" button
    """
    lang = get_user_language(message.from_user.id)
    
    # Check if command is used in a group
    if message.chat.type != "private":
        error_msg = await translate(
            "❌ <b>The /create command can only be used in private chat with the bot.</b>\n\n"
            "Please start a private conversation with me and use /create there, "
            "or use the 🛡️ CREATE ESCROW GROUP button in the group.",
            lang
        )
        await bot.send_message(
            message.chat.id,
            error_msg,
            parse_mode="HTML"
        )
        return
    
    # Check if user has reached group limit
    cursor = escrow_db.conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM escrow_groups WHERE creator_id = ?', (message.from_user.id,))
    group_count = cursor.fetchone()[0]

    if group_count >= 15:  # Limit to 10 groups per user
        # Get user's active groups
        cursor.execute('SELECT chat_id, invite_link FROM escrow_groups WHERE creator_id = ?',
                       (message.from_user.id,))
        groups = cursor.fetchall()

        groups_msg = await translate(
            "❌ <b>You have reached the maximum number of groups you can create!</b>\n\n"
            "Use one of your existing groups or contact an admin for assistance.\n\n"
            "<b>Active Groups Created by you:</b>\n",
            lang
        )

        for group in groups:
            groups_msg += f"\n• {group['chat_id']}: {group['invite_link']}"

        await bot.send_message(
            message.from_user.id,
            groups_msg,
            parse_mode="HTML"
        )
        return

    # Show group creation options (same as the button)
    options_msg = await translate(
        "🛡️ <b>Create Your Escrow Group</b>\n\n"
        "Choose one of these options:\n\n"
        "🔹 <b>With Admin</b> - Creates a group with admins for a secure escrow\n"
        "🔹 <b>Bot Only</b> - Creates a group with only the bot, ideal for privacy-focused users",
        lang
    )

    options_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 WITH ADMINS", callback_data="create_with_admins")],
        [InlineKeyboardButton(text="🤖 ONLY BOT", callback_data="create_bot_only")],
        [InlineKeyboardButton(text="🔙 Back to Main", callback_data="back:main_menu")]
    ])

    await bot.send_message(
        message.from_user.id,
        options_msg,
        reply_markup=options_keyboard,
        parse_mode="HTML"
    )

@dp.callback_query(lambda c: c.data == "referral_program")
async def callback_referral_program(callback_query: types.CallbackQuery):
    """Handle referral program button click"""
    await cmd_referral(callback_query.message)
    await callback_query.answer()

# Add function to reward referrals when transactions are completed
async def reward_referral(transaction_id: str):
    """Reward referrer when a transaction is completed"""
    conn = sqlite3.connect('escrow_bot.db')
    cursor = conn.cursor()
    
    # Get transaction details
    cursor.execute('SELECT buyer_id, seller_id, amount FROM transactions WHERE tx_id = ?', (transaction_id,))
    transaction = cursor.fetchone()
    
    if not transaction:
        return
    
    buyer_id, seller_id, amount = transaction
    
    # Check if buyer was referred
    cursor.execute('SELECT referred_by FROM user_settings WHERE user_id = ?', (buyer_id,))
    buyer_referral = cursor.fetchone()
    
    if buyer_referral and buyer_referral[0]:
        referrer_code = buyer_referral[0]
        
        # Calculate reward (0.5% of transaction amount or fixed amount)
        reward_amount = max(amount * 0.005, Config.REFERRAL_REWARD)
        
        # Add to referrals table
        cursor.execute('''
            INSERT INTO referrals (referral_code, referred_user_id, reward_amount, transaction_id, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (referrer_code, buyer_id, reward_amount, transaction_id, int(time.time())))
        
        # Notify referrer
        try:
            cursor.execute('SELECT user_id FROM user_settings WHERE referral_code = ?', (referrer_code,))
            referrer_id = cursor.fetchone()[0]
            
            referrer_msg = await translate(
                "🎉 You've earned referral rewards!\n\n"
                f"Your referral has completed a transaction of {amount:.8f} BTC.\n"
                f"You've earned {reward_amount:.8f} BTC in rewards!\n\n"
                "Use /referral to see your total earnings.",
                get_user_language(referrer_id)
            )
            
            await bot.send_message(referrer_id, referrer_msg)
        except:
            pass  # Could not notify referrer
    
    # Also check if seller was referred
    cursor.execute('SELECT referred_by FROM user_settings WHERE user_id = ?', (seller_id,))
    seller_referral = cursor.fetchone()
    
    if seller_referral and seller_referral[0]:
        referrer_code = seller_referral[0]
        
        # Calculate reward (0.5% of transaction amount or fixed amount)
        reward_amount = max(amount * 0.005, Config.REFERRAL_REWARD)
        
        # Add to referrals table
        cursor.execute('''
            INSERT INTO referrals (referral_code, referred_user_id, reward_amount, transaction_id, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (referrer_code, seller_id, reward_amount, transaction_id, int(time.time())))
        
        # Notify referrer
        try:
            cursor.execute('SELECT user_id FROM user_settings WHERE referral_code = ?', (referrer_code,))
            referrer_id = cursor.fetchone()[0]
            
            referrer_msg = await translate(
                "🎉 You've earned referral rewards!\n\n"
                f"Your referral has completed a transaction of {amount:.8f} BTC.\n"
                f"You've earned {reward_amount:.8f} BTC in rewards!\n\n"
                "Use /referral to see your total earnings.",
                get_user_language(referrer_id)
            )
            
            await bot.send_message(referrer_id, referrer_msg)
        except:
            pass  # Could not notify referrer
    
    conn.commit()
    conn.close()


# ========================
# GROUP CREATION HANDLERS
# ========================
@dp.callback_query(lambda c: c.data == "create_escrow_group")
async def create_escrow_group_callback(callback_query: types.CallbackQuery):
    lang = get_user_language(callback_query.from_user.id)

    # Show loading message
    await bot.answer_callback_query(
        callback_query.id,
        text=await translate("Creating your escrow group...", lang)
    )

    # Check if user has reached group limit
    cursor = escrow_db.conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM escrow_groups WHERE creator_id = ?', (callback_query.from_user.id,))
    group_count = cursor.fetchone()[0]

    if group_count >= 10:  # Limit to 10 groups per user
        # Get user's active groups
        cursor.execute('SELECT chat_id, invite_link FROM escrow_groups WHERE creator_id = ?',
                       (callback_query.from_user.id,))
        groups = cursor.fetchall()

        groups_msg = await translate(
            "You have reached the maximum number of groups you can create!\n"
            "Use one of your existing groups or contact an admin for assistance.\n\n"
            "Active Groups Created by you:\n",
            lang
        )

        for group in groups:
            groups_msg += f"\n{group['chat_id']}: {group['invite_link']}"

        await bot.send_message(
            callback_query.from_user.id,
            groups_msg
        )
        return

    # Show group creation options
    options_msg = await translate(
        "Choose one of those options:\n\n"
        "• With Admins :- Creates a group with admins for a secure escrow.\n"
        "• Bot Only :- Creates a group with only the bot, ideal for privacy-focused users.",
        lang
    )

    options_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="WITH ADMINS", callback_data="create_with_admins")],
        [InlineKeyboardButton(text="ONLY BOT", callback_data="create_bot_only")],
        [InlineKeyboardButton(text="🔙 Back to Main", callback_data="back:main_menu")]
    ])

    await bot.send_message(
        callback_query.from_user.id,
        options_msg,
        reply_markup=options_keyboard
    )


@dp.callback_query(lambda c: c.data in ["create_with_admins", "create_bot_only"])
async def handle_group_creation_option(callback_query: types.CallbackQuery):
    lang = get_user_language(callback_query.from_user.id)
    with_admins = callback_query.data == "create_with_admins"

    # Show loading message
    await bot.answer_callback_query(
        callback_query.id,
        text=await translate("Creating your escrow group...", lang)
    )

    # Create the group
    result = await group_manager.create_escrow_group(
        callback_query.from_user.id,
        callback_query.from_user.username or callback_query.from_user.first_name,
        with_admins
    )

    if result['success']:
        # Format the message with proper styling
        success_msg = (
            f"🏢 <b>Escrow Group Created Successfully!</b>\n\n"
            f"<b>Group Name:</b> {result['group_name']}\n"
            f"<b>Created By:</b> @{callback_query.from_user.username or callback_query.from_user.first_name}\n\n"
            f"<b>Invite Link:</b>\n<code>{result['invite_link']}</code>\n\n"
            f"<i>Share this link with the other party to begin your secure transaction.</i>\n\n"
            f"🔒 <b>Security Note:</b> This group is limited to 2 members only for maximum security."
        )

        # Create keyboard with group link
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔷 Join Escrow Group Now",
                url=result['invite_link']
            )],
            [InlineKeyboardButton(
                text="🔄 Create New Transaction",
                callback_data="create_escrow_start"
            )]
        ])

        await bot.send_message(
            callback_query.from_user.id,
            success_msg,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        # Add admin users if required
        if with_admins:
            for admin_id in Config.ADMIN_IDS:
                success = await group_manager.add_user_to_group(result['chat_id'], admin_id)
                if success:
                    try:
                        await send_banner(
                            admin_id,
                            "admin",
                            f"👥 <b>Added to Escrow Group</b>\n\n"
                            f"You've been added as an admin to:\n"
                            f"<b>Group:</b> {result['group_name']}\n"
                            f"<b>Group ID:</b> {result['chat_id']}\n"
                            f"<b>Created by:</b> @{callback_query.from_user.username or callback_query.from_user.first_name}\n\n"
                            f"Please monitor this group for any disputes or issues."
                        )
                    except:
                        pass  # Skip if we can't message the admin

        # Send welcome message to the group with video and inline buttons
        group_welcome = (
            f"🛡️ <b>Welcome to {result['group_name']}</b>\n\n"
            f"This is a secure escrow group created by @{callback_query.from_user.username or callback_query.from_user.first_name}.\n\n"
            f"<b>Group Rules:</b>\n"
            f"• Only discuss the specific transaction\n"
            f"• Be respectful to all parties\n"
            f"• The escrow bot will monitor this conversation\n"
            f"• Do not share sensitive personal information\n\n"
            f"<b>Service Overview:</b>\n"
            f"Your trusted escrow service for secure Telegram transactions. Keep your funds safe and trade with confidence!\n\n"
            f"<b>Escrow Fee:</b>\n"
            f"• $5.0 if under $100\n"
            f"• 5.0% if over $100\n\n"
            f"<b>Statistics:</b>\n"
            f"• Deals Completed: 4097\n"
            f"• Disputes Resolved: 184\n\n"
            f"<b>To start:</b> Declare yourself as buyer/seller by dropping your crypto address (BTC, LTC, XMR, or USDT-TRC20)\n\n"
            f"📹 <i>Watch our welcome video for a complete guide</i>"
        )

        # Create inline keyboard for the group
        group_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📜 TERMS", callback_data="terms"),
                InlineKeyboardButton(text="📘 INSTRUCTIONS", callback_data="instructions")
            ],
            [InlineKeyboardButton(text="❓ WHAT IS ESCROW?", callback_data="what_is_escrow")]
        ])

        try:
            # Try to send video to the group
            BASE_DIR = os.path.dirname(os.path.abspath(__file__))
            video_path = os.path.join(BASE_DIR, "assets", "group_welcome_video.mp4")
            if os.path.exists(video_path):
                video = FSInputFile(video_path)
                await bot.send_video(
                    chat_id=result['chat_id'],
                    video=video,
                    caption=group_welcome,
                    reply_markup=group_keyboard,
                    parse_mode="HTML"
                )
            else:
                # Fallback to text message if video is not available
                await bot.send_message(
                    result['chat_id'],
                    group_welcome,
                    parse_mode="HTML",
                    reply_markup=group_keyboard
                )
        except Exception as e:
            print(f"Could not send message to group: {e}")

    else:
        error_msg = await translate(
            f"❌ <b>Error Creating Group</b>\n\n"
            f"Could not create escrow group. Please try again later.\n\n"
            f"<b>Error Details:</b> {result['error']}\n\n"
            f"If this problem persists, please contact {Config.SUPPORT_CHAT} for assistance.",
            lang
        )

        await bot.send_message(
            callback_query.from_user.id,
            error_msg,
            parse_mode="HTML"
        )

# Add a handler for when the bot is added to a group
@dp.message(Command("init_escrow"))
async def init_escrow_group(message: types.Message):
    # This command should be used in the group after the bot is added
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("This command can only be used in a group.")
        return

    lang = get_user_language(message.from_user.id)

    try:
        # Check if this user has a pending group
        cursor = escrow_db.conn.cursor()
        cursor.execute('SELECT * FROM escrow_groups WHERE creator_id = ? AND status = ?',
                       (message.from_user.id, 'pending'))
        group_data = cursor.fetchone()

        if not group_data:
            await message.reply(await translate(
                "No pending escrow group found for you. Please use the 'CREATE ESCROW GROUP' button first.",
                lang
            ))
            return

        # Generate an invite link for the group
        invite_link = await bot.create_chat_invite_link(
            chat_id=message.chat.id,
            member_limit=MAX_GROUP_MEMBERS,
            creates_join_request=False
        )

        # Update the group in database
        cursor.execute('''
            UPDATE escrow_groups 
            SET chat_id = ?, invite_link = ?, status = ?
            WHERE group_id = ?
        ''', (message.chat.id, invite_link.invite_link, 'active', group_data['group_id']))

        escrow_db.conn.commit()

        # Send confirmation to the user
        success_msg = await translate(
            f"🏢 <b>Escrow Group Setup Complete</b>\n\n"
            f"Group Name: {message.chat.title}\n"
            f"Your escrow group is now ready!\n\n"
            f"Share this link with the buyer/seller:\n"
            f"<code>{invite_link.invite_link}</code>\n\n"
            f"Note: This link is for 2 members only—third parties are not allowed to join.",
            lang
        )

        await message.reply(success_msg, parse_mode="HTML")

        # Also send a message to the user's private chat
        try:
            await bot.send_message(
                message.from_user.id,
                success_msg,
                parse_mode="HTML"
            )
        except:
            pass  # If we can't message the user privately, it's okay

    except Exception as e:
        print(f"Error initializing escrow group: {e}")
        await message.reply(await translate(
            "An error occurred during group setup. Please try again or contact support.",
            lang
        ))


# KEEP THE CORRECT HANDLER FOR create_escrow_group:
# Update the callback handler to provide instructions instead of trying to create the group
@dp.callback_query(lambda c: c.data == "create_escrow_group")
async def create_escrow_group_callback(callback_query: types.CallbackQuery):
    lang = get_user_language(callback_query.from_user.id)

    # Show loading message
    await bot.answer_callback_query(
        callback_query.id,
        text=await translate("Preparing your escrow group...", lang)
    )

    # Create the group record and get instructions
    result = await escrow_db.create_escrow_group(
        callback_query.from_user.id,
        callback_query.from_user.username or callback_query.from_user.first_name
    )

    if result['success']:
        instruction_msg = await translate(
            f"📋 <b>How to Create Your Escrow Group</b>\n\n"
            f"{result['instructions']}\n\n"
            f"Once you've created the group and added me as admin, "
            f"I'll help you set up the secure escrow environment.",
            lang
        )

        await bot.send_message(
            callback_query.from_user.id,
            instruction_msg,
            parse_mode="HTML"
        )
    else:
        error_msg = await translate(
            f"❌ <b>Error Creating Group</b>\n\n"
            f"Could not initialize escrow group. Please try again later.\n\n"
            f"Error: {result['error']}",
            lang
        )

        await bot.send_message(
            callback_query.from_user.id,
            error_msg,
            parse_mode="HTML"
        )

    # -----------------------
    # GROUP-ONLY CHECK
    # -----------------------


 
def is_group_only(message: types.Message):
    return message.chat.type in ["supergroup", "group"]

    # -----------------------
    # HELPER: SAVE ROLE
    # -----------------------


def save_role(chat_id, user_id, role, crypto_address):
    cursor = escrow_db.conn.cursor()
    cursor.execute('''
         INSERT OR REPLACE INTO group_users (chat_id, user_id, role, crypto_address)
         VALUES (?, ?, ?, ?)
     ''', (chat_id, user_id, role, crypto_address))
    conn.commit()

 


































  # -----------------------
# /buyer COMMAND - MODERN STYLING
# -----------------------

@dp.message(Command("buyer"))
async def buyer_command(message: types.Message):
    # Debug logging
    logger.info(f"🔍 BUYER COMMAND DEBUG:")
    logger.info(f"  - Chat ID: {message.chat.id}")
    logger.info(f"  - Chat Type: {message.chat.type}")
    logger.info(f"  - User ID: {message.from_user.id}")
    logger.info(f"  - Message Text: {message.text}")
    logger.info(f"  - Is Group Check: {is_group_only(message)}")
    
    if not is_group_only(message):
        logger.warning(f"❌ Buyer command rejected - not in group. Chat type: {message.chat.type}")
        await message.reply("❌ This command can only be used inside the escrow group.")
        return

    # Extract address from command
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(
            "❌ Please provide your wallet address. Example: /buyer bc1q5qul3hvx0826qdn7lcw9k6ttudhnmuhxj30wu4v32lkmcm2yrgg78cyr7")
        return

    address = parts[1]
    coin_type = detect_coin_type(address)

    if coin_type == "UNKNOWN":
        await message.reply("❌ Invalid wallet address format. Please use a valid BTC, ETH, LTC, or USDT-TRC20 address.")
        return

    conn = sqlite3.connect("escrow_bot.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Use a transaction to prevent race conditions
    with conn:
        # Check if there's already a buyer in this group (by any user)
        cursor.execute('SELECT user_id FROM group_users WHERE role = "buyer" AND chat_id = ?', (message.chat.id,))
        existing_buyer = cursor.fetchone()
        
        if existing_buyer and existing_buyer['user_id'] != message.from_user.id:
            await message.reply("❌ There is already a buyer for this transaction. Please wait for a seller.")
            return

        # Check if user already has a buyer role in this group (allow updating address)
        cursor.execute('SELECT role FROM group_users WHERE user_id = ? AND chat_id = ?', 
                       (message.from_user.id, message.chat.id))
        existing_role = cursor.fetchone()
        
        # Allow user to update their buyer address if they're already a buyer
        # Only prevent if they have a different role (like seller)
        if existing_role and existing_role['role'] == "seller":
            await message.reply("❌ You are already registered as a seller in this group. You cannot be both buyer and seller.")
            return

        # Save buyer info in group_users
        cursor.execute('''
            INSERT OR REPLACE INTO group_users (chat_id, user_id, role, crypto_address, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (message.chat.id, message.from_user.id, "buyer", address, int(time.time())))
        
        # Update user_settings to set role as buyer
        cursor.execute('''
            INSERT OR REPLACE INTO user_settings (user_id, role)
            VALUES (?, ?)
        ''', (message.from_user.id, "buyer"))
        
        conn.commit()

    # Modern styled response for buyer declaration
    buyer_response = (
        "🎯 <b>BUYER REGISTRATION CONFIRMED</b>\n\n"
        "┌──────────────────────────────┐\n"
        "│ 👤 <b>USER DETAILS</b>                   │\n"
        "├──────────────────────────────┤\n"
        f"│ <b>Name:</b> {message.from_user.first_name} {message.from_user.last_name or ''} │\n"
        f"│ <b>User ID:</b> <code>{message.from_user.id}</code>        │\n"
        f"│ <b>Username:</b> @{message.from_user.username or 'N/A'}     │\n"
        "└──────────────────────────────┘\n\n"
        "┌──────────────────────────────┐\n"
        "│ 💰 <b>WALLET INFORMATION</b>             │\n"
        "├──────────────────────────────┤\n"
        f"│ <b>Address:</b> <code>{address}</code> │\n"
        f"│ <b>Coin Type:</b> {coin_type}                │\n"
        "└──────────────────────────────┘\n\n"
        "<i>You can update your address before the seller joins.</i>\n\n"
        "🔒 <i>Secure trading with @HoldEscrowBot</i>"
    )

    # Send buyer declaration
    await message.reply(buyer_response, parse_mode="HTML")

    # Modern seller instruction message
    seller_instruction = (
        "⏳ <b>WAITING FOR SELLER</b>\n\n"
        "Please wait for a seller to join using:\n"
        "<code>/seller [wallet_address]</code>\n\n"
        "📋 <b>REQUIREMENTS:</b>\n"
        f"• Must use the same coin type: <b>{coin_type}</b>\n\n"
        "💡 <b>SUPPORTED COINS:</b>\n"
        "• BTC (Bitcoin)\n"
        "• LTC (Litecoin)  \n"
        "• ETH (Ethereum)\n"
        "• USDT (TRC-20)\n\n"
        "⚡ <i>Tip: Copy-paste addresses to avoid errors</i>"
    )

    # Send the seller instruction
    await message.answer(seller_instruction, parse_mode="HTML")

    # Close connection
    conn.close()


# -----------------------
# /seller COMMAND - MODERN STYLING
# -----------------------
@dp.message(Command("seller"))
async def seller_command(message: types.Message):
    # Debug logging
    logger.info(f"🔍 SELLER COMMAND DEBUG:")
    logger.info(f"  - Chat ID: {message.chat.id}")
    logger.info(f"  - Chat Type: {message.chat.type}")
    logger.info(f"  - User ID: {message.from_user.id}")
    logger.info(f"  - Message Text: {message.text}")
    logger.info(f"  - Is Group Check: {is_group_only(message)}")
    
    user_id = message.from_user.id
    
    # Use a single connection for the entire function
    conn = sqlite3.connect("escrow_bot.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if a buyer exists in this group
    cursor.execute('SELECT user_id, crypto_address FROM group_users WHERE role = "buyer" AND chat_id = ?', (message.chat.id,))
    buyer_row = cursor.fetchone()
    
    if not buyer_row:
        await message.reply("❌ A buyer must register first before a seller can join.")
        conn.close()
        return
    
    buyer_id = buyer_row['user_id']
    buyer_address = buyer_row['crypto_address']
    
    # Check if user is trying to be both buyer and seller
    if buyer_id == user_id:
        await message.reply("❌ You cannot be both the buyer and seller in the same transaction.")
        conn.close()
        return

    # Extract address from command
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(
            "❌ Please provide your wallet address. Example: /seller bc1q5qul3hvx0826qdn7lcw9k6ttudhnmuhxj30wu4v32lkmcm2yrgg78cyr7")
        conn.close()
        return

    address = parts[1]
    coin_type = detect_coin_type(address)

    if coin_type == "UNKNOWN":
        await message.reply("❌ Invalid wallet address format. Please use a valid BTC, ETH, LTC, or USDT-TRC20 address.")
        conn.close()
        return

    # Check coin type compatibility with buyer
    buyer_coin_type = detect_coin_type(buyer_address)
    if buyer_coin_type != coin_type:
        await message.reply(
            f"❌ Coin type mismatch! Buyer is using {buyer_coin_type}, but you provided a {coin_type} address. Please use a {buyer_coin_type} address.")
        conn.close()
        return

    # Save seller info
    cursor.execute('''
        INSERT OR REPLACE INTO group_users (chat_id, user_id, role, crypto_address, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (message.chat.id, user_id, "seller", address, int(time.time())))
    
    # Update user_settings to set role as seller
    cursor.execute('''
        INSERT OR REPLACE INTO user_settings (user_id, role)
        VALUES (?, ?)
    ''', (user_id, "seller"))
    
    conn.commit()

    # Modern styled response for seller declaration
    seller_response = (
        "🎯 <b>SELLER REGISTRATION CONFIRMED</b>\n\n"
        "┌──────────────────────────────┐\n"
        "│ 👤 <b>USER DETAILS</b>                   │\n"
        "├──────────────────────────────┤\n"
        f"│ <b>Name:</b> {message.from_user.first_name} {message.from_user.last_name or ''} │\n"
        f"│ <b>User ID:</b> <code>{message.from_user.id}</code>        │\n"
        f"│ <b>Username:</b> @{message.from_user.username or 'N/A'}     │\n"
        "└──────────────────────────────┘\n\n"
        "┌──────────────────────────────┐\n"
        "│ 💰 <b>WALLET INFORMATION</b>             │\n"
        "├──────────────────────────────┤\n"
        f"│ <b>Address:</b> <code>{address}</code> │\n"
        f"│ <b>Coin Type:</b> {coin_type}                │\n"
        "└──────────────────────────────┘\n\n"
        "<i>Transaction is now being created...</i>\n\n"
        "🔒 <i>Secure trading with @HoldEscrowBot</i>"
    )

    # Send seller declaration
    await message.reply(seller_response, parse_mode="HTML")

    # Get buyer and seller info for display
    try:
        buyer_user = await bot.get_chat(buyer_id)
        buyer_username = buyer_user.username or buyer_user.first_name
    except:
        buyer_username = "Unknown"

    seller_username = message.from_user.username or message.from_user.first_name

    # Generate transaction ID
    tx_id = generate_transaction_id()

    # Get escrow wallet address
    escrow_address = get_escrow_wallet(coin_type)
    if not escrow_address:
        await message.reply("❌ Error: No escrow wallet available for this coin type.")
        conn.close()
        return

    # Modern transaction summary
    transaction_summary = (
        "🎉 <b>TRANSACTION CREATED SUCCESSFULLY</b>\n\n"
        "┌──────────────────────────────┐\n"
        "│ 📋 <b>TRANSACTION DETAILS</b>           │\n"
        "├──────────────────────────────┤\n"
        f"│ <b>ID:</b> <code>{tx_id}</code> │\n"
        f"│ <b>Coin:</b> {coin_type}                │\n"
        "└──────────────────────────────┘\n\n"
        "👤 <b>BUYER</b>\n"
        f"• {buyer_username} (<code>{buyer_id}</code>)\n\n"
        "🛒 <b>SELLER</b>\n"
        f"• {seller_username} (<code>{message.from_user.id}</code>)\n\n"
        "🏦 <b>ESCROW ADDRESS</b>\n"
        f"<code>{escrow_address}</code>\n\n"
        "🔒 <b>SECURITY NOTICE</b>\n"
        "Always verify the escrow address in the verification group before sending funds.\n\n"
        "💡 <b>NEXT STEPS</b>\n"
        "1. Buyer sends funds to escrow address\n"
        "2. Share transaction hash using /blockchain [hash]\n"
        "3. Seller fulfills obligations\n"
        "4. Buyer releases funds with /release\n\n"
        "⚡ <i>Secure trading with @HoldEscrowBot</i>"
    )
    
    # Send the transaction summary
    await message.answer(transaction_summary, parse_mode="HTML")
    
    # Save transaction to database
    cursor.execute('''
        INSERT INTO transactions (tx_id, buyer_id, seller_id, coin, escrow_address, group_id, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (tx_id, buyer_id, user_id, coin_type, escrow_address, message.chat.id, int(time.time()), "pending"))
    conn.commit()
    
    # Verification instruction
    verification_instruction = (
        "🔍 <b>VERIFICATION REQUIRED</b>\n\n"
        f"@{buyer_username}, please verify the escrow address in the verification group before sending funds.\n\n"
        "After verification, send the agreed amount and use /blockchain [hash] to monitor your transaction."
    )
    
    # Send verification instruction
    await message.answer(verification_instruction, parse_mode="HTML")
    
    # Update the group profile picture
    try:
        chat = await bot.get_chat(message.chat.id)
        group_name = chat.title
        logo_path = await create_group_logo_image(buyer_username, seller_username)
        if logo_path:
            photo = FSInputFile(logo_path)
            await bot.set_chat_photo(message.chat.id, photo)
            os.remove(logo_path)
            print(f"Updated group profile picture for {group_name}")
    except Exception as e:
        print(f"Could not update group photo: {e}")
    
    # Request transaction hash from buyer
    request_hash_msg = (
        f"👋 @{buyer_username}, please send your transaction hash after payment\n\n"
        "📋 <b>INSTRUCTIONS:</b>\n"
        "1. Send exact amount to escrow address\n"
        "2. Copy transaction hash (TxID) from your wallet\n"
        "3. Paste it here in this chat\n\n"
        "🔍 I'll verify it immediately and confirm receipt!"
    )

    await message.answer(request_hash_msg, parse_mode="HTML")
    
    # Close connection
    conn.close()


  # Enhanced Blockchain API configuration
BLOCKCHAIN_APIS = {
    'BTC': {
        'url': 'https://api.blockcypher.com/v1/btc/main/txs/{}',
        'params': {'token': Config.API_KEYS['BLOCKCYPHER']},
        'parser': 'parse_bitcoin_transaction'
    },
    'ETH': {
        'url': 'https://api.etherscan.io/api',
        'params_template': {
            'module': 'proxy',
            'action': 'eth_getTransactionByHash',
            'txhash': '{}',
            'apikey': Config.API_KEYS['ETH']
        },
        'parser': 'parse_ethereum_transaction'
    },
    'USDT': {
        'url': 'https://api.etherscan.io/api',
        'params_template': {
            'module': 'account',
            'action': 'tokentx',
            'txhash': '{}',
            'apikey': Config.API_KEYS['ETH'],
            'sort': 'desc'
        },
        'parser': 'parse_usdt_token_transaction'
    },
    'LTC': {
        'url': 'https://api.blockcypher.com/v1/ltc/main/txs/{}',
        'params': {'token': Config.API_KEYS['BLOCKCYPHER']},
        'parser': 'parse_litecoin_transaction'
    }
}

# Rate limiter for APIs
class RateLimiter:
    def __init__(self, calls_per_second: float = 0.2):
        self.calls_per_second = calls_per_second
        self.last_call = time.time()
        self.lock = asyncio.Lock()
    
    async def wait(self):
        async with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            wait_time = max(0, (1 / self.calls_per_second) - elapsed)
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_call = time.time()

# Create rate limiters for each API
rate_limiters = {
    'BLOCKCYPHER': RateLimiter(0.2),
    'ETHERSCAN': RateLimiter(0.2)
}

# Background monitoring tasks
monitoring_tasks = {}

# ========================
# ENHANCED BLOCKCHAIN PARSER FUNCTIONS
# ========================
async def parse_bitcoin_transaction(data: dict, tx_hash: str) -> dict:
    """Parse Bitcoin transaction data from BlockCypher API"""
    try:
        if 'error' in data:
            print(f"BlockCypher API error: {data.get('error')}")
            return None
            
        # Get transaction details
        confirmations = data.get('confirmations', 0)
        total_amount = data.get('total', 0) / 10**8  # Convert from satoshis to BTC
        
        # Get sender and receiver addresses
        inputs = data.get('inputs', [])
        outputs = data.get('outputs', [])
        
        senders = []
        for inp in inputs:
            if 'addresses' in inp:
                senders.extend(inp['addresses'])
        
        receivers = []
        amounts = []
        for out in outputs:
            if 'addresses' in out:
                receivers.extend(out['addresses'])
                amounts.append(out.get('value', 0) / 10**8)  # Convert to BTC
        
        return {
            'coin': 'BTC',
            'hash': tx_hash,
            'confirmations': confirmations,
            'total_amount': total_amount,
            'senders': list(set(senders)),
            'receivers': list(set(receivers)),
            'amounts': amounts,
            'status': 'confirmed' if confirmations > 0 else 'unconfirmed',
            'timestamp': data.get('received', ''),
            'block_height': data.get('block_height', '')
        }
    except Exception as e:
        print(f"Error parsing Bitcoin transaction: {e}")
        return None

async def parse_ethereum_transaction(data: dict, tx_hash: str) -> dict:
    """Parse Ethereum transaction data from Etherscan API"""
    try:
        result = data.get('result', {})
        if not result:
            print("Etherscan API returned no result")
            return None
            
        # Check if transaction exists
        if result is None:
            print("Etherscan API returned null result")
            return None
            
        # Convert from wei to ETH
        amount = int(result.get('value', '0'), 16) / 10**18
        from_address = result.get('from', '')
        to_address = result.get('to', '')
        
        # Get block number for confirmations
        block_number = int(result.get('blockNumber', '0'), 16) if result.get('blockNumber') else 0
        
        return {
            'coin': 'ETH',
            'hash': tx_hash,
            'amount': amount,
            'from_address': from_address,
            'to_address': to_address,
            'block_number': block_number,
            'status': 'confirmed' if block_number > 0 else 'pending',
            'gas_price': int(result.get('gasPrice', '0'), 16) / 10**18,
            'gas_used': int(result.get('gas', '0'), 16)
        }
    except Exception as e:
        print(f"Error parsing Ethereum transaction: {e}")
        return None

async def parse_usdt_token_transaction(data: dict, tx_hash: str) -> dict:
    """Parse USDT (ERC-20) transaction data from Etherscan Token API"""
    try:
        # Check API response status
        if data.get('status') != '1' and data.get('message') != 'OK':
            print(f"Etherscan token API error: {data.get('message')}")
            return None
            
        results = data.get('result', [])
        if not results:
            print("Etherscan token API returned no results")
            return None
        
        # Find USDT transactions in the results
        for tx in results:
            if (tx.get('hash') == tx_hash and 
                tx.get('tokenSymbol', '').upper() == 'USDT'):
                
                # Convert value with proper decimals
                decimals = int(tx.get('tokenDecimal', 6))
                amount = float(tx.get('value', 0)) / (10 ** decimals)
                
                return {
                    'coin': 'USDT',
                    'hash': tx_hash,
                    'amount': amount,
                    'from_address': tx.get('from', ''),
                    'to_address': tx.get('to', ''),
                    'block_number': int(tx.get('blockNumber', 0)),
                    'status': 'confirmed',
                    'contract_address': tx.get('contractAddress', ''),
                    'confirmations': int(tx.get('confirmations', 0)),
                    'timestamp': tx.get('timeStamp', '')
                }
        
        print(f"No USDT transaction found with hash: {tx_hash}")
        return None
        
    except Exception as e:
        print(f"Error parsing USDT token transaction: {e}")
        return None

async def parse_litecoin_transaction(data: dict, tx_hash: str) -> dict:
    """Parse Litecoin transaction data from BlockCypher API"""
    try:
        if 'error' in data:
            print(f"BlockCypher API error: {data.get('error')}")
            return None
            
        # Get transaction details
        confirmations = data.get('confirmations', 0)
        total_amount = data.get('total', 0) / 10**8  # Convert from litoshis to LTC
        
        # Get sender and receiver addresses
        inputs = data.get('inputs', [])
        outputs = data.get('outputs', [])
        
        senders = []
        for inp in inputs:
            if 'addresses' in inp:
                senders.extend(inp['addresses'])
        
        receivers = []
        amounts = []
        for out in outputs:
            if 'addresses' in out:
                receivers.extend(out['addresses'])
                amounts.append(out.get('value', 0) / 10**8)  # Convert to LTC
        
        return {
            'coin': 'LTC',
            'hash': tx_hash,
            'confirmations': confirmations,
            'total_amount': total_amount,
            'senders': list(set(senders)),
            'receivers': list(set(receivers)),
            'amounts': amounts,
            'status': 'confirmed' if confirmations > 0 else 'unconfirmed',
            'timestamp': data.get('received', ''),
            'block_height': data.get('block_height', '')
        }
    except Exception as e:
        print(f"Error parsing Litecoin transaction: {e}")
        return None

# ========================
# TRANSACTION TRACKING COMMAND
# ========================
@dp.message(Command("blockchain"))
async def cmd_blockchain(message: types.Message):
    """Track a transaction by its hash - requires explicit command"""
    # Parse command arguments
    args = message.text.split()
    
    if len(args) < 2:
        await message.reply(
            "❌ Please provide a transaction hash. Example:\n"
            "<code>/blockchain 0x...</code>\n"
            "Or specify coin type:\n"
            "<code>/blockchain usdt 0x...</code>"
        )
        return
    
    # Check if user specified coin type
    coin_type = None
    tx_hash = ""
    
    if len(args) >= 3:
        # User specified coin type: /blockchain usdt 0x...
        coin_type = args[1].upper()
        tx_hash = " ".join(args[2:])
    else:
        # User just provided hash: /blockchain 0x...
        tx_hash = args[1]
        # Try to auto-detect coin type
        coin_type = detect_coin_from_hash(tx_hash)
    
    # Clean the hash
    tx_hash = clean_transaction_hash(tx_hash, coin_type)
    
    # If we still don't have a coin type, try to detect it from the cleaned hash
    if not coin_type:
        coin_type = detect_coin_from_hash(tx_hash)
    
    # Show loading message
    loading_msg = await message.reply("🔍 Tracking transaction... This may take a few seconds.")
    
    try:
        # Track the transaction
        result = await track_transaction(tx_hash, coin_type)
        
        if result['success']:
            response = format_tracking_response(result, tx_hash, coin_type)
            await loading_msg.edit_text(response, parse_mode="HTML")
            
            # Start background monitoring if transaction is pending
            if result['data'].get('status') == 'pending':
                await start_background_monitoring(message.chat.id, tx_hash, coin_type)
        else:
            error_msg = f"❌ {result['error']}"
            
            # Add debugging info if available
            if 'debug' in result:
                error_msg += f"\n\nDebug: {result['debug']}"
                
            await loading_msg.edit_text(error_msg)
            
            # Start background monitoring for pending transactions
            await start_background_monitoring(message.chat.id, tx_hash, coin_type)
            
    except Exception as e:
        print(f"Error tracking transaction: {e}")
        await loading_msg.edit_text("❌ An error occurred while tracking the transaction.")

async def track_transaction(tx_hash: str, coin_type: str):
    """Track a transaction using blockchain APIs"""
    # Clean the hash
    tx_hash = clean_transaction_hash(tx_hash, coin_type)
    
    # Validate hash format
    if not is_valid_tx_hash(tx_hash, coin_type):
        return {
            'success': False,
            'error': f"Invalid {coin_type} transaction hash format.",
            'debug': f"Hash: {tx_hash}, Coin: {coin_type}"
        }
    
    # Get API configuration
    api_config = BLOCKCHAIN_APIS.get(coin_type)
    if not api_config:
        return {
            'success': False,
            'error': f"Unsupported coin type: {coin_type}"
        }
    
    # Apply rate limiting
    limiter_name = 'ETHERSCAN' if coin_type in ['ETH', 'USDT'] else 'BLOCKCYPHER'
    await rate_limiters[limiter_name].wait()
    
    try:
        # Make API request
        if coin_type in ['ETH', 'USDT']:
            # For Etherscan, we need to format the params
            params = {k: v.format(tx_hash) if isinstance(v, str) and '{}' in v else v 
                     for k, v in api_config['params_template'].items()}
            url = api_config['url']
        else:
            # For BlockCypher, we format the URL
            url = api_config['url'].format(tx_hash)
            params = api_config.get('params', {})
        
        print(f"Making API request to: {url}")
        print(f"Params: {params}")
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=10) as response:
                response_text = await response.text()
                print(f"API response status: {response.status}")
                print(f"API response: {response_text[:500]}...")  # First 500 chars
                
                if response.status != 200:
                    return {
                        'success': False,
                        'error': f"API returned status {response.status}",
                        'debug': f"URL: {url}, Response: {response_text[:200]}..."
                    }
                
                data = await response.json()
                
                # Get the parser function
                parser_name = api_config['parser']
                parser_func = globals().get(parser_name)
                
                if not parser_func:
                    return {
                        'success': False,
                        'error': f"Parser function {parser_name} not found."
                    }
                
                result = await parser_func(data, tx_hash)
                
                if result:
                    return {
                        'success': True,
                        'data': result
                    }
                else:
                    # For USDT, try alternative parsing if the first attempt failed
                    if coin_type == 'USDT':
                        # Try to parse as a regular Ethereum transaction
                        eth_config = BLOCKCHAIN_APIS['ETH']
                        eth_params = {k: v.format(tx_hash) if isinstance(v, str) and '{}' in v else v 
                                     for k, v in eth_config['params_template'].items()}
                        
                        async with session.get(eth_config['url'], params=eth_params, timeout=10) as eth_response:
                            if eth_response.status == 200:
                                eth_data = await eth_response.json()
                                eth_result = await parse_ethereum_transaction(eth_data, tx_hash)
                                if eth_result:
                                    return {
                                        'success': True,
                                        'data': eth_result
                                    }
                    
                    return {
                        'success': False,
                        'error': "Transaction not found or not confirmed yet.",
                        'debug': f"API returned data but parser couldn't extract transaction info. Data: {str(data)[:200]}..."
                    }
                    
    except asyncio.TimeoutError:
        return {
            'success': False,
            'error': "API request timeout. Please try again later."
        }
    except Exception as e:
        print(f"API error: {e}")
        return {
            'success': False,
            'error': f"API error: {str(e)}"
        }

async def start_background_monitoring(chat_id: int, tx_hash: str, coin_type: str):
    """Start background monitoring for a transaction"""
    # Check if already monitoring this transaction
    if (chat_id, tx_hash) in monitoring_tasks:
        return
    
    # Create monitoring task
    task = asyncio.create_task(monitor_transaction(chat_id, tx_hash, coin_type))
    monitoring_tasks[(chat_id, tx_hash)] = task
    
    # Send notification
    await bot.send_message(
        chat_id,
        f"🔍 I'll monitor transaction `{tx_hash}` in the background and notify you when it's confirmed.",
        parse_mode="Markdown"
    )

async def monitor_transaction(chat_id: int, tx_hash: str, coin_type: str):
    """Monitor a transaction in the background until it's confirmed"""
    max_attempts = 30  # Monitor for up to 30 minutes
    check_interval = 60  # Check every 60 seconds
    
    for attempt in range(max_attempts):
        await asyncio.sleep(check_interval)
        
        print(f"Background check {attempt + 1} for {tx_hash}")
        
        try:
            result = await track_transaction(tx_hash, coin_type)
            
            if result['success']:
                if result['data'].get('status') == 'confirmed':
                    # Transaction confirmed, send notification
                    response = format_tracking_response(result, tx_hash, coin_type)
                    await bot.send_message(chat_id, response, parse_mode="HTML")
                    
                    # Stop monitoring
                    if (chat_id, tx_hash) in monitoring_tasks:
                        del monitoring_tasks[(chat_id, tx_hash)]
                    return
            else:
                print(f"Background check failed: {result.get('error')}")
                
        except Exception as e:
            print(f"Error in background monitoring: {e}")
    
    # If we get here, monitoring timed out
    if (chat_id, tx_hash) in monitoring_tasks:
        del monitoring_tasks[(chat_id, tx_hash)]
    
    await bot.send_message(
        chat_id,
        f"⏰ Stopped monitoring transaction `{tx_hash}` after {max_attempts} minutes. It may still be pending.",
        parse_mode="Markdown"
    )

def detect_coin_from_hash(tx_hash: str) -> str:
    """Detect coin type from transaction hash format"""
    # Clean the hash first
    tx_hash = clean_transaction_hash(tx_hash, None)
    
    if not tx_hash:
        return None
    
    # Check for Ethereum-style hashes (0x followed by 64 hex chars)
    if tx_hash.startswith('0x') and len(tx_hash) == 66 and re.match(r'^0x[a-f0-9]{64}$', tx_hash):
        return 'ETH'  # We'll assume ETH, but it could be USDT
    
    # Check for Bitcoin/Litecoin-style hashes (64 hex chars)
    elif len(tx_hash) == 64 and re.match(r'^[a-f0-9]{64}$', tx_hash):
        # We can't distinguish between BTC and LTC from hash alone
        # So we'll try BTC first, then LTC if BTC fails
        return 'BTC'
    
    return None

def clean_transaction_hash(tx_hash: str, coin_type: str = None) -> str:
    """Clean transaction hash by removing extra spaces and fixing common issues"""
    if not tx_hash:
        return ""
    
    # Remove all whitespace (spaces, newlines, etc.)
    tx_hash = ''.join(tx_hash.split())
    
    # If we know it's an Ethereum hash, ensure it starts with 0x
    if coin_type in ['ETH', 'USDT'] or (tx_hash.startswith('0x') or tx_hash.startswith('Ox')):
        # Ensure it starts with 0x (not Ox or other variants)
        if not tx_hash.startswith('0x'):
            if tx_hash.startswith('Ox'):
                tx_hash = '0x' + tx_hash[2:]
            else:
                tx_hash = '0x' + tx_hash
        
        # Replace common mis-typed characters
        replacements = {
            'O': '0',  # Capital O to zero
            'o': '0',  # Lowercase o to zero
            'I': '1',  # Capital I to one
            'l': '1',  # Lowercase L to one
        }
        
        for wrong, correct in replacements.items():
            tx_hash = tx_hash.replace(wrong, correct)
    
    return tx_hash.lower()  # Standardize to lowercase

def is_valid_tx_hash(tx_hash: str, coin_type: str) -> bool:
    """Validate transaction hash format based on coin type"""
    # Clean the hash first
    tx_hash = clean_transaction_hash(tx_hash, coin_type)
    
    if coin_type in ['BTC', 'LTC']:
        # BTC/LTC hashes should be 64 hex characters
        return bool(re.match(r'^[a-f0-9]{64}$', tx_hash))
    elif coin_type in ['ETH', 'USDT']:
        # ETH/USDT hashes should start with 0x followed by 64 hex characters
        return bool(re.match(r'^0x[a-f0-9]{64}$', tx_hash))
    return False

def format_tracking_response(result: dict, tx_hash: str, coin_type: str) -> str:
    """Format the transaction tracking response"""
    data = result['data']
    
    if coin_type in ['BTC', 'LTC']:
        response = (
            f"🔍 <b>Transaction Details - {coin_type}</b>\n\n"
            f"<b>Hash:</b> <code>{tx_hash}</code>\n"
            f"<b>Status:</b> {data['status'].capitalize()}\n"
            f"<b>Confirmations:</b> {data['confirmations']}\n"
            f"<b>Total Amount:</b> {data['total_amount']:.8f} {coin_type}\n"
            f"<b>Block Height:</b> {data.get('block_height', 'N/A')}\n"
            f"<b>Timestamp:</b> {data.get('timestamp', 'N/A')}\n\n"
            f"<b>Senders:</b>\n" + "\n".join([f"• <code>{addr}</code>" for addr in data['senders'][:3]]) + 
            f"\n\n<b>Receivers:</b>\n" + "\n".join([f"• <code>{addr}</code>" for addr in data['receivers'][:3]])
        )
    elif coin_type == 'ETH':
        response = (
            f"🔍 <b>Transaction Details - ETH</b>\n\n"
            f"<b>Hash:</b> <code>{tx_hash}</code>\n"
            f"<b>Status:</b> {data['status'].capitalize()}\n"
            f"<b>Amount:</b> {data['amount']:.6f} ETH\n"
            f"<b>Block Number:</b> {data['block_number']}\n"
            f"<b>From:</b> <code>{data['from_address']}</code>\n"
            f"<b>To:</b> <code>{data['to_address']}</code>\n"
            f"<b>Gas Price:</b> {data['gas_price']:.8f} ETH\n"
            f"<b>Gas Used:</b> {data['gas_used']}\n"
        )
    elif coin_type == 'USDT':
        response = (
            f"🔍 <b>Transaction Details - USDT</b>\n\n"
            f"<b>Hash:</b> <code>{tx_hash}</code>\n"
            f"<b>Status:</b> {data['status'].capitalize()}\n"
            f"<b>Amount:</b> {data['amount']:.2f} USDT\n"
            f"<b>Block Number:</b> {data.get('block_number', 'N/A')}\n"
            f"<b>Confirmations:</b> {data.get('confirmations', 'N/A')}\n"
            f"<b>From:</b> <code>{data.get('from_address', 'N/A')}</code>\n"
            f"<b>To:</b> <code>{data.get('to_address', 'N/A')}</code>\n"
            f"<b>Contract:</b> <code>{data.get('contract_address', 'N/A')}</code>\n"
        )
    else:
        response = f"❌ Unsupported coin type: {coin_type}"
    
    return response

 

# -----------------------
# /balance COMMAND
# -----------------------
@dp.message(Command("balance"))
async def balance_command(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("escrow_bot.db")
    cursor = conn.cursor()

    cursor.execute('''
        SELECT amount_received, coin, escrow_address, payment_tx_hash 
        FROM transactions 
        WHERE (buyer_id = ? OR seller_id = ?) 
        ORDER BY created_at DESC LIMIT 1
    ''', (user_id, user_id))

    tx_data = cursor.fetchone()
    conn.close()

    if not tx_data or not tx_data[0]:
        await message.reply("No transactions found or no payments received yet.")
        return

    amount, coin, escrow_address, tx_hash = tx_data
    amount_formatted = format_crypto_amount(amount, coin)

    balance_msg = (
        "💼 **Escrow Balance Summary**\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 **Amount:** {amount_formatted} {coin}\n"
        f"🔗 **Transaction Hash:** `{tx_hash}`\n"
        f"🏦 **Escrow Address:** `{escrow_address}`\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ Funds are securely held in escrow\n"
        "📋 Use /pay_seller to complete transaction\n"
        "🔄 Use /refund_buyer to cancel transaction"
    )

    await message.reply(balance_msg, parse_mode="Markdown")


def format_crypto_amount(amount, coin_type):
    """Format amount based on coin type, handling None values"""
    if amount is None:
        return "0.0"
    
    # Handle case where coin_type might be None
    if coin_type is None:
        coin_type = "BTC"  # Default to BTC formatting
    
    decimals = {
        'BTC': 8,
        'ETH': 6,
        'USDT': 2,
        'LTC': 8
    }
    
    # Use 8 decimals as default if coin_type not found
    decimal_places = decimals.get(coin_type, 8)
    
    try:
        return f"{float(amount):,.{decimal_places}f}"
    except (ValueError, TypeError):
        return "0.0"

# -----------------------
# Message handler for transaction hashes
# -----------------------
@dp.message(lambda message: message.text and not message.text.startswith('/'))
async def handle_transaction_hash(message: types.Message):
    # Check if message might be a transaction hash
    possible_hash = message.text.strip()
    if len(possible_hash) >= 64:  # Most hashes are 64+ chars
        await verify_transaction_hash(message)


# Create a function to generate the group logo image
async def create_group_logo_image(buyer_username: str, seller_username: str) -> str:
    try:
        # Create image with dark background
        width, height = 600, 400
        image = Image.new('RGB', (width, height), color=(30, 30, 46))
        draw = ImageDraw.Draw(image)

        # Try to load fonts
        try:
            # Try to use a bold font for the title
            title_font = ImageFont.truetype("arialbd.ttf", 36)
            name_font = ImageFont.truetype("arialbd.ttf", 28)
            username_font = ImageFont.truetype("arial.ttf", 24)
        except:
            # Fallback to default fonts
            title_font = ImageFont.load_default()
            name_font = ImageFont.load_default()
            username_font = ImageFont.load_default()

        # Draw title
        title = "Escrow by @HoldEscrowBot"
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_width) // 2, 50), title, fill=(255, 255, 255), font=title_font)

        # Draw buyer section
        draw.text((100, 150), "Buyer:", fill=(200, 200, 220), font=name_font)
        draw.text((100, 190), f"@{buyer_username}", fill=(150, 200, 150), font=username_font)

        # Draw seller section
        draw.text((100, 250), "Seller:", fill=(200, 200, 220), font=name_font)
        draw.text((100, 290), f"@{seller_username}", fill=(150, 150, 200), font=username_font)

        # Draw a simple logo/icon (shield shape)
        # Draw a shield shape
        shield_points = [
            (width - 100, 50),  # Top
            (width - 150, 100),  # Left
            (width - 150, 150),  # Left bottom
            (width - 100, 180),  # Bottom center
            (width - 50, 150),  # Right bottom
            (width - 50, 100)  # Right top
        ]
        draw.polygon(shield_points, fill=(80, 120, 180), outline=(100, 150, 200), width=3)

        # Draw a checkmark inside the shield
        draw.line([(width - 120, 110), (width - 100, 130), (width - 80, 90)], fill=(255, 255, 255), width=4)

        # Save image
        os.makedirs("tmp", exist_ok=True)
        image_path = f"tmp/logo_{int(time.time())}.png"
        image.save(image_path)
        return image_path
    except Exception as e:
        print(f"Error creating group logo: {e}")
        return None


# Also add this after the verification message to simulate the admin message
admin_message = (
    "Group, send the agreed amount to the verified address.\n\n"
    "Use /qr for QR code, /balance to check balance, /blockchain to track transaction."
)




# Add a callback handler for the create escrow button
@dp.callback_query(lambda c: c.data == "create_escrow_group")
async def create_escrow_group(callback_query: types.CallbackQuery):
    lang = get_user_language(callback_query.from_user.id)

    # Show loading message
    await bot.answer_callback_query(
        callback_query.id,
        text=await translate("Creating your escrow group...", lang)
    )

    # Create the group
    result = await escrow_db.create_escrow_group(
        callback_query.from_user.id,
        callback_query.from_user.username or callback_query.from_user.first_name
    )

    if result['success']:
        success_msg = await translate(
            f"🏢 <b>Escrow Group Created</b>\n\n"
            f"Group Name: {result['group_name']}\n"
            f"Creator: @{callback_query.from_user.username or callback_query.from_user.first_name}\n\n"
            f"Join this escrow group and share the link with the buyer/seller:\n"
            f"<code>{result['invite_link']}</code>\n\n"
            f"Note: This link is for 2 members only—third parties are not allowed to join.\n\n"
            f"The button below opens your escrow group after joining with the link.",
            lang
        )

        # Create keyboard with group link
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="🔷 Open Group (After Join)",
                url=f"https://t.me/c/{str(result['chat_id']).replace('-100', '')}"
            )],
            [InlineKeyboardButton(
                text="🔄 Create New Transaction",
                callback_data="create_escrow_start"
            )]
        ])

        await bot.send_message(
            callback_query.from_user.id,
            success_msg,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        # Send welcome message to the group
        group_welcome = await translate(
            f"🛡️ <b>Welcome to {result['group_name']}</b>\n\n"
            f"This is a secure escrow group created by @{callback_query.from_user.username or callback_query.from_user.first_name}.\n\n"
            f"<b>Rules:</b>\n"
            f"• Only discuss the specific transaction\n"
            f"• Be respectful to all parties\n"
            f"• The escrow bot will monitor this conversation\n"
            f"• Do not share sensitive information\n\n"
            f"To start a transaction, use /create in private chat with the bot.",
            lang
        )

        try:
            await bot.send_message(
                result['chat_id'],
                group_welcome,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Could not send message to group: {e}")

    else:
        error_msg = await translate(
            f"❌ <b>Error Creating Group</b>\n\n"
            f"Could not create escrow group. Please try again later.\n\n"
            f"Error: {result['error']}",
            lang
        )

        await bot.send_message(
            callback_query.from_user.id,
            error_msg,
            parse_mode="HTML"
        )


# Add handler for new chat members to enforce the 2-member limit
@dp.chat_member()
async def chat_member_handler(chat_member: types.ChatMemberUpdated):
    # Check if this is one of our escrow groups
    cursor = escrow_db.conn.cursor()
    cursor.execute('SELECT * FROM escrow_groups WHERE chat_id = ?', (chat_member.chat.id,))
    group = cursor.fetchone()

    if not group:
        return

    # Get current member count
    try:
        members_count = await bot.get_chat_members_count(chat_member.chat.id)
    except:
        return

    # If超过 2 members, remove the newest member
    if members_count > MAX_GROUP_MEMBERS:
        try:
            await bot.ban_chat_member(
                chat_id=chat_member.chat.id,
                user_id=chat_member.new_chat_member.user.id
            )

            # Notify the group
            await bot.send_message(
                chat_member.chat.id,
                f"❌ <b>Member Removed</b>\n\n"
                f"@{chat_member.new_chat_member.user.username} was removed because "
                f"this escrow group is limited to 2 members only.",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Error removing member: {e}")


# Update the detect_coin_type function to handle None values
def detect_coin_type(address: str) -> str:
    if not address:
        return "UNKNOWN"
    
    address = address.strip()

    # BTC patterns
    btc_patterns = [
        r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$',  # Legacy BTC addresses
        r'^bc1[ac-hj-np-z02-9]{11,71}$',  # Native SegWit BTC addresses
    ]
    # ETH patterns (also covers USDT-ERC20)
    eth_pattern = r'^0x[a-fA-F0-9]{40}$'
    # USDT-TRC20 pattern (TRON addresses)
    trc20_pattern = r'^T[a-zA-Z0-9]{33}$'
    # LTC patterns
    ltc_patterns = [
        r'^[LM3][a-km-zA-HJ-NP-Z1-9]{26,33}$',  # Legacy LTC addresses
        r'^ltc1[ac-hj-np-z02-9]{11,71}$',  # Native SegWit LTC addresses
    ]

    for pattern in btc_patterns:
        if re.match(pattern, address):
            return "BTC"

    if re.match(eth_pattern, address):
        return "ETH"

    if re.match(trc20_pattern, address):
        return "USDT"

    for pattern in ltc_patterns:
        if re.match(pattern, address):
            return "LTC"

    return "UNKNOWN"


# Add this function to get a random wallet address for a coin type
def get_escrow_wallet(coin_type: str) -> str:
    wallets = Config.WALLETS.get(coin_type, [])
    if wallets:
        return random.choice(wallets)
    return None


# Add this function to generate transaction ID
def generate_transaction_id() -> str:
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    parts = [
        ''.join(random.choice(chars) for _ in range(6)),
        ''.join(random.choice(chars) for _ in range(6)),
        ''.join(random.choice(chars) for _ in range(6))
    ]
    return '-'.join(parts)


# Add this function to create group profile image
async def create_group_profile_image(group_name: str, buyer_username: str, seller_username: str) -> str:
    try:
        # Create image with dark background
        width, height = 600, 600
        image = Image.new('RGB', (width, height), color=(30, 30, 46))
        draw = ImageDraw.Draw(image)

        # Try to load a font, fallback to default if not available
        try:
            title_font = ImageFont.truetype("arialbd.ttf", 30)
            text_font = ImageFont.truetype("arial.ttf", 20)
        except:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()

        # Draw title
        draw.text((width // 2, 50), "@HoldEscrowBot", fill=(255, 255, 255), font=title_font, anchor="mm")

        # Draw group name
        wrapped_name = textwrap.fill(group_name, width=30)
        draw.text((width // 2, 120), wrapped_name, fill=(200, 200, 220), font=text_font, anchor="mm")

        # Draw divider
        draw.line([(50, 180), (width - 50, 180)], fill=(100, 100, 140), width=2)

        # Draw buyer info
        draw.text((width // 2, 230), f"Buyer: @{buyer_username}", fill=(150, 200, 150), font=text_font, anchor="mm")

        # Draw seller info
        draw.text((width // 2, 270), f"Seller: @{seller_username}", fill=(150, 150, 200), font=text_font, anchor="mm")

        # Draw footer
        draw.text((width // 2, height - 50), "Secure Crypto Transactions", fill=(180, 180, 200), font=text_font,
                  anchor="mm")

        # Save image
        os.makedirs("tmp", exist_ok=True)
        image_path = f"tmp/group_{int(time.time())}.png"
        image.save(image_path)
        return image_path
    except Exception as e:
        print(f"Error creating group image: {e}")
        return None


# Fix the group photo update issue in generate_escrow_address function
async def generate_escrow_address(chat_id: int):
    cursor = escrow_db.conn.cursor()

    # Get buyer and seller info
    cursor.execute('SELECT user_id, crypto_address, role FROM group_users WHERE chat_id=?', (chat_id,))
    users = cursor.fetchall()

    buyer_id = None
    seller_id = None
    buyer_address = None
    seller_address = None
    coin_type = None

    for user in users:
        if user[2] == "buyer":
            buyer_id = user[0]
            buyer_address = user[1]
            coin_type = detect_coin_type(buyer_address)
        elif user[2] == "seller":
            seller_id = user[0]
            seller_address = user[1]

    if not all([buyer_id, seller_id, buyer_address, seller_address, coin_type]):
        return

    # Get buyer and seller usernames
    try:
        buyer_user = await bot.get_chat(buyer_id)
        buyer_username = buyer_user.username or buyer_user.first_name
    except:
        buyer_username = "Unknown"

    try:
        seller_user = await bot.get_chat(seller_id)
        seller_username = seller_user.username or seller_user.first_name
    except:
        seller_username = "Unknown"

    # Generate transaction ID
    tx_id = generate_transaction_id()

    # Get escrow wallet address
    escrow_address = get_escrow_wallet(coin_type)
    if not escrow_address:
        await bot.send_message(chat_id, "❌ Error: No escrow wallet available for this coin type.")
        return

    # Create transaction information message
    response = (
        f"### TRANSACTION INFORMATION\n"
        f"TXN ID: {tx_id}\n\n"
        f"- **BUYER**\n"
        f"  @{buyer_username} [{buyer_id}]\n\n"
        f"- **SELLER**\n"
        f"  @{seller_username} [{seller_id}]\n\n"
        f"- **ESCROW ADDRESS**\n"
        f"  {escrow_address} [{coin_type}] [Tap to Copy]\n\n"
        f"---\n\n"
        f"### IMPORTANT: AVOID SCAMS!\n\n"
        f"- Always verify the escrow address by sending it to the Verification Group before sending funds.\n"
        f"- COMMANDS:\n"
        f"  /pay_seller - pay funds to seller.\n"
        f"  /refund_buyer - Return funds to buyer.\n"
        f"- Multiple payments accepted to same address.\n"
        f"- DESCRIPTION\n\n"
        f"Use /description to set clear terms and speed up fund release.\n\n"
        f"**Example:** /description Digital art commission, delivery"
    )

    await bot.send_message(chat_id, response, parse_mode="Markdown")

    # Update group profile picture - FIXED: Use chat_id directly instead of message.chat.id
    try:
        chat = await bot.get_chat(chat_id)
        group_name = chat.title
        logo_path = await create_group_logo_image(buyer_username, seller_username)
        if logo_path:
            photo = FSInputFile(logo_path)
            await bot.set_chat_photo(chat_id, photo)
            os.remove(logo_path)
            print(f"Updated group profile picture for {group_name}")
    except Exception as e:
        print(f"Could not update group photo: {e}")

    # Save transaction to database
    cursor.execute('''
        INSERT INTO transactions (tx_id, buyer_id, seller_id, coin, created_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (tx_id, buyer_id, seller_id, coin_type, int(time.time()), "pending"))
    escrow_db.conn.commit()


 

# Add this function to check if an address is from our escrow pool
def is_escrow_address(address: str) -> bool:
    # Check all wallet types
    for coin_type, addresses in Config.WALLETS.items():
        if address in addresses:
            return True
    return False


# Add this function to get transaction by escrow address
def get_transaction_by_escrow_address(escrow_address: str):
    """
    Get the most recent transaction for a given escrow address.
    Returns the transaction with the latest created_at timestamp.
    """
    conn = sqlite3.connect('escrow_bot.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Order by created_at DESC to get the most recent transaction first
    cursor.execute('SELECT * FROM transactions WHERE escrow_address = ? ORDER BY created_at DESC', (escrow_address,))
    result = cursor.fetchone()
    conn.close()
    return result


# =========================================
# VERIFICATION COMMAND (WORKS IN ANY GROUP)
# =========================================
@dp.message(Command("verify"))
async def verify_command_anywhere(message: types.Message):
    # Extract address from command
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply(
            "❌ Please provide an escrow address. Example: /verify bc1q5qul3hvx0826qdn7lcw9k6ttudhnmuhxj30wu4v32lhmcm2yrgg78cyr7"
        )
        return

    address = parts[1]

    # Check if this is a valid escrow address
    if not is_escrow_address(address):
        await message.reply("❌ This is not a valid escrow address from our system.")
        return

    # Get transaction details for this address
    transaction = get_transaction_by_escrow_address(address)
    if not transaction:
        await message.reply("❌ No active transaction found for this escrow address.")
        return

    # Get user details
    try:
        buyer = await bot.get_chat(transaction['buyer_id'])
        buyer_name = buyer.first_name
        buyer_username = buyer.username or "NoUsername"
    except:
        buyer_name = "Unknown"
        buyer_username = "Unknown"

    try:
        seller = await bot.get_chat(transaction['seller_id'])
        seller_name = seller.first_name
        seller_username = seller.username or "NoUsername"
    except:
        seller_name = "Unknown"
        seller_username = "Unknown"

    # Create verification response
    verification_text = (
        "✅ **VERIFICATION SUCCESSFUL**\n\n"
        f"**Address:** `{address}`\n"
        f"**Transaction ID:** {transaction['tx_id']}\n"
        f"**Buyer:** {buyer_name} (@{buyer_username}, ID: {transaction['buyer_id']})\n"
        f"**Seller:** {seller_name} (@{seller_username}, ID: {transaction['seller_id']})\n\n"
        "This address has been verified as a legitimate HoldEscrowBot address.\n\n"
        "**Valid Escrow Address:** This is the official escrow address for your transaction.\n"
        "As the buyer, you may securely send funds to this address.\n\n"
        "Generated by @HoldEscrowBot."
    )

    await message.reply(verification_text, parse_mode="Markdown")

    # Update transaction status to verified
    cursor = escrow_db.conn.cursor()
    cursor.execute(
        'UPDATE transactions SET status = ?, verified_at = ? WHERE escrow_address = ?',
        ('verified', int(time.time()), address)
    )
    escrow_db.conn.commit()

    # Send notification to the original escrow group
    try:
        original_group_id = transaction.get('group_id')
        if original_group_id:
            notification_msg = (
                f"✅ **Address Verified**\n\n"
                f"The escrow address `{address}` has been successfully verified.\n"
                f"**Transaction ID:** {transaction['tx_id']}\n\n"
                "The buyer can now safely send funds to this address."
            )
            await bot.send_message(original_group_id, notification_msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Could not send notification to original group: {e}")


# ===================================
# HANDLE PASTED ADDRESSES IN ANY CHAT
# ===================================
@dp.message(lambda message: message.text and
                            not message.text.startswith('/') and
                            len(message.text.strip()) > 20 and
                            detect_coin_type(message.text.strip()) != "UNKNOWN")

async def handle_pasted_address_anywhere(message: types.Message):
    """Handle pasted addresses anywhere"""
    address = message.text.strip()

    # Check if this is a valid escrow address
    if is_escrow_address(address):
        # Create inline keyboard with verify button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Verify This Address",
                callback_data=f"verify_address:{address}"
            )]
        ])

        await message.reply(
            "🔍 This looks like a HoldEscrowBot address. Would you like to verify it?",
            reply_markup=keyboard
        )


# ========================
# CALLBACK FOR VERIFY BUTTON
# ========================
@dp.callback_query(lambda c: c.data.startswith("verify_address:"))
async def verify_address_callback(callback_query: types.CallbackQuery):
    await callback_query.answer()

    address = callback_query.data.replace("verify_address:", "")

    # Edit the original message to show verification in progress
    await callback_query.message.edit_text(
        "⏳ Verifying address...",
        reply_markup=None
    )

    # Process the verification
    if not is_escrow_address(address):
        await callback_query.message.edit_text(
            "❌ This is not a valid escrow address from our system."
        )
        return

    # Get transaction details for this address
    transaction = get_transaction_by_escrow_address(address)
    if not transaction:
        await callback_query.message.edit_text(
            "❌ No active transaction found for this escrow address."
        )
        return

    # Get user details - use dictionary-like access for SQLite Row
    try:
        buyer = await bot.get_chat(transaction['buyer_id'])
        buyer_name = buyer.first_name
        buyer_username = buyer.username or "NoUsername"
    except:
        buyer_name = "Unknown"
        buyer_username = "Unknown"

    try:
        seller = await bot.get_chat(transaction['seller_id'])
        seller_name = seller.first_name
        seller_username = seller.username or "NoUsername"
    except:
        seller_name = "Unknown"
        seller_username = "Unknown"

    # Create verification response
    verification_text = (
        "✅ **VERIFICATION SUCCESSFUL**\n\n"
        f"**Address:** `{address}`\n"
        f"**Transaction ID:** {transaction['tx_id']}\n"
        f"**Buyer:** {buyer_name} (@{buyer_username}, ID: {transaction['buyer_id']})\n"
        f"**Seller:** {seller_name} (@{seller_username}, ID: {transaction['seller_id']})\n\n"
        "This address has been verified as a legitimate @HoldEscrowBot address.\n\n"
        "**Valid Escrow Address:** This is the official escrow address for your transaction.\n"
        "As the buyer, you may securely send funds to this address.\n\n"
        "Generated by @HoldEscrowBot."
    )

    await callback_query.message.edit_text(
        verification_text,
        parse_mode="Markdown"
    )

    # Update transaction status to verified
    conn = sqlite3.connect('escrow_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE transactions SET status = ?, verified_at = ? WHERE escrow_address = ?',
        ('verified', int(time.time()), address)
    )
    conn.commit()
    conn.close()

    # Send notification to the original escrow group
    try:
        original_group_id = transaction['group_id'] if 'group_id' in transaction.keys() else None
        if original_group_id:
            notification_msg = (
                f"✅ **Address Verified**\n\n"
                f"The escrow address `{address}` has been successfully verified.\n"
                f"**Transaction ID:** {transaction['tx_id']}\n\n"
                "The buyer can now safely send funds to this address."
            )
            await bot.send_message(original_group_id, notification_msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Could not send notification to original group: {e}")

# ========================
# TERMS OF SERVICE COMMAND
# ========================
@dp.message(Command("terms"))
async def cmd_terms(message: types.Message):
    lang = get_user_language(message.from_user.id)
    terms_text = await translate(
        "📜 <b>@HoldEscrowBot Terms of Service</b>\n"
        "Simple rules to ensure safe, fair, and transparent transactions.\n\n"
        "🎟️ <b>Escrow Fees:</b>\n"
        "• 5.0% for transactions over $100\n"
        "• $5.0 fee for transactions under $100\n"
        "Please consider fees when depositing funds.\n\n"
        "1️⃣ Record or screenshot while verifying goods, testing credentials, or unboxing items. This helps in case of disputes.\n"
        "⬩ Lack of evidence may lead to fund loss.\n\n"
        "2️⃣ Understand the product/service before buying.\n"
        "⬩ It's the buyer's responsibility to know what they are purchasing.\n\n"
        "3️⃣ Release funds only after verifying the product/service.\n"
        "⬩ Once released, funds cannot be recovered.\n\n"
        "4️⃣ Ensure your deposit covers the item cost + escrow fee.\n\n"
        "5️⃣ <b>Inactive or non-responsive users:</b>\n"
        "If the buyer receives the product but ignores the seller and admin, or leaves the group without releasing payment — the seller will receive the funds after a grace period.\n"
        "If the seller ignores the buyer, fails to deliver, or vanishes after delivering faulty goods — the buyer will be refunded after review.\n"
        "⬩ A short waiting period is granted in case of accidental disconnects.\n\n"
        "6️⃣ <b>Escrow Protection:</b>\n"
        "Escrow protects only the current deal started through the bot — it cannot be used for past direct deals, personal disputes, or to claim funds without delivering the agreed product/service.\n\n"
        "7️⃣ <b>Escrow Restrictions:</b>\n"
        "We do not support escrow for SMTP, enrolls, or other high-risk items.\n\n"
        "✦ <b>User Responsibilities:</b>\n"
        "• Verify escrow address and transaction details\n"
        "• Keep credentials secure and report suspicious activity\n"
        "• No refunds for user mistakes or poor due diligence\n"
        "• You're responsible for verifying counterparties\n"
        "• Funds can't be recovered once released — double-check everything\n\n"
        "By using @@HoldEscrowBot, you accept these terms and take full responsibility for your transactions. 🚀",
        lang
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")]
    ])


    await message.reply(terms_text, reply_markup=keyboard, parse_mode="HTML")


@dp.message(Command("instructions"))
async def cmd_instructions(message: types.Message):
    lang = get_user_language(message.from_user.id)

    instructions_text = await translate(
        "💭 <b>INSTRUCTIONS</b>\n"
        "To protect yourself from scams, please follow these guides:\n\n"
        "<b>Tutorials & Safety Tips:</b>\n"
        "⚠️ <a href='https://t.me/HoldEscrowBot/14'>Click here</a>\n"
        " ⤷ Reading is mandatory\n\n"
        "<b>Buyer's Safety Guide:</b>\n"
        "⚠️ <a href='https://t.me/HoldEscrowBot/18'>Click here</a>\n"
        " ⤷ Reading is mandatory\n\n"
        "<b>Seller's Safety Guide:</b>\n"
        "⚠️ <a href='https://t.me/HoldEscrowBot/20'>Click here</a>\n"
        " ⤷ Reading is mandatory",
        lang
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Main", callback_data="back:main_menu")]
    ])
    await message.reply(instructions_text, parse_mode="HTML", reply_markup=keyboard)

@dp.message(Command("whatisescrow"))
async def cmd_whatisescrow(message: types.Message):
    lang = get_user_language(message.from_user.id)

    escrow_text = await translate(
        "💡 <b>Understanding Escrow Services</b>\n\n"
        "✦ <b>Definition:</b>\n"
        "Escrow is a secure financial arrangement where an authorized third party temporarily holds and manages funds during a transaction between two parties.\n\n"
        "🔄 <b>Process Flow:</b>\n"
        "• Step 1: Buyer deposits funds into escrow\n"
        "• Step 2: Seller delivers product/service\n"
        "• Step 3: Buyer verifies & approves\n"
        "• Step 4: Escrow releases payment to seller\n\n"
        "🛡️ <b>Key Benefits:</b>\n"
        "• Fraud prevention systems\n"
        "• Secure payment holding\n"
        "• Verification protocols\n"
        "• Dispute resolution\n"
        "• Complete transaction transparency\n"
        "• Enhanced security\n"
        "• Risk mitigation\n\n"
        "✨ <b>Perfect for:</b> Online purchases, Business deals, Digital assets.\n\n"
        "🤝 Trust & Security Guaranteed! @@HoldEscrowBot",
        lang
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back", callback_data="back_to_main")]
    ])

    await message.reply(escrow_text, reply_markup=keyboard, parse_mode="HTML")




# Callback for TERMS button
@dp.callback_query(lambda c: c.data == "terms")
async def callback_terms(callback: types.CallbackQuery):
    await cmd_terms(callback.message)   # reuse command handler
    await callback.answer()


# Callback for INSTRUCTIONS button
@dp.callback_query(lambda c: c.data == "instructions")
async def callback_instructions(callback: types.CallbackQuery):
    await cmd_instructions(callback.message)
    await callback.answer()


# Callback for WHAT IS ESCROW button
@dp.callback_query(lambda c: c.data == "what_is_escrow")
async def callback_whatisescrow(callback: types.CallbackQuery):
    await cmd_whatisescrow(callback.message)
    await callback.answer()


@dp.message(Command("verify_tx"))
async def verify_tx_command(message: types.Message):
    # Extract hash from command
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Please provide a transaction hash. Example: /verify_tx abc123def456...")
        return
    
    tx_hash = parts[1]
    await verify_transaction_hash(message, tx_hash)

@dp.message(Command("admin_verify"))
async def admin_verify_command(message: types.Message):
    # Check if user is admin
    if message.from_user.id not in Config.ADMIN_IDS:
        await message.reply("❌ This command is for administrators only.")
        return
    
    # Extract hash from command
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("Please provide a transaction hash. Example: /admin_verify abc123def456...")
        return
    
    tx_hash = parts[1]
    
    # Extract optional transaction ID
    tx_id = None
    if len(parts) >= 3:
        tx_id = parts[2]
    
    await admin_verify_transaction(message, tx_hash, tx_id)

async def admin_verify_transaction(message: types.Message, tx_hash: str, tx_id: str = None):
    # Show "verifying" message
    verifying_msg = await message.reply("🔍 Admin verifying transaction...")
    
    # If no TX ID provided, try to find it in the database
    conn = sqlite3.connect("escrow_bot.db")
    cursor = conn.cursor()
    
    if not tx_id:
        cursor.execute('SELECT tx_id, escrow_address, coin FROM transactions WHERE payment_tx_hash = ?', (tx_hash,))
        tx_data = cursor.fetchone()
        if not tx_data:
            await verifying_msg.edit_text("❌ No transaction found with this hash.")
            conn.close()
            return
        tx_id, escrow_address, coin_type = tx_data
    else:
        cursor.execute('SELECT escrow_address, coin FROM transactions WHERE tx_id = ?', (tx_id,))
        tx_data = cursor.fetchone()
        if not tx_data:
            await verifying_msg.edit_text("❌ No transaction found with this ID.")
            conn.close()
            return
        escrow_address, coin_type = tx_data
    
    # Check transaction on blockchain
    tx_info = await check_blockchain_transaction(tx_hash, coin_type, escrow_address)
    if not tx_info:
        await verifying_msg.edit_text("❌ Transaction not found on blockchain.")
        conn.close()
        return
    
    # Update transaction in database
    cursor.execute('''
        UPDATE transactions 
        SET payment_tx_hash = ?, amount_received = ?, status = 'paid', verified_at = ?
        WHERE tx_id = ?
    ''', (tx_hash, tx_info['amount'], int(time.time()), tx_id))
    
    conn.commit()
    conn.close()
    
    # Format amount nicely
    amount_formatted = format_crypto_amount(tx_info['amount'], coin_type)
    
    # Send confirmation message
    confirmation_msg = (
        "✅ **Admin Verification Complete**\n\n"
        f"**Transaction ID:** {tx_id}\n"
        f"**Amount:** {amount_formatted} {coin_type}\n"
        f"**Transaction Hash:** `{tx_hash}`\n"
        f"**Status:** {tx_info['confirmations']} confirmations\n\n"
        "Transaction has been manually verified and marked as paid."
    )
    
    await verifying_msg.edit_text(confirmation_msg, parse_mode="Markdown")
@dp.message(Command("status"))
async def status_command(message: types.Message):
    user_id = message.from_user.id
    conn = sqlite3.connect("escrow_bot.db")
    cursor = conn.cursor()
    
    # Get latest transaction for this user
    cursor.execute('''
        SELECT tx_id, amount, amount_received, coin, escrow_address, payment_tx_hash, status 
        FROM transactions 
        WHERE (buyer_id = ? OR seller_id = ?) 
        ORDER BY created_at DESC LIMIT 1
    ''', (user_id, user_id))
    
    tx_data = cursor.fetchone()
    conn.close()
    
    if not tx_data:
        await message.reply("No transactions found.")
        return
    
    tx_id, amount, amount_received, coin, escrow_address, payment_tx_hash, status = tx_data
    
    # Debugging: Print values to console
    print(f"Debug - tx_id: {tx_id}, amount: {amount}, amount_received: {amount_received}, coin: {coin}")
    
    # Format status message
    if status == 'pending' and not payment_tx_hash:
        status_msg = (
            "⏳ **Transaction Status: Pending Payment**\n\n"
            f"**Transaction ID:** {tx_id}\n"
            f"**Amount:** {format_crypto_amount(amount, coin)} {coin}\n"
            f"**Escrow Address:** `{escrow_address}`\n\n"
            "Waiting for buyer to send funds to the escrow address."
        )
    elif status == 'pending' and payment_tx_hash:
        status_msg = (
            "⏳ **Transaction Status: Verifying Payment**\n\n"
            f"**Transaction ID:** {tx_id}\n"
            f"**Amount:** {format_crypto_amount(amount, coin)} {coin}\n"
            f"**Transaction Hash:** `{payment_tx_hash}`\n\n"
            "Payment detected but waiting for blockchain confirmations."
        )
    elif status == 'paid':
        status_msg = (
            "✅ **Transaction Status: Paid**\n\n"
            f"**Transaction ID:** {tx_id}\n"
            f"**Amount:** {format_crypto_amount(amount_received, coin)} {coin}\n"
            f"**Transaction Hash:** `{payment_tx_hash}`\n\n"
            "Funds are securely held in escrow. Seller can now fulfill their obligations."
        )
    else:
        status_msg = f"**Transaction Status:** {status}"
    
    await message.reply(status_msg, parse_mode="Markdown")

@dp.message(Command("support"))
async def cmd_support(message: types.Message):
    # Get user language
    lang = get_user_language(message.from_user.id)
    
    # Create the support message with HTML formatting
    support_message = await translate(
        "🤝 <b>Customer Support Assistance</b>\n\n"
        "• Need help with your escrow transaction?\n"
        "  Our dedicated support team is here to assist you every step of the way.\n\n"
        "• <b>Contact Us:</b>\n"
        "  @HoldEscrowSupport @HoldEscrowAdmin\n\n"
        "• To invite an admin to the escrow group, simply send /dispute.\n\n"
        "---\n\n"
        "<i>Available 24/7 to ensure a seamless transaction experience.</i>\n"
        "+ Fast, Secure, and Reliable Support",
        lang
    )
    
    # Send the message
    await message.reply(support_message, parse_mode="HTML")

@dp.message(Command("convert"))
async def cmd_convert(message: types.Message):
    # Check if command is used in a group
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ This command can only be used in group chats.")
        return

    # Parse command arguments
    args = message.text.split()
    
    # Validate command format
    if len(args) != 4:
        error_msg = (
            "❌ <b>INVALID FORMAT</b>\n\n"
            "<b>FORMAT:</b> /convert amount from_coin to_coin\n\n"
            "<b>EXAMPLES:</b>\n"
            "• /convert 0.00009 btc usdt\n"
            "• /convert 1000 usdt btc\n"
            "• /convert 0.00007 btc ltc\n\n"
            "<i>This command is only for obtaining an estimated exchange value of any cryptocurrency to any currency</i>"
        )
        await message.reply(error_msg, parse_mode="HTML")
        return

    # Extract and validate arguments
    try:
        amount = float(args[1])
        if amount <= 0:
            await message.reply("❌ Amount must be a positive number.")
            return
            
        from_coin = args[2].upper()
        to_coin = args[3].upper()
    except ValueError:
        await message.reply("❌ Invalid amount. Please provide a valid number.")
        return

    # Validate coin types
    supported_coins = ["BTC", "ETH", "LTC", "USDT", "USD"]
    if from_coin not in supported_coins:
        await message.reply(
            f"❌ Unsupported source coin: {from_coin}. Supported coins: {', '.join(supported_coins)}"
        )
        return
        
    if to_coin not in supported_coins:
        await message.reply(
            f"❌ Unsupported target coin: {to_coin}. Supported coins: {', '.join(supported_coins)}"
        )
        return

    # Show loading message
    loading_msg = await message.reply("⏳ Fetching current exchange rates...")

    # Try multiple APIs in order
    rate = None
    api_errors = []
    
    # Try Binance first (most reliable for crypto pairs)
    rate = await get_conversion_rate_binance(from_coin, to_coin)
    if rate is not None:
        api_used = "Binance"
    else:
        api_errors.append("Binance: Failed to fetch rate")
        # Try Coinbase
        rate = await get_conversion_rate_coinbase(from_coin, to_coin)
        if rate is not None:
            api_used = "Coinbase"
        else:
            api_errors.append("Coinbase: Failed to fetch rate")
            # Try Kraken
            rate = await get_conversion_rate_kraken(from_coin, to_coin)
            if rate is not None:
                api_used = "Kraken"
            else:
                api_errors.append("Kraken: Failed to fetch rate")
    
    if rate is None:
        # Fallback to hardcoded rates if APIs fail
        fallback_rates = {
            "BTC": {"USDT": 50000, "USD": 50000, "ETH": 15, "LTC": 5000},
            "ETH": {"BTC": 0.000066, "USDT": 3300, "USD": 3300, "LTC": 330},
            "LTC": {"BTC": 0.0002, "ETH": 0.003, "USDT": 100, "USD": 100},
            "USDT": {"BTC": 0.00002, "ETH": 0.0003, "LTC": 0.01, "USD": 1},
            "USD": {"BTC": 0.00002, "ETH": 0.0003, "LTC": 0.01, "USDT": 1}
        }
        
        if from_coin in fallback_rates and to_coin in fallback_rates[from_coin]:
            rate = fallback_rates[from_coin][to_coin]
            api_used = "Fallback Rates"
        else:
            error_details = "\n".join(api_errors)
            await loading_msg.edit_text(
                "❌ Could not fetch conversion rate from any available API.\n\n"
                f"Error details:\n{error_details}\n\n"
                "Please try again in a few moments."
            )
            return
        
    # Calculate converted amount
    converted_amount = amount * rate
    
    # Format the response
    response = await format_conversion_response(
        amount, from_coin, converted_amount, to_coin, rate, False, api_used
    )
    
    await loading_msg.edit_text(response, parse_mode="HTML")

# Updated Binance API function with proper USDT to BTC conversion
async def get_conversion_rate_binance(from_coin, to_coin):
    """Get conversion rate from Binance API with proper USDT handling"""
    try:
        # Handle direct pairs
        if from_coin == to_coin:
            return 1.0
            
        # Map USD to USDT for Binance
        if from_coin == "USD":
            from_coin = "USDT"
        if to_coin == "USD":
            to_coin = "USDT"
            
        # For USDT to BTC conversion, we need to use BTCUSDT pair and invert
        if from_coin == "USDT" and to_coin == "BTC":
            pair = "BTCUSDT"
            inverse = True
        elif to_coin == "USDT" and from_coin == "BTC":
            pair = "BTCUSDT"
            inverse = False
        else:
            # Try direct pair first
            pair = from_coin + to_coin
            inverse = False
            
            # Check if direct pair exists by trying to get its price
            test_price = await get_binance_rate(pair)
            if test_price is None:
                # Try inverse pair
                pair = to_coin + from_coin
                inverse = True
                test_price = await get_binance_rate(pair)
                if test_price is None:
                    # Use USDT as intermediary for non-direct pairs
                    rate1 = await get_conversion_rate_binance(from_coin, "USDT")
                    rate2 = await get_conversion_rate_binance("USDT", to_coin)
                    if rate1 is not None and rate2 is not None:
                        return rate1 * rate2
                    return None
        
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {'symbol': pair}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    price = data.get('price')
                    if price:
                        return 1 / float(price) if inverse else float(price)
                return None
    except Exception as e:
        print(f"Binance API error: {e}")
        return None

# Updated format function with proper decimal places
async def format_conversion_response(amount, from_coin, converted_amount, to_coin, rate, from_cache=False, api_used=None):
    """Format the conversion response message with proper decimal places"""
    # Format amounts based on coin type
    if from_coin in ["BTC", "LTC"]:
        from_amount_str = f"{amount:.8f}"
    else:
        from_amount_str = f"{amount:.2f}"
        
    if to_coin in ["BTC", "LTC"]:
        to_amount_str = f"{converted_amount:.8f}"
        rate_str = f"{rate:.8f}"
    elif to_coin in ["ETH"]:
        to_amount_str = f"{converted_amount:.6f}"
        rate_str = f"{rate:.6f}"
    else:
        to_amount_str = f"{converted_amount:.2f}"
        rate_str = f"{rate:.6f}"  # Show more decimals for rate
    
    # Create cache indicator and API source
    cache_indicator = " (cached)" if from_cache else ""
    api_source = f" via {api_used}" if api_used else ""
    
    return (
        f"🔄 <b>Currency Conversion{cache_indicator}{api_source}</b>\n\n"
        f"• <b>From:</b> {from_amount_str} {from_coin}\n"
        f"• <b>To:</b> {to_amount_str} {to_coin}\n"
        f"• <b>Rate:</b> 1 {from_coin} = {rate_str} {to_coin}\n\n"
        f"<i>Note: This is an estimated value. Actual rates may vary.</i>"
    )

@dp.message(Command("real"))
async def cmd_real(message: types.Message):
    # Check if command is used in a group
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ This command can only be used in group chats.")
        return

    # Get chat administrators
    try:
        admins = await bot.get_chat_administrators(message.chat.id)
        admin_usernames = [admin.user.username for admin in admins if admin.user.username]
        
        # Check if any admin is from the official support team
        official_admins = ["HoldEscrowAdmin", "HoldEscrowAdmin"]  # Add more if needed
        has_official_admin = any(admin in official_admins for admin in admin_usernames)
        
        if has_official_admin:
            response = (
                "✅ <b>Verification Successful!</b>\n\n"
                "The bot's admin @HoldEscrowAdmin is currently active in this group, "
                "which confirms that you are interacting with a legitimate admin.\n\n"
                "• Proceed only after double-checking all details.\n"
                "• Release funds only if all terms are met. If instructed by an admin, "
                "proceed confidently but stay cautious.\n\n"
                "Stay secure! 💬"
            )
        else:
            response = (
                "⚠️ <b>Admin Verification</b>\n\n"
                "No official admin was found in this group. Please be cautious and "
                "verify all details before proceeding with any transaction.\n\n"
                "Contact @HoldEscrowAdmin if you need assistance."
            )
            
        await message.reply(response, parse_mode="HTML")
        
    except Exception as e:
        print(f"Error checking admins: {e}")
        await message.reply(
            "❌ Could not verify admins. Please try again or contact support."
        )
# ========================
# /description COMMAND
# ========================
@dp.message(Command("description"))
async def cmd_description(message: types.Message):
    # Check if command is used in a group
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ This command can only be used in group chats.")
        return

    response = (
        "🤖 <b>@HoldEscrowBot Commands Guide</b>\n\n"
        "Set seller and buyer address first! Use:\n"
        "• <code>/seller [LTC/BTC/USDT(TRC20) Address]</code>\n"
        "• <code>/buyer [LTC/BTC/USDT(TRC20) Address]</code>\n\n"
        "<b>Other Available Commands:</b>\n"
        "• <code>/start</code> - Start the bot and see main menu\n"
        "• <code>/convert amount from_coin to_coin</code> - Convert between currencies\n"
        "• <code>/checkadmin</code> - Verify if official admin is in group\n"
        "• <code>/qr</code> - Show QR code for current escrow address\n"
        "• <code>/video</code> - Watch instructional video\n"
        "• <code>/balance</code> - Check transaction balance\n"
        "• <code>/dispute</code> - Invite admin to resolve issues\n"
        "• <code>/terms</code> - View terms of service\n"
        "• <code>/instructions</code> - See safety guidelines\n\n"
        "<i>Always verify addresses and transactions before proceeding.</i>"
    )
    
    await message.reply(response, parse_mode="HTML")
@dp.message(Command("video"))
async def cmd_video(message: types.Message):
    try:
        # Path to the video file
        video_path = os.path.join(BASE_DIR, "assets", "instructional_video.mp4")
        
        if not os.path.exists(video_path):
            # If the specific video doesn't exist, try to find any video file
            video_files = [f for f in os.listdir(os.path.join(BASE_DIR, "assets")) 
                          if f.endswith(('.mp4', '.mov', '.avi'))]
            
            if video_files:
                video_path = os.path.join(BASE_DIR, "assets", video_files[0])
            else:
                await message.reply("❌ No video file found in the assets folder.")
                return
        
        # Send the video
        video = FSInputFile(video_path)
        caption = (
            "📹 <b>Instructional Video</b>\n\n"
            "This video demonstrates how to use @HoldEscrowBot for secure escrow transactions.\n\n"
            "• Declare the seller or buyer using /seller or /buyer [BTC/LTC/USDT Address]\n"
            "• Follow the instructions carefully\n"
            "• Verify all details before proceeding\n\n"
            "Stay secure! 🔒"
        )
        
        await bot.send_video(
            chat_id=message.chat.id,
            video=video,
            caption=caption,
            parse_mode="HTML"
        )
        
    except Exception as e:
        print(f"Error sending video: {e}")
        await message.reply("❌ Could not send video. Please try again later.")

# ========================
# /qr COMMAND
# ========================
@dp.message(Command("qr"))
async def cmd_qr(message: types.Message):
    # Check if command is used in a group
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ This command can only be used in group chats.")
        return

    # Get the current group's escrow address from database
    conn = sqlite3.connect('escrow_bot.db')
    cursor = conn.cursor()
    
    try:
        # Get the latest transaction for this group
        cursor.execute('''
            SELECT escrow_address, coin FROM transactions 
            WHERE group_id = ? 
            ORDER BY created_at DESC LIMIT 1
        ''', (message.chat.id,))
        
        transaction = cursor.fetchone()
        
        if not transaction:
            await message.reply(
                "❌ No escrow address found for this group. "
                "Please set up a transaction first using /buyer and /seller commands."
            )
            return
            
        escrow_address, coin_type = transaction
        
        # Check if we have a pre-generated QR code for this address
        qr_code_path = os.path.join(BASE_DIR, "assets", "qr_codes", f"{escrow_address}.jpg")
        
        # Create qr_codes directory if it doesn't exist
        os.makedirs(os.path.dirname(qr_code_path), exist_ok=True)
        
        # Generate QR code if it doesn't exist
        if not os.path.exists(qr_code_path):
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(escrow_address)
            qr.make(fit=True)
            
            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img.save(qr_code_path)
        
        # Send the QR code
        qr_photo = FSInputFile(qr_code_path)
        caption = (
            f"📱 <b>QR Code for {coin_type} Deposit</b>\n\n"
            f"<b>Address:</b> <code>{escrow_address}</code>\n"
            f"<b>Coin Type:</b> {coin_type}\n\n"
            "Scan this QR code with your wallet app to send funds to the escrow address.\n\n"
            "<i>Always verify the address before sending funds.</i>"
        )
        
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=qr_photo,
            caption=caption,
            parse_mode="HTML"
        )
        
    except Exception as e:
        print(f"Error generating/sending QR code: {e}")
        await message.reply("❌ Could not generate QR code. Please try again later.")
        
    finally:
        conn.close()


# ========================
# /pay_seller COMMAND
# ========================
@dp.message(Command("pay_seller"))
async def cmd_pay_seller(message: types.Message):
    # Check if command is used in a group
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ This command can only be used in group chats.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Connect to database
    conn = sqlite3.connect("escrow_bot.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get the latest transaction for this group
        cursor.execute('''
            SELECT tx_id, buyer_id, seller_id, amount_received, coin, status 
            FROM transactions 
            WHERE group_id = ? 
            ORDER BY created_at DESC LIMIT 1
        ''', (chat_id,))
        
        transaction = cursor.fetchone()
        
        if not transaction:
            await message.reply("❌ No active transaction found for this group.")
            return
            
        tx_id, buyer_id, seller_id, amount, coin, status = transaction
        
        # Check if user is the buyer or an admin
        if user_id != buyer_id and user_id not in Config.ADMIN_IDS:
            await message.reply("❌ Only the buyer or an admin can release funds to the seller.")
            return
            
        # Check if transaction is in the right status
        if status != 'paid':
            await message.reply("❌ Funds can only be released after payment has been verified.")
            return
            
        # Update transaction status to released
        cursor.execute('''
            UPDATE transactions 
            SET status = 'released', released_at = ?
            WHERE tx_id = ?
        ''', (int(time.time()), tx_id))
        conn.commit()
        
        # Format amount
        amount_formatted = format_crypto_amount(amount, coin)
        
        # Create success message
        success_message = (
            "✅ <b>FUNDS RELEASED TO SELLER</b>\n\n"
            f"<b>Transaction ID:</b> {tx_id}\n"
            f"<b>Amount:</b> {amount_formatted} {coin}\n"
            f"<b>Released by:</b> @{message.from_user.username or message.from_user.first_name}\n\n"
            "The seller has received the funds and the transaction is now complete.\n\n"
            "Thank you for using HoldEscrowBot! 🚀"
        )
        
        await message.reply(success_message, parse_mode="HTML")
        
        # Send transaction summary to vouch channel
        transaction_data = {
            'tx_id': tx_id,
            'buyer_id': buyer_id,
            'seller_id': seller_id,
            'amount_received': amount,
            'coin': coin,
            'status': 'completed'
        }
        await send_transaction_to_vouch_channel(transaction_data)
        
        # Notify seller
        try:
            seller_notification = (
                "💰 <b>FUNDS RELEASED</b>\n\n"
                f"The buyer has released {amount_formatted} {coin} to you.\n"
                f"<b>Transaction ID:</b> {tx_id}\n\n"
                "The transaction is now complete. Thank you for using HoldEscrowAdmin! 🚀"
            )
            await bot.send_message(seller_id, seller_notification, parse_mode="HTML")
        except Exception as e:
            print(f"Could not notify seller: {e}")
            
    except Exception as e:
        print(f"Error in pay_seller command: {e}")
        await message.reply("❌ An error occurred while processing your request.")
    finally:
        conn.close()

async def send_transaction_to_vouch_channel(transaction_data: dict):
    """Send transaction summary to the vouch channel"""
    try:
        tx_id = transaction_data['tx_id']
        buyer_id = transaction_data['buyer_id']
        seller_id = transaction_data['seller_id']
        amount = transaction_data['amount_received']
        coin_type = transaction_data['coin']
        status = transaction_data['status']
        
        # Get user information
        try:
            buyer = await bot.get_chat(buyer_id)
            buyer_username = f"@{buyer.username}" if buyer.username else buyer.first_name
        except:
            buyer_username = "Unknown"
            
        try:
            seller = await bot.get_chat(seller_id)
            seller_username = f"@{seller.username}" if seller.username else seller.first_name
        except:
            seller_username = "Unknown"
        
        # Format amount based on coin type
        if coin_type in ["BTC", "LTC"]:
            amount_str = f"{amount:.8f}"
        elif coin_type == "ETH":
            amount_str = f"{amount:.6f}"
        else:
            amount_str = f"{amount:.2f}"
        
        # Create beautiful transaction summary for the channel
        vouch_message = (
            "🎉 <b>SUCCESSFUL TRANSACTION COMPLETED</b> 🎉\n\n"
            "┌──────────────────────────────┐\n"
            "│ 📋 <b>TRANSACTION DETAILS</b>           │\n"
            "├──────────────────────────────┤\n"
            f"│ <b>ID:</b> <code>{tx_id}</code> │\n"
            f"│ <b>Amount:</b> {amount_str} {coin_type}        │\n"
            f"│ <b>Status:</b> {status.capitalize()}           │\n"
            "└──────────────────────────────┘\n\n"
            "👤 <b>BUYER</b>\n"
            f"• {buyer_username} (<code>{buyer_id}</code>)\n\n"
            "🛒 <b>SELLER</b>\n"
            f"• {seller_username} (<code>{seller_id}</code>)\n\n"
            "⏰ <b>COMPLETED AT</b>\n"
            f"• {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "💫 <i>Another successful trade secured by</i> <b>@HoldEscrowBot</b> 💫\n\n"
            "⭐ <b>Leave feedback for your trading partner!</b>"
        )
        
        # Send to vouch channel
        if Config.VOUCH_CHANNEL_ID:
            await bot.send_message(
                chat_id=Config.VOUCH_CHANNEL_ID,
                text=vouch_message,
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=Config.VOUCH_CHANNEL,
                text=vouch_message,
                parse_mode="HTML"
            )
            
        print(f"✅ Transaction {tx_id} summary sent to vouch channel")
        
    except Exception as e:
        print(f"❌ Error sending transaction to vouch channel: {e}")


# ========================
# /refund_buyer COMMAND
# ========================
@dp.message(Command("refund_buyer"))
async def cmd_refund_buyer(message: types.Message):
    # Check if command is used in a group
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ This command can only be used in group chats.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Connect to database
    conn = sqlite3.connect("escrow_bot.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get the latest transaction for this group
        cursor.execute('''
            SELECT tx_id, buyer_id, seller_id, amount_received, coin, status 
            FROM transactions 
            WHERE group_id = ? 
            ORDER BY created_at DESC LIMIT 1
        ''', (chat_id,))
        
        transaction = cursor.fetchone()
        
        if not transaction:
            await message.reply("❌ No active transaction found for this group.")
            return
            
        tx_id, buyer_id, seller_id, amount, coin, status = transaction
        
        # Check if user is the seller or an admin
        if user_id != seller_id and user_id not in Config.ADMIN_IDS:
            await message.reply("❌ Only the seller or an admin can refund funds to the buyer.")
            return
            
        # Check if transaction is in the right status
        if status != 'paid':
            await message.reply("❌ Funds can only be refunded after payment has been verified.")
            return
            
        # Update transaction status to refunded
        cursor.execute('''
            UPDATE transactions 
            SET status = 'refunded', refunded_at = ?
            WHERE tx_id = ?
        ''', (int(time.time()), tx_id))
        conn.commit()
        
        # Format amount
        amount_formatted = format_crypto_amount(amount, coin)
        
        # Create success message
        success_message = (
            "✅ <b>FUNDS REFUNDED TO BUYER</b>\n\n"
            f"<b>Transaction ID:</b> {tx_id}\n"
            f"<b>Amount:</b> {amount_formatted} {coin}\n"
            f"<b>Refunded by:</b> @{message.from_user.username or message.from_user.first_name}\n\n"
            "The buyer has received a refund and the transaction is now closed.\n\n"
            "Thank you for using HoldEscrowBot! 🚀"
        )
        
        await message.reply(success_message, parse_mode="HTML")
        
        # Send transaction summary to vouch channel (with refund status)
        transaction_data = {
            'tx_id': tx_id,
            'buyer_id': buyer_id,
            'seller_id': seller_id,
            'amount_received': amount,
            'coin': coin,
            'status': 'refunded'
        }
        await send_transaction_to_vouch_channel(transaction_data)
        
        # Notify buyer
        try:
            buyer_notification = (
                "💰 <b>REFUND PROCESSED</b>\n\n"
                f"You have received a refund of {amount_formatted} {coin}.\n"
                f"<b>Transaction ID:</b> {tx_id}\n\n"
                "The transaction is now closed. Thank you for using @HoldEscrowBot! 🚀"
            )
            await bot.send_message(buyer_id, buyer_notification, parse_mode="HTML")
        except Exception as e:
            print(f"Could not notify buyer: {e}")
            
    except Exception as e:
        print(f"Error in refund_buyer command: {e}")
        await message.reply("❌ An error occurred while processing your request.")
    finally:
        conn.close()


# ========================
# /dispute COMMAND
# ========================
@dp.message(Command("dispute"))
async def cmd_dispute(message: types.Message):
    # Check if command is used in a group
    if message.chat.type not in ["group", "supergroup"]:
        await message.reply("❌ This command can only be used in group chats.")
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Connect to database
    conn = sqlite3.connect("escrow_bot.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get the latest transaction for this group
        cursor.execute('''
            SELECT tx_id, buyer_id, seller_id, amount_received, coin, status 
            FROM transactions 
            WHERE group_id = ? 
            ORDER BY created_at DESC LIMIT 1
        ''', (chat_id,))
        
        transaction = cursor.fetchone()
        
        if not transaction:
            await message.reply("❌ No active transaction found for this group.")
            return
            
        tx_id, buyer_id, seller_id, amount, coin, status = transaction
        
        # Check if user is part of the transaction
        if user_id not in [buyer_id, seller_id]:
            await message.reply("❌ Only the buyer or seller can open a dispute for this transaction.")
            return
            
        # Check if transaction is in a disputable status
        if status not in ['paid', 'pending']:
            await message.reply("❌ A dispute can only be opened for active transactions.")
            return
            
        # Check if there's already an open dispute
        cursor.execute('SELECT id FROM disputes WHERE transaction_id = ? AND status = "open"', (tx_id,))
        existing_dispute = cursor.fetchone()
        
        if existing_dispute:
            await message.reply("❌ There is already an open dispute for this transaction.")
            return
            
        # Create dispute record
        cursor.execute('''
            INSERT INTO disputes (transaction_id, user_id, reason, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (tx_id, user_id, "Dispute opened via command", "open", int(time.time())))
        conn.commit()
        
        # Update transaction status to disputed
        cursor.execute('''
            UPDATE transactions 
            SET status = 'disputed', dispute_opened = 1
            WHERE tx_id = ?
        ''', (tx_id,))
        conn.commit()
        
        # Format amount
        amount_formatted = format_crypto_amount(amount, coin) if amount else "Unknown"
        
        # Create dispute message
        dispute_message = (
            "⚖️ <b>DISPUTE OPENED</b>\n\n"
            f"<b>Transaction ID:</b> {tx_id}\n"
            f"<b>Amount:</b> {amount_formatted} {coin}\n"
            f"<b>Opened by:</b> @{message.from_user.username or message.from_user.first_name}\n\n"
            "An admin has been notified and will review this dispute shortly.\n\n"
            "Please provide any relevant details about the issue in this chat.\n\n"
            "<i>The transaction is now frozen until the dispute is resolved.</i>"
        )
        
        await message.reply(dispute_message, parse_mode="HTML")
        
        # Notify the other party
        other_party_id = seller_id if user_id == buyer_id else buyer_id
        try:
            other_party_notification = (
                "⚖️ <b>DISPUTE OPENED</b>\n\n"
                f"A dispute has been opened for transaction {tx_id}.\n"
                "An admin will review the case shortly.\n\n"
                "Please wait for further instructions."
            )
            await bot.send_message(other_party_id, other_party_notification, parse_mode="HTML")
        except Exception as e:
            print(f"Could not notify other party: {e}")
            
        # Notify admins
        for admin_id in Config.ADMIN_IDS:
            try:
                admin_notification = (
                    "⚖️ <b>NEW DISPUTE</b>\n\n"
                    f"<b>Transaction ID:</b> {tx_id}\n"
                    f"<b>Group ID:</b> {chat_id}\n"
                    f"<b>Amount:</b> {amount_formatted} {coin}\n"
                    f"<b>Opened by:</b> @{message.from_user.username or message.from_user.first_name}\n\n"
                    f"<b>Buyer:</b> {buyer_id}\n"
                    f"<b>Seller:</b> {seller_id}\n\n"
                    "Please review this dispute as soon as possible."
                )
                await bot.send_message(admin_id, admin_notification, parse_mode="HTML")
            except Exception as e:
                print(f"Could not notify admin {admin_id}: {e}")
                
    except Exception as e:
        print(f"Error in dispute command: {e}")
        await message.reply("❌ An error occurred while processing your request.")
    finally:
        conn.close()


# ========================
# HELPER FUNCTION
# ========================
def format_crypto_amount(amount, coin_type):
    """Format amount based on coin type"""
    if amount is None:
        return "Unknown"
    
    decimals = {
        'BTC': 8,
        'ETH': 6,
        'USDT': 2,
        'LTC': 8
    }
    
    decimal_places = decimals.get(coin_type, 8)
    
    try:
        return f"{float(amount):,.{decimal_places}f}"
    except (ValueError, TypeError):
        return "Unknown"


# ========================
# REFERRAL SYSTEM
# ========================
@dp.message(Command("referral"))
async def cmd_referral(message: types.Message):
    """Show user's referral information and stats"""
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    
    # Get user data
    conn = sqlite3.connect('escrow_bot.db')
    cursor = conn.cursor()
    
    # Get user's referral code and stats
    cursor.execute('''
        SELECT us.referral_code, 
               COUNT(r.referral_code) as referral_count,
               COALESCE(SUM(r.reward_amount), 0) as total_rewards
        FROM user_settings us
        LEFT JOIN referrals r ON us.referral_code = r.referral_code
        WHERE us.user_id = ?
        GROUP BY us.referral_code
    ''', (user_id,))
    
    user_data = cursor.fetchone()
    
    if not user_data or not user_data[0]:
        # Generate referral code if user doesn't have one
        referral_code = generate_referral_code()
        cursor.execute('''
            INSERT OR REPLACE INTO user_settings (user_id, referral_code)
            VALUES (?, ?)
        ''', (user_id, referral_code))
        conn.commit()
        
        # Get updated data
        cursor.execute('''
            SELECT us.referral_code, 
                   COUNT(r.referral_code) as referral_count,
                   COALESCE(SUM(r.reward_amount), 0) as total_rewards
            FROM user_settings us
            LEFT JOIN referrals r ON us.referral_code = r.referral_code
            WHERE us.user_id = ?
            GROUP BY us.referral_code
        ''', (user_id,))
        user_data = cursor.fetchone()
    
    referral_code, referral_count, total_rewards = user_data
    
    # Get pending rewards (from users who signed up but haven't completed transactions yet)
    cursor.execute('''
        SELECT COUNT(*) 
        FROM user_settings 
        WHERE referred_by = ? AND user_id NOT IN (
            SELECT DISTINCT buyer_id FROM transactions WHERE status = 'released'
            UNION 
            SELECT DISTINCT seller_id FROM transactions WHERE status = 'released'
        )
    ''', (referral_code,))
    
    pending_referrals = cursor.fetchone()[0]
    
    # Format rewards based on language
    if lang != 'en':
        total_rewards_text = await translate(f"{total_rewards:.8f} BTC", lang)
    else:
        total_rewards_text = f"{total_rewards:.8f} BTC"
    
    # Create referral message
    referral_msg = await translate(
        f"🎯 <b>Your Referral Program</b>\n\n"
        f"🔗 <b>Your Referral Code:</b> <code>{referral_code}</code>\n\n"
        f"📊 <b>Statistics:</b>\n"
        f"• Successful referrals: <b>{referral_count}</b>\n"
        f"• Pending referrals: <b>{pending_referrals}</b>\n"
        f"• Total rewards earned: <b>{total_rewards_text}</b>\n\n"
        f"💰 <b>Reward System:</b>\n"
        f"• Earn {Config.REFERRAL_REWARD:.8f} BTC for each friend who completes a transaction\n"
        f"• Rewards are paid automatically after their first successful escrow\n\n"
        f"📣 <b>How to share:</b>\n"
        f"Share your referral link: https://t.me/{BOT_USERNAME}?start={referral_code}\n\n"
        f"💡 <b>Pro Tip:</b> The more friends you refer, the more you earn!",
        lang
    )
    
    # Create keyboard with sharing options
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📤 Share Referral Link", 
            url=f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={referral_code}&text=Join%20me%20on%20@HoldEscrowBot%20Escrow%20for%20secure%20crypto%20transactions!"
        )],
        [InlineKeyboardButton(
            text="📊 Referral Leaderboard", 
            callback_data="referral_leaderboard"
        )],
        [InlineKeyboardButton(
            text="💼 Withdraw Earnings", 
            callback_data="withdraw_referral"
        )]
    ])
    
    await message.reply(referral_msg, parse_mode="HTML", reply_markup=keyboard)
    conn.close()

@dp.callback_query(lambda c: c.data == "referral_leaderboard")
async def referral_leaderboard(callback_query: types.CallbackQuery):
    """Show top referrers"""
    user_id = callback_query.from_user.id
    lang = get_user_language(user_id)
    
    conn = sqlite3.connect('escrow_bot.db')
    cursor = conn.cursor()
    
    # Get top 10 referrers
    cursor.execute('''
        SELECT us.user_id, us.referral_code, 
               COUNT(r.referral_code) as referral_count,
               COALESCE(SUM(r.reward_amount), 0) as total_rewards
        FROM user_settings us
        LEFT JOIN referrals r ON us.referral_code = r.referral_code
        GROUP BY us.user_id, us.referral_code
        HAVING referral_count > 0
        ORDER BY total_rewards DESC
        LIMIT 10
    ''')
    
    top_referrers = cursor.fetchall()
    
    leaderboard_msg = await translate("🏆 <b>Top Referrers Leaderboard</b>\n\n", lang)
    
    if not top_referrers:
        leaderboard_msg += await translate("No referrals yet. Be the first to refer friends!", lang)
    else:
        for i, (ref_user_id, ref_code, count, rewards) in enumerate(top_referrers, 1):
            try:
                user = await bot.get_chat(ref_user_id)
                username = f"@{user.username}" if user.username else user.first_name
            except:
                username = "Unknown User"
                
            leaderboard_msg += f"{i}. {username}: {count} referrals, {rewards:.8f} BTC\n"
    
    leaderboard_msg += await translate(
        "\n💡 <b>Tip:</b> Refer more friends to climb the leaderboard!",
        lang
    )
    
    await callback_query.message.edit_text(leaderboard_msg, parse_mode="HTML")
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "withdraw_referral")
async def withdraw_referral_earnings(callback_query: types.CallbackQuery):
    """Handle referral earnings withdrawal"""
    user_id = callback_query.from_user.id
    lang = get_user_language(user_id)
    
    conn = sqlite3.connect('escrow_bot.db')
    cursor = conn.cursor()
    
    # Get user's total rewards
    cursor.execute('''
        SELECT COALESCE(SUM(r.reward_amount), 0) as total_rewards
        FROM user_settings us
        LEFT JOIN referrals r ON us.referral_code = r.referral_code
        WHERE us.user_id = ?
    ''', (user_id,))
    
    total_rewards = cursor.fetchone()[0]
    
    if total_rewards <= 0:
        await callback_query.answer(
            await translate("You don't have any rewards to withdraw yet.", lang),
            show_alert=True
        )
        return
    
    # Check minimum withdrawal amount (0.0005 BTC)
    if total_rewards < 0.0005:
        await callback_query.answer(
            await translate(f"Minimum withdrawal is 0.0005 BTC. You have {total_rewards:.8f} BTC.", lang),
            show_alert=True
        )
        return
    
    # Ask for withdrawal address
    withdrawal_msg = await translate(
        f"💳 <b>Withdraw Referral Earnings</b>\n\n"
        f"Your available balance: <b>{total_rewards:.8f} BTC</b>\n\n"
        f"Please send your Bitcoin address for withdrawal:",
        lang
    )
    
    await callback_query.message.edit_text(withdrawal_msg, parse_mode="HTML")
    
    # Set state to wait for withdrawal address
    from aiogram.fsm.state import State, StatesGroup
    
    class WithdrawalStates(StatesGroup):
        waiting_for_address = State()
    
    # You'll need to implement state management
    # For now, we'll just prompt the user to message their address
    await callback_query.answer()
    
    # In a real implementation, you would:
    # 1. Set a state to wait for the address
    # 2. Process the address when received
    # 3. Initiate the withdrawal
    # 4. Update the database to mark rewards as paid


# ========================
# STARTUP AND MAIN
# ========================
async def on_startup(dp):
    print("Bot started")
    # Initialize the Telethon client
    await group_manager.initialize()
      # Start deposit monitoring
    asyncio.create_task(deposit_monitor.start_monitoring())

    # Set bot description (persistent static message)
    try:
        # Attempt to set bot description and notify admins
        bot_description = (
            "🤖 HoldEscrowBot\n\n"
            "🟢 CHAT @CoinHoldVerify\n"
            "📢 UPDATES @CoinHoldEscrow\n"
            "⭐ VOUCHES @CoinHoldVouches\n\n"
            "💵 5$ Flat Fee For Transaction Under 100$\n"
            "📊 5% Fee For Transaction Over 100$"
        )
        
        await bot.set_my_description(description=bot_description)
        print("✅ Bot description set successfully")
    except Exception as e:
        print(f"❌ Error setting bot description: {e}")


    for admin_id in Config.ADMIN_IDS:
        try:
            # Check if we can send a message to this admin first
            await bot.send_chat_action(admin_id, "typing")
            await send_banner(
                admin_id,
                "admin",
                "🟢 Escrow Bot is now online\n\n"
                "Admin commands available:\n"
                "/verify [tx_id] [tx_hash]\n"
                "/release [tx_id]\n"
                "/admin - View dashboard\n"
                "/admin_stats - Detailed statistics"
            )
        except Exception as e:
            print(f"Could not send startup message to admin {admin_id}: {e}")


if __name__ == '__main__':
    required_vars = [
        "BOT_TOKEN", "ADMIN_IDS",
        "BTC_WALLETS", "ETH_WALLETS",
        "USDT_WALLETS", "LTC_WALLETS",
        "TELEGRAM_API_ID", "TELEGRAM_API_HASH"
    ]

    for var in required_vars:
        if not os.getenv(var):
            raise ValueError(f"Missing required environment variable: {var}")

    print("✅ Configuration validated")
    print(f"• Supported coins: {', '.join(Config.WALLETS.keys())}")
    print(f"• Admin IDs: {', '.join(map(str, Config.ADMIN_IDS))}")
    print(f"• Minimum BTC deposit: {MIN_BTC_DEPOSIT}")
    print(f"• Supported languages: {', '.join(SUPPORTED_LANGUAGES.values())}")


    async def main():
        await on_startup(dp)
        await dp.start_polling(bot, skip_updates=True)

    asyncio.run(main())