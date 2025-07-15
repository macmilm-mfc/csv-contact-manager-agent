import asyncio
import subprocess
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def run_api_server():
    """Run the FastAPI server"""
    print("🚀 Starting FastAPI server...")
    process = await asyncio.create_subprocess_exec(
        sys.executable, "main.py",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    return process

async def run_telegram_bot():
    """Run the Telegram bot"""
    print("🤖 Starting Telegram bot...")
    process = await asyncio.create_subprocess_exec(
        sys.executable, "telegram_bot.py",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    return process

async def main():
    """Run both services concurrently"""
    print("🎯 Starting CSV Contact Manager Agent...")
    
    # Check if required environment variables are set
    required_vars = ["TELEGRAM_TOKEN"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set them in your .env file or environment")
        return
    
    # Start both services
    api_process = await run_api_server()
    bot_process = await run_telegram_bot()
    
    try:
        # Wait for both processes
        await asyncio.gather(
            api_process.wait(),
            bot_process.wait()
        )
    except KeyboardInterrupt:
        print("\n🛑 Shutting down services...")
        api_process.terminate()
        bot_process.terminate()
        await asyncio.gather(
            api_process.wait(),
            bot_process.wait()
        )
        print("✅ Services stopped")

if __name__ == "__main__":
    asyncio.run(main()) 