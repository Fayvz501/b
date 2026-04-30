import os
from dotenv import load_dotenv

load_dotenv()

VK_TOKEN = os.getenv("VK_TOKEN")
DB_PATH = "src/database/bot_database.db"
PDF_DIR = "generated_reports"

if not os.path.exists(PDF_DIR):
    os.makedirs(PDF_DIR)