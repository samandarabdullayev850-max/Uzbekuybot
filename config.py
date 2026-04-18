import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

CITIES = ["Toshkent", "Samarqand", "Buxoro", "Namangan", "Andijon", "Fargona", "Nukus", "Qarshi", "Termiz"]

DEAL_TYPES = {"uz": ["Ijaraga", "Sotuvga"], "ru": ["Arenda", "Prodaja"], "en": ["Rent", "Sale"]}

ROOMS = ["1", "2", "3", "4", "5+"]

NOTIFY_FREQ = {"uz": {"instant": "Darhol", "daily": "Kuniga 1", "weekly": "Haftada 1"}, "ru": {"instant": "Srazu", "daily": "Raz v den", "weekly": "Raz v nedelyu"}, "en": {"instant": "Instantly", "daily": "Once a day", "weekly": "Once a week"}}

DAILY_LIMITS = [3, 5, 10, 0]
