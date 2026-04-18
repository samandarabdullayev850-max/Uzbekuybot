import asyncio
import logging
from telegram.ext import ApplicationBuilder
from config import BOT_TOKEN
from handlers.start import register_start_handlers
from handlers.search import register_search_handlers
from handlers.listing import register_listing_handlers
from handlers.settings import register_settings_handlers

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    register_start_handlers(app)
    register_search_handlers(app)
    register_listing_handlers(app)
    register_settings_handlers(app)
    await app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
