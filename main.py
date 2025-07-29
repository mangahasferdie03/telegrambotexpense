import os
import logging
import json
import base64
from datetime import datetime
from io import BytesIO
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from openai import OpenAI
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class ExpenseTrackerBot:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN') or '8112811334:AAGWhQz7MVRaEFcOyNs442ErWGeYSV8tMqw'
        openai_key = os.getenv('OPENAI_API_KEY') or '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'
        self.openai_client = OpenAI(api_key=openai_key)
        self.ph_timezone = pytz.timezone('Asia/Manila')
        self.pending_expenses = {}
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        welcome_message = (
            "🏪 Welcome to Expense Tracker Bot!\n\n"
            "Send me:\n"
            "📷 Images of receipts or GCash screenshots\n"
            "🎵 Audio recordings of expenses\n"
            "💬 Text descriptions of expenses\n\n"
            "I'll parse them and extract expense details for you!"
        )
        await update.message.reply_text(welcome_message)
    
    async def handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle photo messages"""
        try:
            # Send loading message
            loading_message = await update.message.reply_text("🔍 Analyzing receipt image...")
            
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            
            # Download the image
            response = requests.get(file.file_path)
            image_bytes = response.content
            
            # Convert to base64 for OpenAI
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            # Parse the expense
            expense_data = await self.parse_image_expense(base64_image)
            
            # Delete loading message and send confirmation with buttons
            await loading_message.delete()
            await self.send_expense_confirmation(update, expense_data)
            
        except Exception as e:
            logger.error(f"Error handling photo: {e}")
            await update.message.reply_text("Sorry, I couldn't process that image. Please try again.")
    
    async def handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle audio messages"""
        try:
            audio = update.message.voice or update.message.audio
            file = await context.bot.get_file(audio.file_id)
            
            # Download the audio
            response = requests.get(file.file_path)
            audio_bytes = response.content
            
            # Parse the expense
            expense_data = await self.parse_audio_expense(audio_bytes)
            
            # Send confirmation with buttons
            await self.send_expense_confirmation(update, expense_data)
            
        except Exception as e:
            logger.error(f"Error handling audio: {e}")
            await update.message.reply_text("Sorry, I couldn't process that audio. Please try again.")
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        try:
            # Send loading message
            loading_message = await update.message.reply_text("💭 Processing expense description...")
            
            text = update.message.text
            
            # Parse the expense
            expense_data = await self.parse_text_expense(text)
            
            # Delete loading message and send confirmation with buttons
            await loading_message.delete()
            await self.send_expense_confirmation(update, expense_data)
            
        except Exception as e:
            logger.error(f"Error handling text: {e}")
            await update.message.reply_text("Sorry, I couldn't process that text. Please try again.")
    
    async def parse_image_expense(self, base64_image):
        """Parse expense from image using OpenAI Vision"""
        current_time = datetime.now(self.ph_timezone)
        
        prompt = f"""
        You are an expert at reading receipts and payment screenshots. Analyze this image carefully and extract expense information.
        
        Current Philippine time: {current_time.strftime('%Y-%m-%d %I:%M %p')}

        Look for these details in the image:
        1. Date: ALWAYS use today's date in format "Month Day, Year": {current_time.strftime('%B %d, %Y')}
        2. Time: ALWAYS use current Philippine time in 12-hour format: {current_time.strftime('%I:%M %p')}
        3. Mode of Payment: 
           - If you see "GCash" branding, logos, or text → "GCash"
           - If you see card logos (Visa, Mastercard) or "CARD" → "Debit Card" or "Credit Card"
           - If it's a paper receipt without digital payment info → "Cash"
           - Otherwise → "Unknown"
        4. Source: The restaurant/store/business name (with proper Title Case capitalization)
        5. Category: Based on the business type:
           - Restaurants/Food → "Food"
           - Gas stations → "Transportation" 
           - Malls/Retail → "Shopping"
           - Utilities → "Bills"
           - etc.
        6. Amount: Look for "Total", "Amount", or the final price. Format with commas (e.g., "1,056.00")
        7. Notes: List the specific items purchased from the receipt (e.g., "Tonkotsu Ramen, Gyoza, Iced Tea"). If items aren't clearly visible, provide a brief summary

        IMPORTANT: 
        - Read the text in the image carefully
        - Don't return "Unknown" unless you truly cannot read the information
        - The business name should be readable from the receipt header

        Return ONLY a valid JSON object with these exact keys: date, time, mode_of_payment, source, category, amount, notes
        
        Example format:
        {{"date": "July 28, 2025", "time": "10:18 PM", "mode_of_payment": "Cash", "source": "Jikoku Fukuoka Ramen", "category": "Food", "amount": "1,056.00", "notes": "Tonkotsu Ramen, Gyoza (5 pcs), Iced Green Tea"}}
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            content = response.choices[0].message.content.strip()
            logger.info(f"OpenAI Vision response: {content}")
            
            # Try to extract JSON from the response
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            elif content.startswith('```'):
                content = content.replace('```', '').strip()
                
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}. Response: {content}")
            return self.get_default_expense_data(current_time)
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            return self.get_default_expense_data(current_time)
    
    async def parse_audio_expense(self, audio_bytes):
        """Parse expense from audio using OpenAI Whisper and GPT"""
        current_time = datetime.now(self.ph_timezone)
        
        # Transcribe audio
        audio_file = BytesIO(audio_bytes)
        audio_file.name = "audio.mp3"
        
        transcript = self.openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        
        # Parse the transcribed text
        return await self.parse_text_expense(transcript.text, current_time)
    
    async def parse_text_expense(self, text, current_time=None):
        """Parse expense from text using OpenAI GPT"""
        if current_time is None:
            current_time = datetime.now(self.ph_timezone)
        
        prompt = f"""
        Parse this expense description and extract information. Current Philippine time: {current_time.strftime('%Y-%m-%d %I:%M %p')}

        Text: "{text}"

        Extract:
        1. Date: ALWAYS use today's date in format "Month Day, Year": {current_time.strftime('%B %d, %Y')}
        2. Time: ALWAYS use current Philippine time in 12-hour format: {current_time.strftime('%I:%M %p')}
        3. Mode of Payment: Determine from context (GCash, debit card, credit card, cash)
        4. Source: The business/merchant name (proper capitalization)
        5. Category: Classify the expense (Food, Transportation, Shopping, Bills, etc.)
        6. Amount: Extract amount with proper comma formatting
        7. Notes: Brief summary with proper grammar

        Return ONLY a JSON object with these exact keys: date, time, mode_of_payment, source, category, amount, notes
        """
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )
        
        try:
            return json.loads(response.choices[0].message.content)
        except json.JSONDecodeError:
            return self.get_default_expense_data(current_time)
    
    def get_default_expense_data(self, current_time):
        """Return default expense data structure"""
        return {
            "date": current_time.strftime('%B %d, %Y'),
            "time": current_time.strftime('%I:%M %p'),
            "mode_of_payment": "Unknown",
            "source": "Unknown",
            "category": "Miscellaneous",
            "amount": "0",
            "notes": "Could not parse expense details"
        }
    
    def format_expense_response(self, expense_data):
        """Format the expense data into a nice response"""
        return f"""
📊 Expense Parsed

📅 Date: {expense_data['date']}
🕐 Time: {expense_data['time']}
💳 Payment Mode: {expense_data['mode_of_payment']}
🏪 Source: {expense_data['source']}
📂 Category: {expense_data['category']}
💰 Amount: ₱{expense_data['amount']}
📝 Notes: {expense_data['notes']}
        """.strip()
    
    async def send_expense_confirmation(self, update: Update, expense_data):
        """Send expense data with confirmation buttons"""
        user_id = update.effective_user.id
        
        # Store the expense data temporarily
        self.pending_expenses[user_id] = expense_data
        
        # Create inline keyboard
        keyboard = [
            [
                InlineKeyboardButton("✅ CONFIRM", callback_data="confirm"),
                InlineKeyboardButton("✏️ EDIT", callback_data="edit"),
                InlineKeyboardButton("❌ CANCEL", callback_data="cancel")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send the formatted expense with buttons
        response_text = self.format_expense_response(expense_data) + "\n\n📋 Please confirm or edit this expense:"
        await update.message.reply_text(response_text, reply_markup=reply_markup)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        action = query.data
        
        if user_id not in self.pending_expenses:
            await query.edit_message_text("❌ Expense data not found. Please try again.")
            return
        
        if action == "confirm":
            expense_data = self.pending_expenses[user_id]
            del self.pending_expenses[user_id]
            
            confirmed_text = self.format_expense_response(expense_data) + "\n\n✅ Expense confirmed and saved!"
            await query.edit_message_text(confirmed_text)
            
        elif action == "edit":
            expense_data = self.pending_expenses[user_id]
            edit_text = f"""✏️ Edit mode activated!

What should we change here?

📅 Date: {expense_data['date']}
🕐 Time: {expense_data['time']}
💳 Payment Mode: {expense_data['mode_of_payment']}
🏪 Source: {expense_data['source']}
📂 Category: {expense_data['category']}
💰 Amount: ₱{expense_data['amount']}
📝 Notes: {expense_data['notes']}"""
            await query.edit_message_text(edit_text)
            
        elif action == "cancel":
            del self.pending_expenses[user_id]
            await query.edit_message_text("❌ Expense entry cancelled.")
    
    async def handle_edit_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages when user is in edit mode"""
        user_id = update.effective_user.id
        
        if user_id not in self.pending_expenses:
            # Regular message handling
            await self.handle_text(update, context)
            return
        
        # User is in edit mode
        if update.message.voice or update.message.audio:
            # Handle voice message edits
            audio = update.message.voice or update.message.audio
            file = await context.bot.get_file(audio.file_id)
            response = requests.get(file.file_path)
            audio_bytes = response.content
            
            # Transcribe audio
            audio_file = BytesIO(audio_bytes)
            audio_file.name = "audio.mp3"
            transcript = self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
            edit_instruction = transcript.text
            
            # Show what Whisper transcribed
            await update.message.reply_text(f"🎙️ I heard: \"{edit_instruction}\"")
        else:
            # Handle text message edits
            edit_instruction = update.message.text
        
        expense_data = self.pending_expenses[user_id]
        
        # Apply the edit using OpenAI
        updated_expense = await self.apply_edit_to_expense(expense_data, edit_instruction)
        self.pending_expenses[user_id] = updated_expense
        
        # Send updated expense with buttons again
        await self.send_expense_confirmation(update, updated_expense)
    
    async def apply_edit_to_expense(self, expense_data, edit_instruction):
        """Apply user's edit instruction to expense data"""
        prompt = f"""
        Original expense data: {json.dumps(expense_data, indent=2)}
        
        User's edit instruction: "{edit_instruction}"
        
        Apply the user's requested changes to the expense data intelligently:
        1. Keep all unchanged fields exactly the same
        2. For notes: Rewrite to sound natural and conversational, like how a person would describe the expense
        3. Don't just append - create a proper, flowing sentence
        4. For other fields: Update as requested
        
        Example: 
        Original notes: "Regular Concrete, Special Oreo"
        Edit: "add that I ate with my college friends"
        Good result: "Ate with my college friends and ordered Regular Concrete and Special Oreo."
        
        Make the notes sound like natural human speech with proper grammar and flow.
        Return ONLY the updated JSON object with the same structure.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.1
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean up JSON response
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            elif content.startswith('```'):
                content = content.replace('```', '').strip()
            
            return json.loads(content)
            
        except Exception as e:
            logger.error(f"Error applying edit: {e}")
            return expense_data
    
    def run(self):
        """Start the bot"""
        application = Application.builder().token(self.telegram_token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        application.add_handler(MessageHandler(filters.PHOTO, self.handle_photo))
        application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self.handle_audio))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_edit_message))
        
        # Start the bot
        print("Expense Tracker Bot started!")
        application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    bot = ExpenseTrackerBot()
    bot.run()
