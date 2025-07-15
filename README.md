# CSV Contact Manager Agent 🤖

A Telegram bot that helps you parse CSV files and manually review contacts before adding them to Mailchimp and/or Pipedrive.

## Features

- 📁 **CSV Upload**: Upload CSV files directly to Telegram
- 👤 **Contact Parsing**: Automatically extracts name, email, and LinkedIn URL
- ✅ **Manual Review**: Review each contact individually with simple tap buttons
- 📧 **Mailchimp Integration**: Add contacts to your email lists
- 📊 **Pipedrive Integration**: Add contacts as persons in your CRM
- 🚀 **Easy Deployment**: Ready to deploy on Railway, Render, or Heroku

## Supported CSV Format

The bot expects CSV files with these columns:
- `name` - Full name (required)
- `email` - Email address (required)
- `What is your LinkedIn profile?` - LinkedIn URL (required)
- `first_name` - First name (optional)
- `last_name` - Last name (optional)

## Quick Start

### 1. Set Up Telegram Bot

1. Message [@BotFather](https://t.me/botfather) on Telegram
2. Create a new bot with `/newbot`
3. Copy the bot token

### 2. Get API Keys

#### Mailchimp (Optional)
1. Go to [Mailchimp API](https://mailchimp.com/developer/marketing/guides/quick-start/)
2. Get your API key
3. Find your List ID and Server Prefix

#### Pipedrive (Optional)
1. Go to [Pipedrive API](https://developers.pipedrive.com/)
2. Get your API key
3. Note your domain (e.g., `yourcompany` for `yourcompany.pipedrive.com`)

### 3. Deploy

#### Option A: Railway (Recommended)

1. Fork this repository
2. Go to [Railway](https://railway.app/)
3. Create new project from GitHub
4. Add environment variables:
   ```
   TELEGRAM_TOKEN=your_bot_token
   MAILCHIMP_API_KEY=your_mailchimp_key
   MAILCHIMP_LIST_ID=your_list_id
   MAILCHIMP_SERVER_PREFIX=us1
   PIPEDRIVE_API_KEY=your_pipedrive_key
   PIPEDRIVE_DOMAIN=your_domain
   ```
5. Deploy!

#### Option B: Local Development

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create `.env` file:
   ```bash
   cp env.example .env
   # Edit .env with your credentials
   ```
4. Run the application:
   ```bash
   python start.py
   ```

## Usage

1. **Start the bot**: Send `/start` to your bot
2. **Upload CSV**: Send a CSV file to the bot
3. **Review contacts**: For each contact, choose:
   - ✅ Add to Mailchimp
   - ✅ Add to Pipedrive
   - ✅ Add to Both
   - ❌ Skip
4. **Complete**: Bot will process all contacts and show results

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_TOKEN` | Your Telegram bot token | ✅ |
| `MAILCHIMP_API_KEY` | Mailchimp API key | ❌ |
| `MAILCHIMP_LIST_ID` | Mailchimp list/audience ID | ❌ |
| `MAILCHIMP_SERVER_PREFIX` | Mailchimp server prefix (e.g., us1) | ❌ |
| `PIPEDRIVE_API_KEY` | Pipedrive API key | ❌ |
| `PIPEDRIVE_DOMAIN` | Pipedrive domain | ❌ |
| `API_BASE_URL` | API base URL (default: http://localhost:8000) | ❌ |

## API Endpoints

- `GET /` - Health check
- `GET /health` - Health check
- `POST /upload-csv` - Upload and parse CSV file
- `POST /review-contact` - Review and process a contact
- `GET /contacts/{session_id}` - Get contacts for a session

## File Structure

```
├── main.py              # FastAPI server
├── telegram_bot.py      # Telegram bot
├── start.py             # Startup script
├── requirements.txt     # Python dependencies
├── env.example          # Environment variables template
├── railway.json         # Railway deployment config
├── Procfile             # Heroku deployment config
└── README.md           # This file
```

## Development

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp env.example .env
# Edit .env with your credentials

# Run the application
python start.py
```

### Testing

The bot includes validation for:
- Email format
- LinkedIn URL format
- Required fields presence

## Troubleshooting

### Common Issues

1. **Bot not responding**: Check your `TELEGRAM_TOKEN`
2. **CSV parsing errors**: Ensure your CSV has the required columns
3. **API integration failures**: Verify your API keys and permissions

### Logs

Check the application logs for detailed error messages. The bot logs all operations for debugging.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - feel free to use this for your own projects!

## Support

If you need help, please open an issue on GitHub or contact the maintainer. 