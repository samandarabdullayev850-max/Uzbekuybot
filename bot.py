import os
import logging
import requests as req
import threading
import time
from bs4 import BeautifulSoup
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEBHOOK_URL = "https://uybot.onrender.com"

ADMIN_IDS = [8726418671]
REQUIRED_CHANNEL = None  # Keyinchalik qo'shiladi: "@kanal_username"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

app = Flask(__name__)

# ===================== SUPABASE =====================
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def sb_get(table, filters=""):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filters}"
    r = req.get(url, headers=HEADERS)
    return r.json() if r.ok else []

def sb_post(table, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    r = req.post(url, headers=HEADERS, json=data)
    return r.json() if r.ok else None

def sb_patch(table, filters, data):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filters}"
    r = req.patch(url, headers=HEADERS, json=data)
    return r.ok

def sb_delete(table, filters):
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filters}"
    r = req.delete(url, headers=HEADERS)
    return r.ok

def sb_count(table, filters=""):
    h = dict(HEADERS)
    h["Prefer"] = "count=exact"
    url = f"{SUPABASE_URL}/rest/v1/{table}?{filters}&select=id"
    r = req.get(url, headers=h)
    cr = r.headers.get("content-range", "0/0")
    try:
        return int(cr.split("/")[1])
    except:
        return 0

# ===================== TELEGRAM =====================
def tg(method, data):
    return req.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=data, timeout=15)

def send(chat_id, text, kb=None, parse_mode="HTML"):
    data = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if kb:
        data["reply_markup"] = {"inline_keyboard": kb}
    tg("sendMessage", data)

def send_photo(chat_id, photo, caption=None, kb=None):
    data = {"chat_id": chat_id, "photo": photo, "parse_mode": "HTML"}
    if caption: data["caption"] = caption
    if kb: data["reply_markup"] = {"inline_keyboard": kb}
    tg("sendPhoto", data)

def answer_cb(cb_id):
    tg("answerCallbackQuery", {"callback_query_id": cb_id})

def set_webhook():
    tg("setWebhook", {"url": f"{WEBHOOK_URL}/webhook"})

def get_chat_member(chat_id, user_id):
    r = req.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember",
                params={"chat_id": chat_id, "user_id": user_id}, timeout=5)
    return r.json().get("result", {}).get("status", "")

# ===================== DB HELPERS =====================
def get_user(tid):
    data = sb_get("users", f"telegram_id=eq.{tid}&select=*")
    return data[0] if data else None

def get_or_create_user(tid, name, username=None):
    u = get_user(tid)
    if not u:
        sb_post("users", {"telegram_id": tid, "full_name": name, "username": username, "language": "uz", "is_banned": False})
        u = get_user(tid)
    return u

def update_lang(tid, lang):
    sb_patch("users", f"telegram_id=eq.{tid}", {"language": lang})

def get_all_users():
    return sb_get("users", "select=telegram_id,is_banned")

def get_admins():
    data = sb_get("admins", "select=telegram_id")
    ids = [d["telegram_id"] for d in data] if data else []
    ids += ADMIN_IDS
    return list(set(ids))

def is_admin(uid):
    return uid in get_admins()

def add_admin(tid):
    existing = sb_get("admins", f"telegram_id=eq.{tid}")
    if not existing:
        sb_post("admins", {"telegram_id": tid})

def remove_admin(tid):
    sb_delete("admins", f"telegram_id=eq.{tid}")

def get_listings_db(city=None, deal_type=None, rooms=None, price_min=None, price_max=None, offset=0, limit=3):
    f = "is_active=eq.true&select=*&order=published_at.desc"
    if city: f += f"&city=eq.{city}"
    if deal_type: f += f"&deal_type=eq.{deal_type}"
    if rooms:
        try:
            f += f"&rooms=eq.{int(rooms)}"
        except:
            pass
    if price_min is not None: f += f"&price=gte.{price_min}"
    if price_max is not None: f += f"&price=lte.{price_max}"
    f += f"&offset={offset}&limit={limit}"
    return sb_get("listings", f)

def count_listings_db(city=None, deal_type=None, rooms=None, price_min=None, price_max=None):
    f = "is_active=eq.true"
    if city: f += f"&city=eq.{city}"
    if deal_type: f += f"&deal_type=eq.{deal_type}"
    if rooms:
        try:
            f += f"&rooms=eq.{int(rooms)}"
        except:
            pass
    if price_min is not None: f += f"&price=gte.{price_min}"
    if price_max is not None: f += f"&price=lte.{price_max}"
    return sb_count("listings", f)

def get_pending_listings():
    return sb_get("listings", "is_active=eq.false&source=eq.bot&select=*&order=published_at.desc")

def approve_listing(lid):
    sb_patch("listings", f"id=eq.{lid}", {"is_active": True})

def delete_listing(lid):
    sb_delete("listings", f"id=eq.{lid}")

def add_listing(data):
    return sb_post("listings", data)

def get_sub(uid):
    data = sb_get("subscriptions", f"user_id=eq.{uid}&select=*")
    return data[0] if data else None

def save_sub(uid, data):
    if get_sub(uid):
        sb_patch("subscriptions", f"user_id=eq.{uid}", data)
    else:
        data["user_id"] = uid
        sb_post("subscriptions", data)

def log_search(uid, city, deal_type, rooms):
    sb_post("search_logs", {"user_id": uid, "city": city, "deal_type": deal_type, "rooms": rooms})

# ===================== CONSTANTS =====================
CITIES = ["Toshkent","Samarqand","Buxoro","Namangan","Andijon","Fargona","Nukus","Qarshi","Termiz"]
CITY_EMOJI = {
    "Toshkent": "🏙",
    "Samarqand": "🏛",
    "Buxoro": "🕌",
    "Namangan": "🌿",
    "Andijon": "🌄",
    "Fargona": "🌸",
    "Nukus": "🏜",
    "Qarshi": "🌾",
    "Termiz": "☀️"
}
DEAL_TYPES = {"uz":["Ijaraga","Sotuvga"],"ru":["Arenda","Prodaja"],"en":["Rent","Sale"]}
ROOMS = ["1","2","3","4","5+"]
PRICE_RANGES_RENT = [(0,300),(300,600),(600,1000),(1000,2000),(2000,99999)]
PRICE_LABELS_RENT = ["💵 $0-300","💵 $300-600","💵 $600-1000","💵 $1000-2000","💵 $2000+"]
PRICE_RANGES_SALE = [(0,10000),(10000,30000),(30000,60000),(60000,100000),(100000,9999999)]
PRICE_LABELS_SALE = ["💰 $0-10,000","💰 $10,000-30,000","💰 $30,000-60,000","💰 $60,000-100,000","💰 $100,000+"]
NOTIFY_FREQ = {"uz":{"instant":"Darhol","daily":"Kuniga 1","weekly":"Haftada 1"},"ru":{"instant":"Srazu","daily":"Raz v den","weekly":"Raz v nedelyu"},"en":{"instant":"Instantly","daily":"Once a day","weekly":"Once a week"}}
DAILY_LIMITS = [3,5,10,0]

WELCOME = {
    "uz": """🏠 <b>UyBot ga xush kelibsiz!</b>

O'zbekistonda uy-joy izlash hech qachon bu qadar oson bo'lmagan!

🔍 Uy qidiring
📢 Elon bering
🔔 Yangi elonlardan xabardor bo'ling""",
    "ru": """🏠 <b>Добро пожаловать в UyBot!</b>

Поиск жилья в Узбекистане ещё никогда не был таким простым!

🔍 Ищите жильё
📢 Подавайте объявления
🔔 Получайте уведомления о новых объявлениях""",
    "en": """🏠 <b>Welcome to UyBot!</b>

Finding housing in Uzbekistan has never been this easy!

🔍 Search for homes
📢 Post listings
🔔 Get notified about new listings"""
}

UZ = {"choose_language":"🌍 Tilni tanlang:","welcome":"🏠 <b>UyBot ga xush kelibsiz!</b>\n\nO'zbekistonda uy-joy izlash hech qachon bu qadar oson bo'lmagan!\n\n🔍 Uy qidiring\n📢 Elon bering\n🔔 Yangi elonlardan xabardor bo'ling","btn_search":"🔍 Qidiruv","btn_my_listings":"📋 Mening elonlarim","btn_add_listing":"📢 Elon berish","btn_settings":"⚙️ Sozlamalar","btn_help":"❓ Yordam","choose_city":"📍 Qaysi shaharda?","choose_deal":"🏠 Nima qidirmoqdasiz?","choose_rooms":"🚪 Nechta xona?","choose_price":"💰 Narx oraligi?","no_results":"😔 Hech narsa topilmadi.","btn_next":"Keyingi ➡️","btn_prev":"⬅️ Oldingi","btn_cancel":"❌ Bekor","btn_skip":"⏭ O'tkazib yuborish","ask_deal":"🏠 Ijara yoki sotish?","ask_city":"📍 Qaysi shahar?","ask_rooms":"🚪 Nechta xona?","ask_price":"💰 Narx ($):","ask_description":"📝 Tavsif:","ask_photos":"📸 Rasm yuboring:","ask_address":"📍 Manzil:","ask_phone":"📞 Telefon:","listing_saved":"✅ Elon saqlandi! Admin tekshirgandan so'ng e'lon qilinadi.","settings_title":"⚙️ Sozlamalar:","notif_on":"🔔 Xabar: Yoqilgan","notif_off":"🔕 Xabar: O'chirilgan","choose_freq":"⏰ Qanchalik tez?","choose_limit":"📊 Kuniga nechta?","limit_unlimited":"♾ Cheksiz","only_cheap_on":"💚 Arzon: Ha","only_cheap_off":"💚 Arzon: Yo'q","help_text":"👨‍💻 Murojaat uchun: @samandarbotdev","stats_title":"📊 Statistika:","stats_users":"👥 Foydalanuvchilar: {count}","stats_listings":"📋 Elonlar: {count}","stats_active":"✅ Faol elonlar: {count}","stats_subs":"🔔 Faol obunalar: {count}"}
RU = {"choose_language":"🌍 Tilni tanlang:","welcome":"🏠 <b>Добро пожаловать в UyBot!</b>\n\nПоиск жилья в Узбекистане ещё никогда не был таким простым!\n\n🔍 Ищите жильё\n📢 Подавайте объявления\n🔔 Получайте уведомления","btn_search":"🔍 Poisk","btn_my_listings":"📋 Moi obyavleniya","btn_add_listing":"📢 Dobavit","btn_settings":"⚙️ Nastroyki","btn_help":"❓ Pomosh","choose_city":"📍 Gorod?","choose_deal":"🏠 Chto ischete?","choose_rooms":"🚪 Komnaty?","choose_price":"💰 Tsena?","no_results":"😔 Ne naydeno.","btn_next":"Dalee ➡️","btn_prev":"⬅️ Nazad","btn_cancel":"❌ Otmena","btn_skip":"⏭ Propustit","ask_deal":"🏠 Arenda ili prodazha?","ask_city":"📍 Gorod?","ask_rooms":"🚪 Komnaty?","ask_price":"💰 Tsena ($):","ask_description":"📝 Opisanie:","ask_photos":"📸 Foto:","ask_address":"📍 Adres:","ask_phone":"📞 Telefon:","listing_saved":"✅ Sokhraneno! Admin proverit.","settings_title":"⚙️ Nastroyki:","notif_on":"🔔 Uvedomleniya: Vkl","notif_off":"🔕 Uvedomleniya: Otkl","choose_freq":"⏰ Kak chasto?","choose_limit":"📊 Maks v den?","limit_unlimited":"♾ Bez limita","only_cheap_on":"💚 Deshevle: Da","only_cheap_off":"💚 Deshevle: Net","help_text":"👨‍💻 Murojaat uchun: @samandarbotdev","stats_title":"📊 Statistika:","stats_users":"👥 Polzovateli: {count}","stats_listings":"📋 Obyavleniya: {count}","stats_active":"✅ Aktivnye: {count}","stats_subs":"🔔 Podpiski: {count}"}
EN = {"choose_language":"🌍 Choose language:","welcome":"🏠 <b>Welcome to UyBot!</b>\n\nFinding housing in Uzbekistan has never been this easy!\n\n🔍 Search for homes\n📢 Post listings\n🔔 Get notified","btn_search":"🔍 Search","btn_my_listings":"📋 My listings","btn_add_listing":"📢 Add listing","btn_settings":"⚙️ Settings","btn_help":"❓ Help","choose_city":"📍 City?","choose_deal":"🏠 Looking for?","choose_rooms":"🚪 Rooms?","choose_price":"💰 Price?","no_results":"😔 Nothing found.","btn_next":"Next ➡️","btn_prev":"⬅️ Previous","btn_cancel":"❌ Cancel","btn_skip":"⏭ Skip","ask_deal":"🏠 Rent or sale?","ask_city":"📍 City?","ask_rooms":"🚪 Rooms?","ask_price":"💰 Price ($):","ask_description":"📝 Description:","ask_photos":"📸 Photos:","ask_address":"📍 Address:","ask_phone":"📞 Phone:","listing_saved":"✅ Saved! Admin will review.","settings_title":"⚙️ Settings:","notif_on":"🔔 Notifications: On","notif_off":"🔕 Notifications: Off","choose_freq":"⏰ How often?","choose_limit":"📊 Max per day?","limit_unlimited":"♾ Unlimited","only_cheap_on":"💚 Cheap only: Yes","only_cheap_off":"💚 Cheap only: No","help_text":"👨‍💻 Contact: @samandarbotdev","stats_title":"📊 Statistics:","stats_users":"👥 Users: {count}","stats_listings":"📋 Listings: {count}","stats_active":"✅ Active: {count}","stats_subs":"🔔 Subscriptions: {count}"}

def tx(lang): return {"uz":UZ,"ru":RU,"en":EN}.get(lang, UZ)

def main_menu_kb(lang):
    menus = {
        "uz": [["🔍 Qidiruv"], ["📢 Elon berish", "📋 Mening elonlarim"], ["⚙️ Sozlamalar", "❓ Yordam"]],
        "ru": [["🔍 Поиск"], ["📢 Добавить", "📋 Мои объявления"], ["⚙️ Настройки", "❓ Помощь"]],
        "en": [["🔍 Search"], ["📢 Add listing", "📋 My listings"], ["⚙️ Settings", "❓ Help"]]
    }
    cbs = [["menu_search"], ["menu_add", "menu_mylist"], ["menu_settings", "menu_help"]]
    labels = menus.get(lang, menus["uz"])
    kb = []
    for row_labels, row_cbs in zip(labels, cbs):
        row = [{"text": lbl, "callback_data": cb} for lbl, cb in zip(row_labels, row_cbs)]
        kb.append(row)
    return kb

# User state
user_state = {}

def get_state(uid): return user_state.get(uid, {})
def set_state(uid, data): user_state[uid] = data
def clear_state(uid): user_state.pop(uid, None)

# ===================== OBUNA TEKSHIRISH =====================
def check_subscription(uid):
    if not REQUIRED_CHANNEL:
        return True
    status = get_chat_member(REQUIRED_CHANNEL, uid)
    return status in ["member", "administrator", "creator"]

def ask_subscribe(chat_id):
    kb = [[{"text": "📢 Kanalga o'tish", "url": f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}"}],
          [{"text": "✅ Obuna bo'ldim", "callback_data": "check_sub"}]]
    send(chat_id, "⚠️ Botdan foydalanish uchun kanalga obuna bo'ling!", kb)

# ===================== ELON FORMATI =====================
def format_listing(l, lang="uz"):
    deal_map = {
        "uz": {"rent": "Ijara", "sale": "Sotish"},
        "ru": {"rent": "Arenda", "sale": "Prodaja"},
        "en": {"rent": "Rent", "sale": "Sale"}
    }
    suffix_map = {
        "uz": "/oy",
        "ru": "/mes",
        "en": "/mo"
    }
    rooms_label = {"uz": "xonali uy", "ru": "комн. кв.", "en": "room apt"}.get(lang, "xonali uy")
    deal = deal_map.get(lang, deal_map["uz"]).get(l.get("deal_type", "rent"), "Ijara")
    rooms = l.get("rooms", "")
    city = l.get("city", "")
    address = l.get("address", "")
    price = l.get("price", "")
    phone = l.get("phone", "")
    description = l.get("description", "")

    location = city
    if address:
        location = f"{city}, {address}"

    text = f"🏠 <b>{rooms} {rooms_label} — {deal}</b>\n"
    text += f"📍 {location}\n"
    if price:
        suffix = suffix_map.get(lang, "/oy") if l.get("deal_type") == "rent" else ""
        text += f"💰 ${price}{suffix}\n"
    if description:
        text += f"📝 {description}\n"
    if phone:
        text += f"📞 {phone}"
    return text

# ===================== QIDIRUV NATIJALARI =====================
def show_results(chat_id, state, lang, page):
    t = tx(lang)
    s = state.get("search_params", {})
    listings = get_listings_db(
        city=s.get("city"), deal_type=s.get("deal_type"),
        rooms=s.get("rooms"), price_min=s.get("price_min"),
        price_max=s.get("price_max"), offset=page*3, limit=3
    )
    total = count_listings_db(
        city=s.get("city"), deal_type=s.get("deal_type"),
        rooms=s.get("rooms"), price_min=s.get("price_min"),
        price_max=s.get("price_max")
    )
    if not listings:
        send(chat_id, t["no_results"], [[{"text": "🏠 Bosh menyu", "callback_data": "menu_main"}]])
        return
    nav = []
    if page > 0: nav.append({"text": t["btn_prev"], "callback_data": f"s_page_{page-1}"})
    if (page+1)*3 < total: nav.append({"text": t["btn_next"], "callback_data": f"s_page_{page+1}"})

    for i, l in enumerate(listings):
        text = format_listing(l, lang)
        kb = [nav] if nav and i == len(listings)-1 else None
        photos = l.get("photos") or []
        if photos:
            send_photo(chat_id, photos[0], text, kb)
        else:
            send(chat_id, text, kb)

# ===================== ADMIN PANEL =====================
def admin_menu(chat_id):
    kb = [
        [{"text": "📊 Statistika", "callback_data": "adm_stats"}],
        [{"text": "📋 Kutayotgan elonlar", "callback_data": "adm_pending"}],
        [{"text": "📣 Broadcast", "callback_data": "adm_broadcast"}],
        [{"text": "👥 Admin qo'shish", "callback_data": "adm_addadmin"}],
        [{"text": "❌ Admin o'chirish", "callback_data": "adm_removeadmin"}],
        [{"text": "📢 Kanal o'rnatish", "callback_data": "adm_setchannel"}],
    ]
    send(chat_id, "🔧 <b>Admin panel</b>", kb)

def admin_stats(chat_id):
    users = sb_count("users")
    listings = sb_count("listings")
    active = sb_count("listings", "is_active=eq.true")
    pending = sb_count("listings", "is_active=eq.false&source=eq.bot")
    today_users = sb_count("users", "created_at=gte." + time.strftime("%Y-%m-%d"))

    # Qidiruv logi
    logs = sb_get("search_logs", "select=city&order=created_at.desc&limit=100")
    city_count = {}
    for log in logs:
        c = log.get("city", "Noma'lum")
        city_count[c] = city_count.get(c, 0) + 1
    top_cities = sorted(city_count.items(), key=lambda x: x[1], reverse=True)[:3]
    top_text = "\n".join([f"  • {c}: {n} marta" for c, n in top_cities]) if top_cities else "  Yo'q"

    text = f"""📊 <b>Batafsil statistika</b>

👥 Jami foydalanuvchilar: <b>{users}</b>
🆕 Bugun qo'shildi: <b>{today_users}</b>
📋 Jami elonlar: <b>{listings}</b>
✅ Faol elonlar: <b>{active}</b>
⏳ Tasdiq kutayapti: <b>{pending}</b>

🔍 Ko'p qidiriladigan shaharlar:
{top_text}"""

    send(chat_id, text, [[{"text": "◀️ Orqaga", "callback_data": "adm_menu"}]])

def show_pending(chat_id):
    listings = get_pending_listings()
    if not listings:
        send(chat_id, "✅ Tasdiq kutayotgan elon yo'q.", [[{"text": "◀️ Orqaga", "callback_data": "adm_menu"}]])
        return
    for l in listings[:5]:
        text = format_listing(l, lang)
        text += f"\n\n🆔 ID: {l['id']}"
        kb = [[
            {"text": "✅ Tasdiqlash", "callback_data": f"adm_approve_{l['id']}"},
            {"text": "❌ O'chirish", "callback_data": f"adm_delete_{l['id']}"}
        ]]
        photos = l.get("photos") or []
        if photos:
            send_photo(chat_id, photos[0], text, kb)
        else:
            send(chat_id, text, kb)

# ===================== OLX SCRAPING =====================
def scrape_olx():
    try:
        cities = {
            "Toshkent": "tashkent",
            "Samarqand": "samarkand",
            "Buxoro": "bukhara",
        }
        for city_uz, city_en in cities.items():
            url = f"https://www.olx.uz/nedvizhimost/kvartiry/sdam/{city_en}/"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            r = req.get(url, headers=headers, timeout=15)
            if not r.ok:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("[data-cy='l-card']")[:10]
            for card in cards:
                try:
                    title_el = card.select_one("[data-cy='ad-card-title']")
                    price_el = card.select_one("[data-testid='ad-price']")
                    img_el = card.select_one("img")
                    link_el = card.select_one("a")

                    title = title_el.text.strip() if title_el else ""
                    price_text = price_el.text.strip() if price_el else ""
                    photo = img_el.get("src", "") if img_el else ""
                    link = "https://www.olx.uz" + link_el.get("href", "") if link_el else ""

                    # Narxni ajratib olish
                    price = 0
                    for word in price_text.replace(",", "").split():
                        if word.isdigit():
                            price = int(word)
                            break

                    # Duplicate tekshirish
                    existing = sb_get("listings", f"source=eq.olx&title=eq.{title}&city=eq.{city_uz}")
                    if existing:
                        continue

                    listing_data = {
                        "title": title,
                        "city": city_uz,
                        "deal_type": "rent",
                        "price": price,
                        "photos": [photo] if photo else [],
                        "source": "olx",
                        "is_active": True,
                        "phone": "",
                        "description": f"OLX: {link}"
                    }
                    sb_post("listings", listing_data)
                except Exception as e:
                    logging.error(f"OLX card xatosi: {e}")
        logging.info("OLX scraping tugadi")
    except Exception as e:
        logging.error(f"OLX scraping xatosi: {e}")

def olx_scheduler():
    while True:
        scrape_olx()
        time.sleep(1800)  # 30 daqiqada bir

# ===================== WEBHOOK =====================
@app.route("/webhook", methods=["POST"])
def webhook():
    global REQUIRED_CHANNEL
    d = request.json
    if not d:
        return "ok"

    if "callback_query" in d:
        cb = d["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        uid = cb["from"]["id"]
        data = cb["data"]
        answer_cb(cb["id"])

        u = get_user(uid)
        lang = u["language"] if u else "uz"
        t = tx(lang)
        state = get_state(chat_id)

        # Obuna tekshirish
        if data == "check_sub":
            if check_subscription(uid):
                handle_main_menu(chat_id, lang)
            else:
                ask_subscribe(chat_id)
            return "ok"

        # Admin panel
        if data == "adm_menu" and is_admin(uid):
            admin_menu(chat_id)
            return "ok"
        if data == "adm_stats" and is_admin(uid):
            admin_stats(chat_id)
            return "ok"
        if data == "adm_pending" and is_admin(uid):
            show_pending(chat_id)
            return "ok"
        if data == "adm_broadcast" and is_admin(uid):
            set_state(uid, {"admin_flow": "broadcast"})
            send(chat_id, "📣 Broadcast xabarini yozing:", [[{"text": "❌ Bekor", "callback_data": "adm_menu"}]])
            return "ok"
        if data == "adm_addadmin" and is_admin(uid):
            set_state(uid, {"admin_flow": "addadmin"})
            send(chat_id, "👤 Yangi admin Telegram ID sini yozing:", [[{"text": "❌ Bekor", "callback_data": "adm_menu"}]])
            return "ok"
        if data == "adm_removeadmin" and is_admin(uid):
            set_state(uid, {"admin_flow": "removeadmin"})
            send(chat_id, "👤 O'chiriladigan admin ID sini yozing:", [[{"text": "❌ Bekor", "callback_data": "adm_menu"}]])
            return "ok"
        if data == "adm_setchannel" and is_admin(uid):
            set_state(uid, {"admin_flow": "setchannel"})
            send(chat_id, "📢 Kanal username ni yozing (masalan @kanal_uz):\n\nO'chirish uchun: off", [[{"text": "❌ Bekor", "callback_data": "adm_menu"}]])
            return "ok"
        if data.startswith("adm_approve_") and is_admin(uid):
            lid = int(data.replace("adm_approve_", ""))
            approve_listing(lid)
            send(chat_id, "✅ Elon tasdiqlandi!")
            return "ok"
        if data.startswith("adm_delete_") and is_admin(uid):
            lid = int(data.replace("adm_delete_", ""))
            delete_listing(lid)
            send(chat_id, "🗑 Elon o'chirildi!")
            return "ok"

        # Asosiy menyu
        if data == "menu_main":
            clear_state(chat_id)
            handle_main_menu(chat_id, lang)
        elif data == "menu_search":
            if REQUIRED_CHANNEL and not check_subscription(uid):
                ask_subscribe(chat_id)
                return "ok"
            handle_search(chat_id, lang)
        elif data == "menu_add":
            if REQUIRED_CHANNEL and not check_subscription(uid):
                ask_subscribe(chat_id)
                return "ok"
            handle_add(chat_id, lang)
        elif data == "menu_settings":
            handle_settings(chat_id, uid, lang)
        elif data == "menu_help":
            send(chat_id, t["help_text"], [[{"text": "◀️ Orqaga", "callback_data": "menu_main"}]])
        elif data == "menu_mylist":
            u2 = get_user(uid)
            if u2:
                my = sb_get("listings", f"user_id=eq.{u2['id']}&select=*&order=published_at.desc&limit=5")
                if my:
                    for l in my:
                        status = "✅ Faol" if l.get("is_active") else "⏳ Tekshirilmoqda"
                        text = format_listing(l, lang) + f"\n\n{status}"
                        photos = l.get("photos") or []
                        if photos:
                            send_photo(chat_id, photos[0], text)
                        else:
                            send(chat_id, text)
                else:
                    send(chat_id, "📋 Sizda hali elon yo'q.", [[{"text": "📢 Elon berish", "callback_data": "menu_add"}]])

        # Til
        elif data.startswith("lang_"):
            new_lang = data.split("_")[1]
            update_lang(uid, new_lang)
            lang = new_lang  # update local lang variable
            t = tx(lang)    # refresh translations
            handle_main_menu(chat_id, new_lang)

        # Qidiruv
        elif data.startswith("s_city_"):
            city = data.replace("s_city_", "")
            state = {"flow": "search", "step": "deal", "search_params": {"city": city}}
            set_state(chat_id, state)
            btns = [[
                {"text": "🏠 " + DEAL_TYPES[lang][0], "callback_data": "s_deal_rent"},
                {"text": "🏷 " + DEAL_TYPES[lang][1], "callback_data": "s_deal_sale"}
            ]]
            header = {"uz": f"🔍 Qidiruv — 2/4 qadam\n\n📍 Shahar: {city}\n\n🏠 Nima qidirmoqdasiz?", "ru": f"🔍 Поиск — шаг 2/4\n\n📍 Город: {city}\n\n🏠 Что ищете?", "en": f"🔍 Search — step 2/4\n\n📍 City: {city}\n\n🏠 What are you looking for?"}.get(lang, t["choose_deal"])
            send(chat_id, header, btns)
        elif data.startswith("s_deal_"):
            deal = data.replace("s_deal_", "")
            state["search_params"]["deal_type"] = deal
            state["step"] = "rooms"
            set_state(chat_id, state)
            deal_label = {"rent": {"uz":"Ijara","ru":"Arenda","en":"Rent"}, "sale": {"uz":"Sotish","ru":"Prodaja","en":"Sale"}}.get(deal, {}).get(lang, deal)
            btns = [[{"text": f"🚪 {r}", "callback_data": f"s_rooms_{r}"} for r in ROOMS]]
            header = {"uz": f"🔍 Qidiruv — 3/4 qadam\n\n🏠 Tur: {deal_label}\n\n🚪 Nechta xona?", "ru": f"🔍 Поиск — шаг 3/4\n\n🏠 Тип: {deal_label}\n\n🚪 Количество комнат?", "en": f"🔍 Search — step 3/4\n\n🏠 Type: {deal_label}\n\n🚪 Number of rooms?"}.get(lang, t["choose_rooms"])
            send(chat_id, header, btns)
        elif data.startswith("s_rooms_"):
            rooms = data.replace("s_rooms_", "")
            state["search_params"]["rooms"] = rooms
            state["step"] = "price"
            set_state(chat_id, state)
            deal = state["search_params"].get("deal_type", "rent")
            if deal == "sale":
                price_labels = PRICE_LABELS_SALE
                price_key = "sale"
            else:
                price_labels = PRICE_LABELS_RENT
                price_key = "rent"
            state["search_params"]["price_key"] = price_key
            btns = [[{"text": p, "callback_data": f"s_price_{i}"}] for i, p in enumerate(price_labels)]
            header = {"uz": f"🔍 Qidiruv — 4/4 qadam\n\n🚪 Xona: {rooms}\n\n💰 Narx oralig'ini tanlang:", "ru": f"🔍 Поиск — шаг 4/4\n\n🚪 Комнат: {rooms}\n\n💰 Выберите диапазон цен:", "en": f"🔍 Search — step 4/4\n\n🚪 Rooms: {rooms}\n\n💰 Select price range:"}.get(lang, t["choose_price"])
            send(chat_id, header, btns)
        elif data.startswith("s_price_"):
            idx = int(data.replace("s_price_", ""))
            price_key = state["search_params"].get("price_key", "rent")
            ranges = PRICE_RANGES_SALE if price_key == "sale" else PRICE_RANGES_RENT
            state["search_params"]["price_min"], state["search_params"]["price_max"] = ranges[idx]
            state["step"] = "results"
            set_state(chat_id, state)
            u2 = get_user(uid)
            if u2:
                s = state["search_params"]
                log_search(u2["id"], s.get("city"), s.get("deal_type"), s.get("rooms"))
            send(chat_id, "🔍 Qidirilmoqda...")
            show_results(chat_id, state, lang, 0)
        elif data.startswith("s_page_"):
            page = int(data.replace("s_page_", ""))
            show_results(chat_id, state, lang, page)

        # Elon berish
        elif data.startswith("nl_deal_"):
            deal = data.replace("nl_deal_", "")
            state["nl"]["deal_type"] = deal
            state["step"] = "city"
            set_state(chat_id, state)
            btns = [[{"text": c, "callback_data": f"nl_city_{c}"}] for c in CITIES]
            btns.append([{"text": t["btn_cancel"], "callback_data": "menu_main"}])
            send(chat_id, t["ask_city"], btns)
        elif data.startswith("nl_city_"):
            city = data.replace("nl_city_", "")
            state["nl"]["city"] = city
            state["step"] = "rooms"
            set_state(chat_id, state)
            btns = [[{"text": str(r), "callback_data": f"nl_rooms_{r}"} for r in [1,2,3,4,5]]]
            btns.append([{"text": t["btn_cancel"], "callback_data": "menu_main"}])
            send(chat_id, t["ask_rooms"], btns)
        elif data.startswith("nl_rooms_"):
            state["nl"]["rooms"] = int(data.replace("nl_rooms_", ""))
            state["step"] = "price"
            set_state(chat_id, state)
            send(chat_id, t["ask_price"])
        elif data == "nl_skip_desc":
            state["nl"]["description"] = None
            state["step"] = "photos"
            set_state(chat_id, state)
            send(chat_id, t["ask_photos"], [[{"text": t["btn_skip"], "callback_data": "nl_skip_photos"}]])
        elif data == "nl_skip_photos":
            state["step"] = "address"
            set_state(chat_id, state)
            send(chat_id, t["ask_address"], [[{"text": t["btn_skip"], "callback_data": "nl_skip_addr"}]])
        elif data == "nl_photos_done":
            state["step"] = "address"
            set_state(chat_id, state)
            send(chat_id, t["ask_address"], [[{"text": t["btn_skip"], "callback_data": "nl_skip_addr"}]])
        elif data == "nl_skip_addr":
            state["nl"]["address"] = None
            state["step"] = "phone"
            set_state(chat_id, state)
            send(chat_id, t["ask_phone"])

        # Sozlamalar
        elif data == "set_notif":
            u2 = get_user(uid)
            sub = get_sub(u2["id"]) or {}
            save_sub(u2["id"], {"is_active": not sub.get("is_active", True)})
            handle_settings(chat_id, uid, lang)
        elif data == "set_cheap":
            u2 = get_user(uid)
            sub = get_sub(u2["id"]) or {}
            save_sub(u2["id"], {"only_cheap": not sub.get("only_cheap", False)})
            handle_settings(chat_id, uid, lang)
        elif data == "set_freq":
            fl = NOTIFY_FREQ[lang]
            kb = [[{"text": fl["instant"], "callback_data": "sf_instant"}],
                  [{"text": fl["daily"], "callback_data": "sf_daily"}],
                  [{"text": fl["weekly"], "callback_data": "sf_weekly"}]]
            send(chat_id, t["choose_freq"], kb)
        elif data.startswith("sf_"):
            u2 = get_user(uid)
            save_sub(u2["id"], {"notify_freq": data.replace("sf_", "")})
            handle_settings(chat_id, uid, lang)
        elif data == "set_limit":
            t2 = tx(lang)
            kb = [[{"text": t2["limit_unlimited"] if l == 0 else f"{l} ta", "callback_data": f"sl_{l}"}] for l in DAILY_LIMITS]
            send(chat_id, t2["choose_limit"], kb)
        elif data.startswith("sl_"):
            u2 = get_user(uid)
            save_sub(u2["id"], {"daily_limit": int(data.replace("sl_", ""))})
            handle_settings(chat_id, uid, lang)
        elif data == "set_lang":
            kb = [[
                {"text": "O'zbek", "callback_data": "lang_uz"},
                {"text": "Русский", "callback_data": "lang_ru"},
                {"text": "English", "callback_data": "lang_en"}
            ]]
            send(chat_id, t["choose_language"], kb)

        return "ok"

    if "message" not in d:
        return "ok"

    msg = d["message"]
    chat_id = msg["chat"]["id"]
    uid = msg["from"]["id"]
    name = msg["from"].get("first_name", "Foydalanuvchi")
    username = msg["from"].get("username")
    text = msg.get("text", "")
    photo = msg.get("photo")
    contact = msg.get("contact")

    u = get_user(uid)
    lang = u["language"] if u else "uz"
    t = tx(lang)
    state = get_state(chat_id)

    # Admin flow
    admin_flow = state.get("admin_flow")
    if admin_flow and is_admin(uid):
        if admin_flow == "broadcast" and text:
            users = get_all_users()
            sent = 0
            for user in users:
                if not user.get("is_banned"):
                    try:
                        send(user["telegram_id"], text)
                        sent += 1
                    except:
                        pass
            clear_state(uid)
            send(chat_id, f"✅ {sent} ta foydalanuvchiga yuborildi!", [[{"text": "◀️ Orqaga", "callback_data": "adm_menu"}]])
            return "ok"
        elif admin_flow == "addadmin" and text:
            try:
                new_id = int(text.strip())
                add_admin(new_id)
                clear_state(uid)
                send(chat_id, f"✅ {new_id} admin qilindi!", [[{"text": "◀️ Orqaga", "callback_data": "adm_menu"}]])
            except:
                send(chat_id, "❌ Noto'g'ri ID!")
            return "ok"
        elif admin_flow == "removeadmin" and text:
            try:
                rem_id = int(text.strip())
                remove_admin(rem_id)
                clear_state(uid)
                send(chat_id, f"✅ {rem_id} admindan o'chirildi!", [[{"text": "◀️ Orqaga", "callback_data": "adm_menu"}]])
            except:
                send(chat_id, "❌ Noto'g'ri ID!")
            return "ok"
        elif admin_flow == "setchannel" and text:
            if text.strip().lower() == "off":
                REQUIRED_CHANNEL = None
                clear_state(uid)
                send(chat_id, "✅ Majburiy obuna o'chirildi!", [[{"text": "◀️ Orqaga", "callback_data": "adm_menu"}]])
            else:
                REQUIRED_CHANNEL = text.strip()
                clear_state(uid)
                send(chat_id, f"✅ Kanal o'rnatildi: {REQUIRED_CHANNEL}", [[{"text": "◀️ Orqaga", "callback_data": "adm_menu"}]])
            return "ok"

    # Komandalar
    if text == "/start":
        get_or_create_user(uid, name, username)
        if REQUIRED_CHANNEL and not check_subscription(uid):
            ask_subscribe(chat_id)
            return "ok"
        send(chat_id, UZ["choose_language"], [[
            {"text": "O'zbek", "callback_data": "lang_uz"},
            {"text": "Русский", "callback_data": "lang_ru"},
            {"text": "English", "callback_data": "lang_en"}
        ]])
        return "ok"

    if text == "/admin" and is_admin(uid):
        admin_menu(chat_id)
        return "ok"

    if text == "/help":
        send(chat_id, t["help_text"])
        return "ok"

    if text == "/stats" and is_admin(uid):
        admin_stats(chat_id)
        return "ok"

    # Elon berish flow
    flow = state.get("flow")
    step = state.get("step")

    if flow == "add":
        nl = state.get("nl", {})
        photos = state.get("photos", [])

        if step == "price" and text:
            clean = text.replace("$", "").strip()
            if not clean.isdigit():
                send(chat_id, "💰 Narxni raqamda kiriting:")
                return "ok"
            nl["price"] = int(clean)
            state["step"] = "description"
            set_state(chat_id, state)
            send(chat_id, t["ask_description"], [[{"text": t["btn_skip"], "callback_data": "nl_skip_desc"}]])

        elif step == "description" and text:
            nl["description"] = text
            state["step"] = "photos"
            set_state(chat_id, state)
            send(chat_id, t["ask_photos"], [[{"text": t["btn_skip"], "callback_data": "nl_skip_photos"}]])

        elif step == "photos":
            if photo:
                photos.append(photo[-1]["file_id"])
                state["photos"] = photos
                set_state(chat_id, state)
                if len(photos) >= 5:
                    state["step"] = "address"
                    set_state(chat_id, state)
                    send(chat_id, t["ask_address"], [[{"text": t["btn_skip"], "callback_data": "nl_skip_addr"}]])
                else:
                    send(chat_id, f"📸 Rasm qabul qilindi ({len(photos)} ta).", [[
                        {"text": f"✅ Tayyor ({len(photos)} ta)", "callback_data": "nl_photos_done"},
                        {"text": "⏭ O'tkazib yuborish", "callback_data": "nl_skip_photos"}
                    ]])

        elif step == "address" and text:
            nl["address"] = text
            state["step"] = "phone"
            set_state(chat_id, state)
            send(chat_id, t["ask_phone"])

        elif step == "phone":
            phone = contact["phone_number"] if contact else text
            nl["phone"] = phone
            nl["photos"] = photos
            nl["source"] = "bot"
            nl["user_id"] = u["id"] if u else None
            nl["is_active"] = False
            add_listing(nl)
            clear_state(chat_id)
            send(chat_id, t["listing_saved"], main_menu_kb(lang))

            # Adminlarga xabar
            for admin_id in get_admins():
                try:
                    send(admin_id, f"📢 Yangi elon tasdiqlash kutmoqda!\n\n{format_listing(nl)}",
                         [[{"text": "📋 Ko'rish", "callback_data": "adm_pending"}]])
                except:
                    pass

    return "ok"


def handle_main_menu(chat_id, lang):
    welcome_text = WELCOME.get(lang, WELCOME["uz"])
    send(chat_id, welcome_text, main_menu_kb(lang))

def handle_search(chat_id, lang):
    set_state(chat_id, {"flow": "search", "step": "city"})
    city_btns = []
    row = []
    for i, c in enumerate(CITIES):
        emoji = CITY_EMOJI.get(c, "📍")
        row.append({"text": f"{emoji} {c}", "callback_data": f"s_city_{c}"})
        if len(row) == 2:
            city_btns.append(row)
            row = []
    if row:
        city_btns.append(row)
    t = tx(lang)
    header = {"uz": "🔍 Qidiruv — 1/4 qadam\n\n📍 Shaharni tanlang:", "ru": "🔍 Поиск — шаг 1/4\n\n📍 Выберите город:", "en": "🔍 Search — step 1/4\n\n📍 Select city:"}.get(lang, "📍 Shaharni tanlang:")
    send(chat_id, header, city_btns)

def handle_add(chat_id, lang):
    set_state(chat_id, {"flow": "add", "step": "deal", "nl": {}, "photos": []})
    t = tx(lang)
    btns = [
        [{"text": DEAL_TYPES[lang][0], "callback_data": "nl_deal_rent"},
         {"text": DEAL_TYPES[lang][1], "callback_data": "nl_deal_sale"}],
        [{"text": t["btn_cancel"], "callback_data": "menu_main"}]
    ]
    send(chat_id, t["ask_deal"], btns)

def handle_settings(chat_id, uid, lang):
    u = get_user(uid)
    sub = get_sub(u["id"]) if u else {}
    sub = sub or {}
    t = tx(lang)
    is_active = sub.get("is_active", True)
    only_cheap = sub.get("only_cheap", False)
    freq = sub.get("notify_freq", "daily")
    daily_limit = sub.get("daily_limit", 5)
    fl = NOTIFY_FREQ[lang]
    limit_label = t["limit_unlimited"] if daily_limit == 0 else f"{daily_limit} ta"
    kb = [
        [{"text": t["notif_on"] if is_active else t["notif_off"], "callback_data": "set_notif"}],
        [{"text": t["only_cheap_on"] if only_cheap else t["only_cheap_off"], "callback_data": "set_cheap"}],
        [{"text": fl[freq], "callback_data": "set_freq"}],
        [{"text": f"Limit: {limit_label}", "callback_data": "set_limit"}],
        [{"text": "🌍 Tilni o'zgartirish", "callback_data": "set_lang"}],
        [{"text": "◀️ Orqaga", "callback_data": "menu_main"}]
    ]
    send(chat_id, t["settings_title"], kb)


@app.route("/")
def index():
    return "UyBot ishlayapti!"

@app.route("/set_webhook")
def setup_webhook():
    set_webhook()
    return "Webhook o'rnatildi!"

@app.route("/scrape_now")
def scrape_now():
    threading.Thread(target=scrape_olx).start()
    return "OLX scraping boshlandi!"


if __name__ == "__main__":
    set_webhook()
    threading.Thread(target=olx_scheduler, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
