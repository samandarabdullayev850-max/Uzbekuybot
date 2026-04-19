import os
import asyncio
import logging
import threading
from flask import Flask
from dotenv import load_dotenv
from supabase import create_client
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

CITIES = ["Toshkent","Samarqand","Buxoro","Namangan","Andijon","Fargona","Nukus","Qarshi","Termiz"]
DEAL_TYPES = {"uz":["Ijaraga","Sotuvga"],"ru":["Arenda","Prodaja"],"en":["Rent","Sale"]}
ROOMS = ["1","2","3","4","5+"]
PRICE_RANGES = [(0,300),(300,600),(600,1000),(1000,2000),(2000,99999)]
PRICE_LABELS = ["$0-300","$300-600","$600-1000","$1000-2000","$2000+"]
NOTIFY_FREQ = {"uz":{"instant":"Darhol","daily":"Kuniga 1","weekly":"Haftada 1"},"ru":{"instant":"Srazu","daily":"Raz v den","weekly":"Raz v nedelyu"},"en":{"instant":"Instantly","daily":"Once a day","weekly":"Once a week"}}
DAILY_LIMITS = [3,5,10,0]

UZ = {"choose_language":"Tilni tanlang:","welcome":"UyBot ga xush kelibsiz!","main_menu":"Asosiy menyu:","btn_search":"Qidiruv","btn_my_listings":"Mening elonlarim","btn_add_listing":"Elon berish","btn_settings":"Sozlamalar","btn_help":"Yordam","choose_city":"Qaysi shaharda?","choose_deal":"Nima qidirmoqdasiz?","choose_rooms":"Nechta xona?","choose_price":"Narx oraligi?","no_results":"Hech narsa topilmadi.","results_found":"{count} ta elon:","btn_next":"Keyingi","btn_prev":"Oldingi","btn_cancel":"Bekor","btn_skip":"Otkazib yuborish","ask_deal":"Ijara yoki sotish?","ask_city":"Qaysi shahar?","ask_rooms":"Nechta xona?","ask_price":"Narx ($):","ask_description":"Tavsif yoki otkazib yuborish:","ask_photos":"Rasm yuboring:","ask_address":"Manzil:","ask_phone":"Telefon:","listing_saved":"Elon saqlandi!","settings_title":"Sozlamalar:","notif_on":"Xabar: Yoqilgan","notif_off":"Xabar: Ochirilgan","choose_freq":"Qanchalik tez?","choose_limit":"Kuniga nechta?","limit_unlimited":"Cheksiz","settings_saved":"Saqlandi!","only_cheap_on":"Arzon: Ha","only_cheap_off":"Arzon: Yoq","new_listing_notif":"Yangi elon!","help_text":"UyBot\n/start\n/add\n/settings\n/stats","stats_title":"Statistika:","stats_users":"Foydalanuvchilar: {count}","stats_listings":"Elonlar: {count}","stats_active":"Faol elonlar: {count}","stats_subs":"Faol obunalar: {count}"}
RU = {"choose_language":"Tilni tanlang:","welcome":"Dobro pozhalovat!","main_menu":"Menyu:","btn_search":"Poisk","btn_my_listings":"Moi obyavleniya","btn_add_listing":"Dobavit","btn_settings":"Nastroyki","btn_help":"Pomosh","choose_city":"Gorod?","choose_deal":"Chto ischete?","choose_rooms":"Komnaty?","choose_price":"Tsena?","no_results":"Ne naydeno.","results_found":"{count}:","btn_next":"Dalee","btn_prev":"Nazad","btn_cancel":"Otmena","btn_skip":"Propustit","ask_deal":"Arenda ili prodazha?","ask_city":"Gorod?","ask_rooms":"Komnaty?","ask_price":"Tsena ($):","ask_description":"Opisanie:","ask_photos":"Foto:","ask_address":"Adres:","ask_phone":"Telefon:","listing_saved":"Sokhraneno!","settings_title":"Nastroyki:","notif_on":"Uvedomleniya: Vkl","notif_off":"Uvedomleniya: Otkl","choose_freq":"Kak chasto?","choose_limit":"Maks v den?","limit_unlimited":"Bez limita","settings_saved":"Sokhraneno!","only_cheap_on":"Deshevle: Da","only_cheap_off":"Deshevle: Net","new_listing_notif":"Novoe obyavlenie!","help_text":"UyBot\n/start\n/add\n/settings\n/stats","stats_title":"Statistika:","stats_users":"Polzovateli: {count}","stats_listings":"Obyavleniya: {count}","stats_active":"Aktivnye: {count}","stats_subs":"Podpiski: {count}"}
EN = {"choose_language":"Choose language:","welcome":"Welcome to UyBot!","main_menu":"Menu:","btn_search":"Search","btn_my_listings":"My listings","btn_add_listing":"Add listing","btn_settings":"Settings","btn_help":"Help","choose_city":"City?","choose_deal":"Looking for?","choose_rooms":"Rooms?","choose_price":"Price?","no_results":"Nothing found.","results_found":"{count} listings:","btn_next":"Next","btn_prev":"Previous","btn_cancel":"Cancel","btn_skip":"Skip","ask_deal":"Rent or sale?","ask_city":"City?","ask_rooms":"Rooms?","ask_price":"Price ($):","ask_description":"Description:","ask_photos":"Photos:","ask_address":"Address:","ask_phone":"Phone:","listing_saved":"Saved!","settings_title":"Settings:","notif_on":"Notifications: On","notif_off":"Notifications: Off","choose_freq":"How often?","choose_limit":"Max per day?","limit_unlimited":"Unlimited","settings_saved":"Saved!","only_cheap_on":"Cheap only: Yes","only_cheap_off":"Cheap only: No","new_listing_notif":"New listing!","help_text":"UyBot\n/start\n/add\n/settings\n/stats","stats_title":"Statistics:","stats_users":"Users: {count}","stats_listings":"Listings: {count}","stats_active":"Active: {count}","stats_subs":"Subscriptions: {count}"}

def tx(lang): return {"uz":UZ,"ru":RU,"en":EN}.get(lang,UZ)

def main_menu_kb(lang):
    t = tx(lang)
    return ReplyKeyboardMarkup([[t["btn_search"]],[t["btn_add_listing"],t["btn_my_listings"]],[t["btn_settings"],t["btn_help"]]],resize_keyboard=True)

def get_user(tid):
    r = supabase.table("users").select("*").eq("telegram_id",tid).execute()
    return r.data[0] if r.data else None

def get_or_create_user(tid,name,username=None):
    u = get_user(tid)
    if not u:
        supabase.table("users").insert({"telegram_id":tid,"full_name":name,"username":username,"language":"uz","is_banned":False}).execute()
        u = get_user(tid)
    return u

def update_lang(tid,lang): supabase.table("users").update({"language":lang}).eq("telegram_id",tid).execute()

def get_listings(city=None,deal_type=None,rooms=None,price_min=None,price_max=None,offset=0,limit=3):
    q = supabase.table("listings").select("*").eq("is_active",True)
    if city: q = q.eq("city",city)
    if deal_type: q = q.eq("deal_type",deal_type)
    if rooms: q = q.eq("rooms",rooms)
    if price_min is not None: q = q.gte("price",price_min)
    if price_max is not None: q = q.lte("price",price_max)
    return q.order("published_at",desc=True).range(offset,offset+limit-1).execute().data

def count_listings(city=None,deal_type=None,rooms=None,price_min=None,price_max=None):
    q = supabase.table("listings").select("id",count="exact").eq("is_active",True)
    if city: q = q.eq("city",city)
    if deal_type: q = q.eq("deal_type",deal_type)
    if rooms: q = q.eq("rooms",rooms)
    if price_min is not None: q = q.gte("price",price_min)
    if price_max is not None: q = q.lte("price",price_max)
    return q.execute().count or 0

def add_listing(data): return supabase.table("listings").insert(data).execute()

def get_sub(uid):
    r = supabase.table("subscriptions").select("*").eq("user_id",uid).execute()
    return r.data[0] if r.data else None

def save_sub(uid,data):
    if get_sub(uid): supabase.table("subscriptions").update(data).eq("user_id",uid).execute()
    else:
        data["user_id"] = uid
        supabase.table("subscriptions").insert(data).execute()

async def cmd_start(update,context):
    u = update.effective_user
    get_or_create_user(u.id,u.full_name,u.username)
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("O'zbek",callback_data="lang_uz"),InlineKeyboardButton("Русский",callback_data="lang_ru"),InlineKeyboardButton("English",callback_data="lang_en")]])
    await update.message.reply_text(UZ["choose_language"],reply_markup=kb)

async def cmd_help(update,context):
    u = get_user(update.effective_user.id)
    lang = u["language"] if u else "uz"
    await update.message.reply_text(tx(lang)["help_text"])

async def cmd_stats(update,context):
    u = get_user(update.effective_user.id)
    lang = u["language"] if u else "uz"
    t = tx(lang)
    users = supabase.table("users").select("id",count="exact").execute().count or 0
    listings = supabase.table("listings").select("id",count="exact").execute().count or 0
    active = supabase.table("listings").select("id",count="exact").eq("is_active",True).execute().count or 0
    subs = supabase.table("subscriptions").select("id",count="exact").eq("is_active",True).execute().count or 0
    text = f"{t['stats_title']}\n\n{t['stats_users'].format(count=users)}\n{t['stats_listings'].format(count=listings)}\n{t['stats_active'].format(count=active)}\n{t['stats_subs'].format(count=subs)}"
    await update.message.reply_text(text)

async def cb_lang(update,context):
    q = update.callback_query
    await q.answer()
    lang = q.data.split("_")[1]
    update_lang(q.from_user.id,lang)
    t = tx(lang)
    await q.message.delete()
    await q.message.reply_text(t["welcome"],reply_markup=main_menu_kb(lang))

async def search_start(update,context):
    u = get_user(update.effective_user.id)
    lang = u["language"] if u else "uz"
    context.user_data["search"] = {}
    btns = [[InlineKeyboardButton(c,callback_data=f"s_city_{c}")] for c in CITIES]
    await update.message.reply_text(tx(lang)["choose_city"],reply_markup=InlineKeyboardMarkup(btns))

async def cb_search(update,context):
    q = update.callback_query
    await q.answer()
    d = q.data
    u = get_user(q.from_user.id)
    lang = u["language"] if u else "uz"
    t = tx(lang)
    s = context.user_data.get("search",{})
    if d.startswith("s_city_"):
        s["city"] = d.replace("s_city_","")
        context.user_data["search"] = s
        btns = [[InlineKeyboardButton(DEAL_TYPES[lang][0],callback_data="s_deal_rent"),InlineKeyboardButton(DEAL_TYPES[lang][1],callback_data="s_deal_sale")]]
        await q.edit_message_text(t["choose_deal"],reply_markup=InlineKeyboardMarkup(btns))
    elif d.startswith("s_deal_"):
        s["deal_type"] = d.replace("s_deal_","")
        context.user_data["search"] = s
        btns = [[InlineKeyboardButton(r,callback_data=f"s_rooms_{r}") for r in ROOMS]]
        await q.edit_message_text(t["choose_rooms"],reply_markup=InlineKeyboardMarkup(btns))
    elif d.startswith("s_rooms_"):
        s["rooms"] = d.replace("s_rooms_","")
        context.user_data["search"] = s
        btns = [[InlineKeyboardButton(p,callback_data=f"s_price_{i}")] for i,p in enumerate(PRICE_LABELS)]
        await q.edit_message_text(t["choose_price"],reply_markup=InlineKeyboardMarkup(btns))
    elif d.startswith("s_price_"):
        idx = int(d.replace("s_price_",""))
        s["price_min"],s["price_max"] = PRICE_RANGES[idx]
        context.user_data["search"] = s
        await show_results(q,context,lang,0)
    elif d.startswith("s_page_"):
        await show_results(q,context,lang,int(d.replace("s_page_","")))

async def show_results(q,context,lang,page):
    t = tx(lang)
    s = context.user_data.get("search",{})
    listings = get_listings(city=s.get("city"),deal_type=s.get("deal_type"),rooms=s.get("rooms"),price_min=s.get("price_min"),price_max=s.get("price_max"),offset=page*3,limit=3)
    total = count_listings(city=s.get("city"),deal_type=s.get("deal_type"),rooms=s.get("rooms"),price_min=s.get("price_min"),price_max=s.get("price_max"))
    if not listings:
        await q.edit_message_text(t["no_results"])
        return
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(t["btn_prev"],callback_data=f"s_page_{page-1}"))
    if (page+1)*3 < total: nav.append(InlineKeyboardButton(t["btn_next"],callback_data=f"s_page_{page+1}"))
    for i,l in enumerate(listings):
        lines = [l.get("title","—")]
        if l.get("price"): lines.append(f"${l['price']}")
        if l.get("rooms"): lines.append(f"{l['rooms']} xona")
        if l.get("address"): lines.append(l["address"])
        if l.get("description"): lines.append(l["description"][:150])
        if l.get("phone"): lines.append(l["phone"])
        text = "\n".join(lines)
        kb = InlineKeyboardMarkup([nav]) if nav and i==len(listings)-1 else None
        photos = l.get("photos") or []
        if photos: await q.message.reply_photo(photo=photos[0],caption=text,reply_markup=kb)
        else: await q.message.reply_text(text,reply_markup=kb)
    await q.message.delete()

async def add_start(update,context):
    u = get_user(update.effective_user.id)
    lang = u["language"] if u else "uz"
    t = tx(lang)
    context.user_data["nl"] = {}
    context.user_data["nl_step"] = "deal"
    context.user_data["nl_photos"] = []
    btns = [[InlineKeyboardButton(DEAL_TYPES[lang][0],callback_data="nl_deal_rent"),InlineKeyboardButton(DEAL_TYPES[lang][1],callback_data="nl_deal_sale")],[InlineKeyboardButton(t["btn_cancel"],callback_data="nl_cancel")]]
    await update.message.reply_text(t["ask_deal"],reply_markup=InlineKeyboardMarkup(btns))

async def cb_listing(update,context):
    q = update.callback_query
    await q.answer()
    d = q.data
    u = get_user(q.from_user.id)
    lang = u["language"] if u else "uz"
    t = tx(lang)
    nl = context.user_data.get("nl",{})
    if d == "nl_cancel":
        context.user_data.pop("nl",None)
        context.user_data.pop("nl_step",None)
        await q.message.delete()
        return
    if d.startswith("nl_deal_"):
        nl["deal_type"] = d.replace("nl_deal_","")
        context.user_data["nl"] = nl
        context.user_data["nl_step"] = "city"
        btns = [[InlineKeyboardButton(c,callback_data=f"nl_city_{c}")] for c in CITIES]
        btns.append([InlineKeyboardButton(t["btn_cancel"],callback_data="nl_cancel")])
        await q.edit_message_text(t["ask_city"],reply_markup=InlineKeyboardMarkup(btns))
    elif d.startswith("nl_city_"):
        nl["city"] = d.replace("nl_city_","")
        context.user_data["nl"] = nl
        context.user_data["nl_step"] = "rooms"
        btns = [[InlineKeyboardButton(str(r),callback_data=f"nl_rooms_{r}") for r in [1,2,3,4,5]]]
        btns.append([InlineKeyboardButton(t["btn_cancel"],callback_data="nl_cancel")])
        await q.edit_message_text(t["ask_rooms"],reply_markup=InlineKeyboardMarkup(btns))
    elif d.startswith("nl_rooms_"):
        nl["rooms"] = int(d.replace("nl_rooms_",""))
        context.user_data["nl"] = nl
        context.user_data["nl_step"] = "price"
        await q.edit_message_text(t["ask_price"])
    elif d == "nl_skip_desc":
        nl["description"] = None
        context.user_data["nl"] = nl
        context.user_data["nl_step"] = "photos"
        await q.edit_message_text(t["ask_photos"],reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t["btn_skip"],callback_data="nl_skip_photos")]]))
    elif d == "nl_skip_photos":
        context.user_data["nl_step"] = "address"
        await q.edit_message_text(t["ask_address"])
    elif d == "nl_photos_done":
        context.user_data["nl_step"] = "address"
        await q.message.reply_text(t["ask_address"])
    elif d == "nl_skip_addr":
        nl["address"] = None
        context.user_data["nl"] = nl
        context.user_data["nl_step"] = "phone"
        await q.edit_message_text(t["ask_phone"])

async def msg_handler(update,context):
    if "nl_step" not in context.user_data: return
    step = context.user_data["nl_step"]
    u = get_user(update.effective_user.id)
    lang = u["language"] if u else "uz"
    t = tx(lang)
    nl = context.user_data.get("nl",{})
    if step == "price":
        text = update.message.text.replace("$","").strip()
        if not text.isdigit():
            await update.message.reply_text("Narxni raqamda kiriting:")
            return
        nl["price"] = int(text)
        context.user_data["nl"] = nl
        context.user_data["nl_step"] = "description"
        await update.message.reply_text(t["ask_description"],reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t["btn_skip"],callback_data="nl_skip_desc")]]))
    elif step == "description":
        nl["description"] = update.message.text
        context.user_data["nl"] = nl
        context.user_data["nl_step"] = "photos"
        await update.message.reply_text(t["ask_photos"],reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t["btn_skip"],callback_data="nl_skip_photos")]]))
    elif step == "photos":
        if update.message.photo:
            photos = context.user_data.get("nl_photos",[])
            photos.append(update.message.photo[-1].file_id)
            context.user_data["nl_photos"] = photos
            if len(photos) >= 10:
                context.user_data["nl_step"] = "address"
                await update.message.reply_text(t["ask_address"])
            else:
                await update.message.reply_text("Rasm qabul qilindi.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"Tayyor ({len(photos)} ta)",callback_data="nl_photos_done")]]))
    elif step == "address":
        nl["address"] = update.message.text
        context.user_data["nl"] = nl
        context.user_data["nl_step"] = "phone"
        await update.message.reply_text(t["ask_phone"])
    elif step == "phone":
        phone = update.message.contact.phone_number if update.message.contact else update.message.text
        nl["phone"] = phone
        nl["photos"] = context.user_data.get("nl_photos",[])
        nl["source"] = "bot"
        nl["user_id"] = u["id"]
        nl["is_active"] = False
        add_listing(nl)
        context.user_data.pop("nl",None)
        context.user_data.pop("nl_step",None)
        context.user_data.pop("nl_photos",None)
        await update.message.reply_text(t["listing_saved"])

async def settings_start(update,context):
    u = get_user(update.effective_user.id)
    lang = u["language"] if u else "uz"
    t = tx(lang)
    sub = get_sub(u["id"]) or {}
    is_active = sub.get("is_active",True)
    only_cheap = sub.get("only_cheap",False)
    freq = sub.get("notify_freq","daily")
    daily_limit = sub.get("daily_limit",5)
    fl = NOTIFY_FREQ[lang]
    limit_label = t["limit_unlimited"] if daily_limit==0 else f"{daily_limit} ta"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(t["notif_on"] if is_active else t["notif_off"],callback_data="set_notif")],[InlineKeyboardButton(t["only_cheap_on"] if only_cheap else t["only_cheap_off"],callback_data="set_cheap")],[InlineKeyboardButton(fl[freq],callback_data="set_freq")],[InlineKeyboardButton(f"Limit: {limit_label}",callback_data="set_limit")],[InlineKeyboardButton("Tilni ozgartirish",callback_data="set_lang")]])
    await update.message.reply_text(t["settings_title"],reply_markup=kb)

async def cb_settings(update,context):
    q = update.callback_query
    await q.answer()
    d = q.data
    u = get_user(q.from_user.id)
    lang = u["language"] if u else "uz"
    t = tx(lang)
    sub = get_sub(u["id"]) or {}
    if d == "set_notif": save_sub(u["id"],{"is_active":not sub.get("is_active",True)})
    elif d == "set_cheap": save_sub(u["id"],{"only_cheap":not sub.get("only_cheap",False)})
    elif d == "set_freq":
        fl = NOTIFY_FREQ[lang]
        await q.edit_message_text(t["choose_freq"],reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(fl["instant"],callback_data="sf_instant")],[InlineKeyboardButton(fl["daily"],callback_data="sf_daily")],[InlineKeyboardButton(fl["weekly"],callback_data="sf_weekly")]]))
        return
    elif d.startswith("sf_"): save_sub(u["id"],{"notify_freq":d.replace("sf_","")})
    elif d == "set_limit":
        await q.edit_message_text(t["choose_limit"],reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(t["limit_unlimited"] if l==0 else f"{l} ta",callback_data=f"sl_{l}")] for l in DAILY_LIMITS]))
        return
    elif d.startswith("sl_"): save_sub(u["id"],{"daily_limit":int(d.replace("sl_",""))})
    elif d == "set_lang":
        await q.edit_message_text(t["choose_language"],reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("O'zbek",callback_data="lang_uz"),InlineKeyboardButton("Русский",callback_data="lang_ru"),InlineKeyboardButton("English",callback_data="lang_en")]]))
        return
    sub2 = get_sub(u["id"]) or {}
    is_active = sub2.get("is_active",True)
    only_cheap = sub2.get("only_cheap",False)
    freq = sub2.get("notify_freq","daily")
    daily_limit = sub2.get("daily_limit",5)
    fl = NOTIFY_FREQ[lang]
    limit_label = t["limit_unlimited"] if daily_limit==0 else f"{daily_limit} ta"
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(t["notif_on"] if is_active else t["notif_off"],callback_data="set_notif")],[InlineKeyboardButton(t["only_cheap_on"] if only_cheap else t["only_cheap_off"],callback_data="set_cheap")],[InlineKeyboardButton(fl[freq],callback_data="set_freq")],[InlineKeyboardButton(f"Limit: {limit_label}",callback_data="set_limit")],[InlineKeyboardButton("Tilni ozgartirish",callback_data="set_lang")]])
    await q.edit_message_text(t["settings_title"],reply_markup=kb)


# Flask health server
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "UyBot ishlayapti!"


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("add", add_start))
    app.add_handler(CommandHandler("settings", settings_start))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(cb_lang, pattern="^lang_"))
    app.add_handler(CallbackQueryHandler(cb_search, pattern="^(s_city_|s_deal_|s_rooms_|s_price_|s_page_)"))
    app.add_handler(CallbackQueryHandler(cb_listing, pattern="^nl_"))
    app.add_handler(CallbackQueryHandler(cb_settings, pattern="^(set_|sf_|sl_)"))
    app.add_handler(MessageHandler(filters.Regex("^(Qidiruv|Poisk|Search)$"), search_start))
    app.add_handler(MessageHandler(filters.Regex("^(Elon berish|Dobavit|Add listing)$"), add_start))
    app.add_handler(MessageHandler(filters.Regex("^(Sozlamalar|Nastroyki|Settings)$"), settings_start))
    app.add_handler(MessageHandler(filters.Regex("^(Yordam|Pomosh|Help)$"), cmd_help))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.CONTACT, msg_handler))

    port = int(os.environ.get("PORT", 5000))
    threading.Thread(
        target=lambda: flask_app.run(host="0.0.0.0", port=port),
        daemon=True
    ).start()

    logging.info("UyBot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
