from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode
from database import get_user, get_listings, count_listings
from config import CITIES, DEAL_TYPES, ROOMS
from handlers.start import t

PRICE_RANGES = [(0,300),(300,600),(600,1000),(1000,2000),(2000,99999)]
PRICE_LABELS = ["$0-300","$300-600","$600-1000","$1000-2000","$2000+"]

def listing_card(listing, lang):
    tx = t(lang)
    lines = [f"{listing.get('title','—')}"]
    if listing.get("price"): lines.append(f"${listing['price']}" + (" / oy" if listing.get("deal_type")=="rent" else ""))
    if listing.get("rooms"): lines.append(f"{listing['rooms']} xona")
    if listing.get("address"): lines.append(f"{listing['address']}")
    if listing.get("description"): lines.append(f"{listing['description'][:150]}")
    if listing.get("phone"): lines.append(f"{listing['phone']}")
    if listing.get("source") and listing["source"]!="bot": lines.append(f"Manba: {listing['source']}")
    return "\n".join(lines)

async def search_start(update, context):
    user = get_user(update.effective_user.id)
    lang = user["language"] if user else "uz"
    tx = t(lang)
    context.user_data["search"] = {}
    city_buttons = [[InlineKeyboardButton(c, callback_data=f"s_city_{c}")] for c in CITIES]
    await update.message.reply_text(tx["choose_city"], reply_markup=InlineKeyboardMarkup(city_buttons))

async def search_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = get_user(query.from_user.id)
    lang = user["language"] if user else "uz"
    tx = t(lang)
    search = context.user_data.get("search", {})

    if data.startswith("s_city_"):
        search["city"] = data.replace("s_city_","")
        context.user_data["search"] = search
        deal_btns = [[InlineKeyboardButton(DEAL_TYPES[lang][0], callback_data="s_deal_rent"), InlineKeyboardButton(DEAL_TYPES[lang][1], callback_data="s_deal_sale")]]
        await query.edit_message_text(tx["choose_deal"], reply_markup=InlineKeyboardMarkup(deal_btns))

    elif data.startswith("s_deal_"):
        search["deal_type"] = data.replace("s_deal_","")
        context.user_data["search"] = search
        room_btns = [[InlineKeyboardButton(r, callback_data=f"s_rooms_{r}") for r in ROOMS]]
        await query.edit_message_text(tx["choose_rooms"], reply_markup=InlineKeyboardMarkup(room_btns))

    elif data.startswith("s_rooms_"):
        search["rooms"] = data.replace("s_rooms_","")
        context.user_data["search"] = search
        price_btns = [[InlineKeyboardButton(p, callback_data=f"s_price_{i}")] for i,p in enumerate(PRICE_LABELS)]
        await query.edit_message_text(tx["choose_price"], reply_markup=InlineKeyboardMarkup(price_btns))

    elif data.startswith("s_price_"):
        idx = int(data.replace("s_price_",""))
        search["price_min"], search["price_max"] = PRICE_RANGES[idx]
        context.user_data["search"] = search
        await show_results(query, context, lang, 0)

    elif data.startswith("page_"):
        await show_results(query, context, lang, int(data.replace("page_","")))

async def show_results(query, context, lang, page):
    tx = t(lang)
    search = context.user_data.get("search", {})
    listings = get_listings(city=search.get("city"), deal_type=search.get("deal_type"), rooms=search.get("rooms"), price_min=search.get("price_min"), price_max=search.get("price_max"), offset=page*3, limit=3)
    total = count_listings(city=search.get("city"), deal_type=search.get("deal_type"), rooms=search.get("rooms"), price_min=search.get("price_min"), price_max=search.get("price_max"))
    if not listings:
        await query.edit_message_text(tx["no_results"])
        return
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(tx["btn_prev"], callback_data=f"page_{page-1}"))
    if (page+1)*3 < total: nav.append(InlineKeyboardButton(tx["btn_next"], callback_data=f"page_{page+1}"))
    for i, listing in enumerate(listings):
        text = listing_card(listing, lang)
        kb = InlineKeyboardMarkup([nav]) if nav and i==len(listings)-1 else None
        photos = listing.get("photos") or []
        if photos:
            await query.message.reply_photo(photo=photos[0], caption=text, reply_markup=kb)
        else:
            await query.message.reply_text(text, reply_markup=kb)
    await query.message.delete()

def register_search_handlers(app):
    app.add_handler(MessageHandler(filters.Regex("^(Qidiruv|Poisk|Search)$"), search_start))
    app.add_handler(CallbackQueryHandler(search_callback, pattern="^(s_city_|s_deal_|s_rooms_|s_price_|page_)"))
