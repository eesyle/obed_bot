#!/usr/bin/env python3
"""
Script to create a Telethon session file from a session string
This will help convert from session string to session file approach
Matches the exact configuration expected by app.py
"""

import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession, SQLiteSession
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def create_session_file():
    """Create a session file from the existing session string"""
    try:
        # Get credentials from environment (same as app.py)
        api_id = int(os.getenv("TELEGRAM_API_ID", "0"))
        api_hash = os.getenv("TELEGRAM_API_HASH", "")
        session_string = os.getenv("TELETHON_SESSION_STRING", "")
        
        # Get the session name that app.py expects
        session_name = os.getenv("TELEGRAM_SESSION", "escrow_bot")
        
        if not all([api_id, api_hash, session_string]):
            print("❌ Missing required environment variables")
            print("Required: TELEGRAM_API_ID, TELEGRAM_API_HASH, TELETHON_SESSION_STRING")
            return False
        
        print(f"📱 API ID: {api_id}")
        print(f"🔑 API Hash: {api_hash[:10]}...")
        print(f"📝 Session String Length: {len(session_string)} characters")
        print(f"📁 Target session file: {session_name}.session")
        
        # Create client with session string to verify it works
        print("\n🔄 Verifying session string...")
        string_session = StringSession(session_string)
        temp_client = TelegramClient(string_session, api_id, api_hash)
        
        # Connect and verify
        await temp_client.connect()
        
        if not await temp_client.is_user_authorized():
            print("❌ Session string is not authorized")
            await temp_client.disconnect()
            return False
        
        print("✅ Session string is valid and authorized")
        
        # Get user info
        me = await temp_client.get_me()
        print(f"👤 Logged in as: {me.first_name} (@{me.username})")
        
        # Disconnect
        await temp_client.disconnect()
        
        # Now create a session file directly with the correct name
        print(f"\n🔄 Creating session file: {session_name}.session...")
        
        # Remove existing session file if it exists
        session_file_path = f"{session_name}.session"
        if os.path.exists(session_file_path):
            os.remove(session_file_path)
            print(f"🗑️ Removed existing session file: {session_file_path}")
        
        # Create SQLite session with the correct name
        sqlite_session = SQLiteSession(session_name)
        
        # Copy session data from string session to SQLite session
        try:
            print(f"🔍 String session DC ID: {string_session.dc_id}")
            print(f"🔍 String session server: {string_session.server_address}:{string_session.port}")
            print(f"🔍 Auth key length: {len(string_session.auth_key.key) if string_session.auth_key else 'None'}")
            
            sqlite_session.set_dc(
                string_session.dc_id,
                string_session.server_address,
                string_session.port
            )
            sqlite_session.auth_key = string_session.auth_key
            sqlite_session.save()
            print("✅ Session data copied to SQLite session")
            
            # Force close the session to ensure it's written to disk
            sqlite_session.close()
            print("💾 Session file closed and saved to disk")
            
        except Exception as e:
            print(f"❌ Error copying session data: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test the session file by creating a new client
        print("🔄 Testing session file...")
        file_client = TelegramClient(session_name, api_id, api_hash)
        
        try:
            await file_client.connect()
            
            if await file_client.is_user_authorized():
                me = await file_client.get_me()
                print(f"✅ Session file created successfully!")
                print(f"👤 Session file user: {me.first_name} (@{me.username})")
                print(f"📁 Session file: {session_name}.session")
                
                # Verify the file exists
                if os.path.exists(f"{session_name}.session"):
                    file_size = os.path.getsize(f"{session_name}.session")
                    print(f"📊 Session file size: {file_size} bytes")
                else:
                    print("⚠️ Warning: Session file not found on disk")
                    
            else:
                print("❌ Session file is not authorized")
                await file_client.disconnect()
                return False
            
            await file_client.disconnect()
            
        except Exception as e:
            print(f"❌ Error testing session file: {e}")
            try:
                await file_client.disconnect()
            except:
                pass
            return False
        
        print("\n🎉 Session file created successfully!")
        print(f"📁 Created: {session_name}.session")
        print("📝 You can now remove TELETHON_SESSION_STRING from your .env file")
        print("🔧 The bot will now use the session file instead")
        print(f"🔄 App.py is configured to use: {session_name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating session file: {e}")
        import traceback
        traceback.print_exc()
        return False

def cleanup_old_session_files():
    """Clean up old session files that might conflict"""
    old_files = [
        "telegram_session.session",
        "escrow_session.session", 
        "bot_session.session"
    ]
    
    cleaned = []
    for file in old_files:
        if os.path.exists(file):
            try:
                os.remove(file)
                cleaned.append(file)
            except Exception as e:
                print(f"⚠️ Could not remove {file}: {e}")
    
    if cleaned:
        print(f"🧹 Cleaned up old session files: {', '.join(cleaned)}")
    
    return cleaned

def verify_environment():
    """Verify all required environment variables are present"""
    required_vars = [
        "TELEGRAM_API_ID",
        "TELEGRAM_API_HASH", 
        "TELETHON_SESSION_STRING"
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("📝 Please check your .env file")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Creating Telethon session file from session string...")
    print("=" * 60)
    
    # Verify environment first
    if not verify_environment():
        print("\n❌ Environment verification failed!")
        exit(1)
    
    # Clean up old session files
    cleanup_old_session_files()
    
    try:
        success = asyncio.run(create_session_file())
        
        if success:
            print("\n" + "=" * 60)
            print("✅ Session file creation completed successfully!")
            print("🎯 Your bot is now ready to use session files!")
        else:
            print("\n" + "=" * 60)
            print("❌ Session file creation failed!")
            print("🔧 Please check the error messages above")
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()