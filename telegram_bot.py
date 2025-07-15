import os
import logging
import asyncio
import aiohttp
import tempfile
from typing import Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Store active sessions for each user
user_sessions: Dict[int, Dict] = {}

class ContactManagerBot:
    def __init__(self):
        self.application = Application.builder().token(TELEGRAM_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup bot command and message handlers"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
🤖 **CSV Contact Manager Bot**

Upload a CSV file with contacts (name, email, LinkedIn URL) and I'll help you review and add them to Mailchimp and/or Pipedrive.

**How to use:**
1. Send me a CSV file
2. I'll parse the contacts and show them to you
3. Review each contact and choose where to add them
4. Single tap to approve/reject for each service

**Supported CSV format:**
- `name` - Full name
- `email` - Email address  
- `What is your LinkedIn profile?` - LinkedIn URL
- `first_name` and `last_name` (optional)

Ready to upload your CSV file! 📁
        """
        await update.message.reply_text(welcome_message, parse_mode='Markdown')
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
📋 **Available Commands:**

/start - Start the bot and see instructions
/help - Show this help message

**To process contacts:**
1. Send a CSV file to the bot
2. Review each contact one by one
3. Use the buttons to add to Mailchimp and/or Pipedrive
4. Skip contacts you don't want to add

**Contact Review:**
- ✅ Mailchimp - Add to your email list
- ✅ Pipedrive - Add as a person/contact
- ❌ Skip - Don't add anywhere
- ⏭️ Next - Move to next contact
        """
        await update.message.reply_text(help_message, parse_mode='Markdown')
    
    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle CSV file uploads"""
        user_id = update.effective_user.id
        document = update.message.document
        
        if not document.file_name.lower().endswith('.csv'):
            await update.message.reply_text("❌ Please upload a CSV file (.csv extension)")
            return
        
        await update.message.reply_text("📥 Processing your CSV file...")
        
        try:
            # Download the file
            file = await context.bot.get_file(document.file_id)
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as temp_file:
                async with aiohttp.ClientSession() as session:
                    async with session.get(file.file_path) as response:
                        content = await response.read()
                        temp_file.write(content)
                        temp_file_path = temp_file.name
            
            # Upload to our API
            async with aiohttp.ClientSession() as session:
                with open(temp_file_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('file', f, filename=document.file_name)
                    
                    async with session.post(f"{API_BASE_URL}/upload-csv", data=data) as response:
                        if response.status == 200:
                            result = await response.json()
                            
                            # Store session for this user
                            user_sessions[user_id] = {
                                'session_id': result['session_id'],
                                'contacts': result['contacts'],
                                'total_contacts': result['total_contacts'],
                                'current_index': 0
                            }
                            
                            # Clean up temp file
                            os.unlink(temp_file_path)
                            
                            # Show first contact for review
                            await self.show_contact_for_review(update, context, user_id)
                        else:
                            error_text = await response.text()
                            await update.message.reply_text(f"❌ Error processing CSV: {error_text}")
                            os.unlink(temp_file_path)
        
        except Exception as e:
            logger.error(f"Error handling document: {e}")
            await update.message.reply_text(f"❌ Error processing file: {str(e)}")
    
    async def show_contact_for_review(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Show a contact for review with action buttons"""
        if user_id not in user_sessions:
            await update.message.reply_text("❌ No active session found. Please upload a CSV file.")
            return
        
        session = user_sessions[user_id]
        current_index = session['current_index']
        
        if current_index >= session['total_contacts']:
            await update.message.reply_text("✅ All contacts have been reviewed!")
            del user_sessions[user_id]
            return
        
        # Get contact details from API
        async with aiohttp.ClientSession() as session_client:
            async with session_client.get(f"{API_BASE_URL}/contacts/{session['session_id']}") as response:
                if response.status == 200:
                    result = await response.json()
                    contact = result['contacts'][current_index]
                else:
                    await update.message.reply_text("❌ Error loading contact details")
                    return
        
        # Create contact display message
        contact_text = f"""
👤 **Contact {current_index + 1} of {session['total_contacts']}**

**Name:** {contact['name']}
**Email:** {contact['email']}
**LinkedIn:** {contact['linkedin_url']}
        """
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ Add to Mailchimp", callback_data=f"mailchimp_{current_index}"),
                InlineKeyboardButton("✅ Add to Pipedrive", callback_data=f"pipedrive_{current_index}")
            ],
            [
                InlineKeyboardButton("✅ Add to Both", callback_data=f"both_{current_index}"),
                InlineKeyboardButton("❌ Skip", callback_data=f"skip_{current_index}")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(contact_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        user_id = update.effective_user.id
        
        if user_id not in user_sessions:
            await query.answer("❌ No active session found")
            return
        
        await query.answer()
        
        # Parse callback data
        action, contact_index = query.data.split('_')
        contact_index = int(contact_index)
        
        session = user_sessions[user_id]
        
        if contact_index != session['current_index']:
            await query.edit_message_text("⚠️ This contact has already been processed. Please continue with the current contact.")
            return
        
        # Process the action
        results = {}
        
        if action in ['mailchimp', 'both']:
            results['mailchimp'] = await self.add_contact_to_service(user_id, contact_index, 'mailchimp')
        
        if action in ['pipedrive', 'both']:
            results['pipedrive'] = await self.add_contact_to_service(user_id, contact_index, 'pipedrive')
        
        # Show results
        result_text = f"📊 **Results for {session['contacts'][contact_index]['name']}:**\n\n"
        
        if 'mailchimp' in results:
            status = "✅ Added" if results['mailchimp'] else "❌ Failed"
            result_text += f"**Mailchimp:** {status}\n"
        
        if 'pipedrive' in results:
            status = "✅ Added" if results['pipedrive'] else "❌ Failed"
            result_text += f"**Pipedrive:** {status}\n"
        
        if action == 'skip':
            result_text = f"⏭️ **Skipped:** {session['contacts'][contact_index]['name']}"
        
        await query.edit_message_text(result_text, parse_mode='Markdown')
        
        # Move to next contact
        session['current_index'] += 1
        
        # Show next contact or completion message
        if session['current_index'] < session['total_contacts']:
            await asyncio.sleep(1)  # Brief pause
            await self.show_contact_for_review(update, context, user_id)
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text="🎉 **All contacts processed!**\n\nUpload another CSV file when you're ready.",
                parse_mode='Markdown'
            )
            del user_sessions[user_id]
    
    async def add_contact_to_service(self, user_id: int, contact_index: int, service: str) -> bool:
        """Add contact to specified service via API"""
        session = user_sessions[user_id]
        
        review_data = {
            "session_id": session['session_id'],
            "contact_index": contact_index,
            "add_to_mailchimp": service == 'mailchimp',
            "add_to_pipedrive": service == 'pipedrive'
        }
        
        try:
            async with aiohttp.ClientSession() as session_client:
                async with session_client.post(
                    f"{API_BASE_URL}/review-contact",
                    json=review_data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result['results'].get(service, False)
                    else:
                        logger.error(f"Error adding to {service}: {await response.text()}")
                        return False
        except Exception as e:
            logger.error(f"Error adding to {service}: {e}")
            return False
    
    def run(self):
        """Start the bot"""
        logger.info("Starting Telegram bot...")
        self.application.run_polling()

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not found in environment variables")
        exit(1)
    
    bot = ContactManagerBot()
    bot.run() 