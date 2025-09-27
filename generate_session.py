import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

async def generate_session_string():
    """Generate a Telethon session string for cloud deployment"""
    api_id = int(os.getenv("TELEGRAM_API_ID"))
    api_hash = os.getenv("TELEGRAM_API_HASH")
    
    if not api_id or not api_hash:
        print("❌ Please set TELEGRAM_API_ID and TELEGRAM_API_HASH in your .env file")
        return
    
    print("🔑 Generating Telethon session string...")
    print("📱 You'll need to authorize this session with your phone number")
    
    async with TelegramClient(StringSession(), api_id, api_hash) as client:
        await client.start()
        session_string = client.session.save()
        
        print("\n✅ Session generated successfully!")
        print("="*50)
        print("COPY THIS SESSION STRING AND ADD IT TO YOUR ENVIRONMENT VARIABLES:")
        print("="*50)
        print(session_string)
        print("="*50)
        print("\n📝 Add this to your Render environment variables as: TELETHON_SESSION_STRING")

if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_session_string())