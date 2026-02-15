from dotenv import load_dotenv
import os

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))

MERCHANT_KEY = os.getenv("MERCHANT_KEY")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
DEPOSIT_LOG_ID = int(os.getenv("DEPOSIT_LOG_ID"))
