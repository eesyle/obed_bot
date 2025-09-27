#!/usr/bin/env python3
"""
Telethon Session Creator - Phone Number Authentication
Creates a session file using phone number and verification code.
"""

import os
import sys
import asyncio
import re
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneNumberInvalidError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def print_banner():
    """Print a nice banner for the session creator"""
    print("\n" + "="*60)
    print("🚀 Telethon Session Creator - Phone Authentication")
    print("="*60)

def validate_phone_number(phone):
    """
    Validate phone number format
    Should be in international format: +1234567890
    """
    # Remove any spaces, dashes, or parentheses
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Check if it starts with + and has 10-15 digits
    if re.match(r'^\+\d{10,15}$', cleaned):
        return cleaned
    
    # If it doesn't start with +, try to add it
    if re.match(r'^\d{10,15}$', cleaned):
        return '+' + cleaned
    
    return None

def verify_environment():
    """Verify that required environment variables are set"""
    required_vars = ['TELEGRAM_API_ID', 'TELEGRAM_API_HASH']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("📝 Please set them in your .env file")
        return False
    
    return True

def cleanup_old_session_files():
    """Remove any existing session files that might conflict"""
    session_files = [
        'telegram_session.session',
        'escrow_session.session', 
        'bot_session.session',
        'escrow_bot.session'
    ]
    
    removed_files = []
    for session_file in session_files:
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
                removed_files.append(session_file)
            except Exception as e:
                print(f"⚠️  Warning: Could not remove {session_file}: {e}")
    
    if removed_files:
        print(f"🧹 Cleaned up old session files: {', '.join(removed_files)}")

async def create_session_with_phone():
    """
    Create a Telethon session using phone number authentication
    """
    try:
        # Get environment variables
        api_id = os.getenv('TELEGRAM_API_ID')
        api_hash = os.getenv('TELEGRAM_API_HASH')
        session_name = os.getenv('TELEGRAM_SESSION', 'escrow_bot')
        
        print(f"📱 API ID: {api_id}")
        print(f"🔑 API Hash: {api_hash[:10]}...")
        print(f"📁 Target session file: {session_name}.session")
        print()
        
        # Get phone number from user
        while True:
            phone = input("📞 Enter your phone number (with country code, e.g., +1234567890): ").strip()
            
            if not phone:
                print("❌ Phone number cannot be empty!")
                continue
                
            validated_phone = validate_phone_number(phone)
            if validated_phone:
                phone = validated_phone
                print(f"✅ Using phone number: {phone}")
                break
            else:
                print("❌ Invalid phone number format!")
                print("💡 Please use international format: +1234567890")
                continue
        
        print(f"\n🔄 Creating session for {phone}...")
        
        # Create the Telegram client
        client = TelegramClient(session_name, api_id, api_hash)
        
        # Connect to Telegram
        await client.connect()
        
        # Check if we're already authorized
        if await client.is_user_authorized():
            print("✅ Already authorized! Session file exists and is valid.")
            me = await client.get_me()
            print(f"👤 Logged in as: {me.first_name} {me.last_name or ''} (@{me.username or 'no_username'})")
        else:
            # Send code request
            print("📤 Sending verification code...")
            await client.send_code_request(phone)
            
            # Get verification code from user
            while True:
                try:
                    code = input("🔢 Enter the verification code you received: ").strip()
                    
                    if not code:
                        print("❌ Verification code cannot be empty!")
                        continue
                    
                    # Sign in with the code
                    await client.sign_in(phone, code)
                    break
                    
                except PhoneCodeInvalidError:
                    print("❌ Invalid verification code! Please try again.")
                    continue
                except SessionPasswordNeededError:
                    # Two-factor authentication is enabled
                    print("🔐 Two-factor authentication detected!")
                    while True:
                        password = input("🔑 Enter your 2FA password: ").strip()
                        
                        if not password:
                            print("❌ Password cannot be empty!")
                            continue
                        
                        try:
                            await client.sign_in(password=password)
                            break
                        except Exception as e:
                            print(f"❌ Invalid password: {e}")
                            continue
                    break
                except Exception as e:
                    print(f"❌ Error during sign in: {e}")
                    return False
            
            # Get user info
            me = await client.get_me()
            print(f"✅ Successfully logged in as: {me.first_name} {me.last_name or ''} (@{me.username or 'no_username'})")
        
        # Disconnect the client
        await client.disconnect()
        
        # Verify the session file was created
        session_file_path = f"{session_name}.session"
        if os.path.exists(session_file_path):
            file_size = os.path.getsize(session_file_path)
            print(f"✅ Session file created successfully!")
            print(f"📁 File: {session_file_path}")
            print(f"📊 Size: {file_size} bytes")
            
            # Test the session file
            print(f"\n🧪 Testing session file...")
            test_client = TelegramClient(session_name, api_id, api_hash)
            await test_client.connect()
            
            if await test_client.is_user_authorized():
                test_me = await test_client.get_me()
                print(f"✅ Session test successful!")
                print(f"👤 Verified as: {test_me.first_name} {test_me.last_name or ''}")
                await test_client.disconnect()
                return True
            else:
                print("❌ Session test failed - not authorized")
                await test_client.disconnect()
                return False
        else:
            print(f"❌ Session file was not created: {session_file_path}")
            return False
            
    except PhoneNumberInvalidError:
        print("❌ Invalid phone number! Please check the format.")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main function"""
    print_banner()
    
    # Verify environment
    if not verify_environment():
        return
    
    # Clean up old session files
    cleanup_old_session_files()
    
    # Create session with phone
    success = await create_session_with_phone()
    
    print("\n" + "="*60)
    if success:
        print("🎉 Session creation completed successfully!")
        print("✅ You can now run your bot with the session file")
        print("💡 Remember to remove TELETHON_SESSION_STRING from .env")
    else:
        print("❌ Session creation failed!")
        print("🔧 Please check the error messages above")
    print("="*60)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)