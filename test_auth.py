import os
import asyncio 
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TELEGRAM_API_ID = "22246371"
TELEGRAM_API_HASH = "7e355e26f32fa592fa0a2970af7dbef8"
TELETHON_SESSION_STRING = os.getenv("TELETHON_SESSION_STRING", "")

async def auth():
    # Use StringSession for deployment compatibility
    session = StringSession(TELETHON_SESSION_STRING) if TELETHON_SESSION_STRING else StringSession()
    client = TelegramClient(session, TELEGRAM_API_ID, TELEGRAM_API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            phone = input("Enter your phone number (e.g., +1234567890): ")
            await client.send_code_request(phone)
            code = input("Enter the code you received: ")
            try:
                await client.sign_in(phone=phone, code=code)
            except SessionPasswordNeededError:
                password = input("Enter 2FA password: ")
                await client.sign_in(password=password)
            logger.info("Session created successfully")
            logger.info(f"Session string: {client.session.save()}")
        else:
            logger.info("Session already authorized")
            logger.info(f"Current session string: {client.session.save()}")
        await client.disconnect()
    except Exception as e:
        logger.error("Failed to create session: %s", str(e))

if __name__ == "__main__":
    asyncio.run(auth())