#!/usr/bin/env python3
import os
import sys
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

async def main():
    print("🔧 HoldEscrowBot Telethon Setup")
    print("=" * 50)
    
    # Check environment variables
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    
    if not api_id or not api_hash:
        print("❌ Missing API credentials!")
        print("Please set these environment variables:")
        print("TELEGRAM_API_ID=your_api_id")
        print("TELEGRAM_API_HASH=your_api_hash")
        return
    
    print("✅ API credentials found")
    print(f"API ID: {api_id}")
    print(f"API Hash: {api_hash[:10]}...")
    print()
    
    try:
        # Create client with StringSession
        client = TelegramClient(StringSession(), int(api_id), api_hash)
        
        print("🔑 Starting authentication...")
        await client.start()
        
        # Get the session string
        session_string = client.session.save()
        
        print("✅ Session generated successfully!")
        print()
        print("=" * 50)
        print("IMPORTANT: Copy this session string exactly:")
        print("=" * 50)
        print(session_string)
        print("=" * 50)
        print()
        
        # Verify the session string length
        print(f"Session string length: {len(session_string)} characters")
        
        if len(session_string) < 200:
            print("❌ WARNING: Session string seems too short!")
        else:
            print("✅ Session string length looks good!")
        
        print()
        print("📝 Add this to your Render environment variables as:")
        print("TELETHON_SESSION_STRING=the_string_above")
        
        # Test the session
        print()
        print("🧪 Testing session...")
        me = await client.get_me()
        print(f"✅ Logged in as: {me.first_name} (@{me.username})")
        
        await client.disconnect()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Troubleshooting tips:")
        print("1. Make sure your API credentials are correct")
        print("2. Ensure you have a stable internet connection")
        print("3. Try using a different phone number if needed")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())