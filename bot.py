import os
import logging
import requests as req
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
WEBHOOK_URL = "https://uybot.onrender.com"

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
    return req.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=data, timeout=10)

def send(chat_id, text, kb=None):
    data = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if kb:
        data["reply_markup"] = {"inline_keyboard": kb}
    tg("sendMessage", data)

def send_photo(chat_id, photo, caption=None, kb=None):
    data = {"chat_id": chat_id, "photo": photo}
    if caption: data["caption"] = caption
    if kb: data["reply_markup"] = {"inline_keyboard": kb}
    tg("sendPhoto", data)

def answer_cb(cb_id):
    tg("answerCallbackQuery", {"callback_query_id": cb_id})

def set_webhook():
    tg("setWebhook", {"url": f"{WEBHOOK_URL}/webhook"})

# ===================== DB =====================
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

def get_listings(city=None, deal_type=None, rooms=None, price_min=None, price_max=None, offset=0, limit=3):
    f = "is_active=eq.true&select=*&order=published_at.desc"
    if city: f += f"&city=eq.{city}"
    if deal_type: f += f"&deal_type=eq.{deal_type}"
    if rooms: f += f"&rooms=eq.{rooms}"
    if price_min is not None: f += f"&price=gte.{price_min}"
    if price_max is not None: f += f"&price=lte.{price_max}"
    f += f"&offset={offset}&limit={limit}"
    return sb_get("listings", f)

def count_listings(city=None, deal_type=None, rooms=None, price_min=None, price_max=None):
    f = "is_active=eq.true"
    if city: f += f"&city=eq.{city}"
    if deal_type: f += f"&deal_type=eq.{deal_type}"
    if rooms: f += f"&rooms=eq.{rooms}"
    if price_min is not None: f += f"&price=gte.{price_min}"
    if price_max is not None: f += f"&price=lte.{price_max}"
    return sb_count("listings", f)

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

# ===================== CONSTANTS =====================
CITIES = ["Toshkent","Samarqand","Buxoro","Namangan","Andijon","Fargona","Nukus","Qarshi","Termiz"]
DEAL_TYPES = {"uz":["Ijaraga","Sotuvga"],"ru":["Arenda","Prodaja"],"en":["Rent","Sale"]}
ROOMS = ["1","2","3","4","5+"]
PRICE_RANGES = [(0,300),(300,600),(600,1000),(1000,2000),(2000,99999)]
PRICE_LABELS = ["$0-300","$300-600","$600-1000","$1000-2000","$2000+"]
NOTIFY_FREQ = {"uz":{"instant":"Darhol","daily":"Kuniga 1","weekly":"Haftada 1"},"ru":{"instant":"Srazu","daily":"Raz v den","weekly":"Raz v nedelyu"},"en":{"instant":"Instantly","daily":"Once a day","weekly":"Once a week"}}
DAILY_LIMITS = [3,5,10,0]

UZ = {"choose_language":"Tilni tanlang:","welcome":"UyBot ga xush kelibsiz!","btn_search":"Qidiruv","btn_my_listings":"Mening elonlarim","btn_add_listing":"Elon berish","btn_settings":"Sozlamalar","btn_help":"Yordam","choose_city":"Qaysi shaharda?","choose_deal":"Nima qidirmoqdasiz?","choose_rooms":"Nechta xona?","choose_price":"Narx oraligi?","no_results":"Hech narsa topilmadi.","btn_next":"Keyingi ➡️","btn_prev":"⬅️ Oldingi","btn_cancel":"Bekor","btn_skip":"O'tkazib yuborish","ask_deal":"Ijara yoki sotish?","ask_city":"Qaysi shahar?","ask_rooms":"Nechta xona?","ask_price":"Narx ($):","ask_description":"Tavsif (yoki o'tkazib yuborish):","ask_photos":"Rasm yuboring:","ask_address":"Manzil:","ask_phone":"Telefon:","listing_saved":"Elon saqlandi!","settings_title":"Sozlamalar:","notif_on":"Xabar: Yoqilgan","notif_off":"Xabar: O'chirilgan","choose_freq":"Qanchalik tez?","choose_limit":"Kuniga nechta?","limit_unlimited":"Cheksiz","only_cheap_on":"Arzon: Ha","only_cheap_off":"Arzon: Yo'q","help_text":"UyBot — uy-joy izlash boti\n\n/start — Boshlaish\n/add — Elon berish\n/settings — Sozlamalar\n/stats — Statistika","stats_title":"Statistika:","stats_users":"Foydalanuvchilar: {count}","stats_listings":"Elonlar: {count}","stats_active":"Faol elonlar: {count}","stats_subs":"Faol obunalar: {count}"}
RU = {"choose_language":"Tilni tanlang:","welcome":"Dobro pozhalovat v UyBot!","btn_search":"Poisk","btn_my_listings":"Moi obyavleniya","btn_add_listing":"Dobavit","btn_settings":"Nastroyki","btn_help":"Pomosh","choose_city":"Gorod?","choose_deal":"Chto ischete?","choose_rooms":"Komnaty?","choose_price":"Tsena?","no_results":"Ne naydeno.","btn_next":"Dalee ➡️","btn_prev":"⬅️ Nazad","btn_cancel":"Otmena","btn_skip":"Propustit","ask_deal":"Arenda ili prodazha?","ask_city":"Gorod?","ask_rooms":"Komnaty?","ask_price":"Tsena ($):","ask_description":"Opisanie:","ask_photos":"Foto:","ask_address":"Adres:","ask_phone":"Telefon:","listing_saved":"Sokhraneno!","settings_title":"Nastroyki:","notif_on":"Uvedomleniya: Vkl","notif_off":"Uvedomleniya: Otkl","choose_freq":"Kak chasto?","choose_limit":"Maks v den?","limit_unlimited":"Bez limita","only_cheap_on":"Deshevle: Da","only_cheap_off":"Deshevle: Net","help_text":"UyBot\n/start /add /settings /stats","stats_title":"Statistika:","stats_users":"Polzovateli: {count}","stats_listings":"Obyavleniya: {count}","stats_active":"Aktivnye: {count}","stats_subs":"Podpiski: {count}"}
EN = {"choose_language":"Choose language:","welcome":"Welcome to UyBot!","btn_search":"Search","btn_my_listings":"My listings","btn_add_listing":"Add listing","btn_settings":"Settings","btn_help":"Help","choose_city":"City?","choose_deal":"Looking for?","choose_rooms":"Rooms?","choose_price":"Price?","no_results":"Nothing found.","btn_next":"Next ➡️","btn_prev":"⬅️ Previous","btn_cancel":"Cancel","btn_skip":"Skip","ask_deal":"Rent or sale?","ask_city":"City?","ask_rooms":"Rooms?","ask_price":"Price ($):","ask_description":"Description:","ask_photos":"Photos:","ask_address":"Address:","ask_phone":"Phone:","listing_saved":"Saved!","settings_title":"Settings:","notif_on":"Notifications: On","notif_off":"Notifications: Off","choose_freq":"How often?","choose_limit":"Max per day?","limit_unlimited":"Unlimited","only_cheap_on":"Cheap only: Yes","only_cheap_off":"Cheap only: No","help_text":"UyBot\n/start /add /settings /stats","stats_title":"Statistics:","stats_users":"Users: {count}","stats_listings":"Listings: {count}","stats_active":"Active: {count}","stats_subs":"Subscriptions: {count}"}

def tx(lang): return {"uz":UZ,"ru":RU,"en":EN}.get(lang, UZ)

def main_menu_kb(lang):
    t = tx(lang)
    return [[{"text": t["btn_search"], "callback_data": "menu_search"}],
            [{"text": t["btn_add_listing"], "callback_data": "menu_add"}, {"text": t["btn_my_listings"], "callback_data": "menu_mylist"}],
            [{"text": t["btn_settings"], "callback_data": "menu_settings"}, {"text": t["btn_help"], "callback_data": "menu_help"}]]

# User state (xotira)
user_state = {}

def get_state(uid):
    return user_state.get(uid, {})

def set_state(uid, data):
    user_state[uid] = data

def clear_state(uid):
    user_state.pop(uid, None)

# ===================== HANDLERS =====================
def handle_start(chat_id, uid, name, username):
    get_or_create_user(uid, name, username)
    kb = [[
        {"text": "O'zbek", "callback_data": "lang_uz"},
        {"text": "Русский", "callback_data": "lang_ru"},
        {"text": "English", "callback_data": "lang_en"}
    ]]
    send(chat_id, UZ["choose_language"], kb)

def handle_main_menu(chat_id, lang):
    t = tx(lang)
    send(chat_id, t["welcome"], main_menu_kb(lang))

def handle_search(chat_id, lang):
    set_state(chat_id, {"flow": "search", "step": "city"})
    btns = [[{"text": c, "callback_data": f"s_city_{c}"}] for c in CITIES]
    send(chat_id, tx(lang)["choose_city"], btns)

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
        [{"text": "Tilni o'zgartirish", "callback_data": "set_lang"}],
        [{"text": "◀️ Orqaga", "callback_data": "menu_main"}]
    ]
    send(chat_id, t["settings_title"], kb)

def show_results(chat_id, state, lang, page):
    t = tx(lang)
    s = state.get("search_params", {})
    listings = get_listings(
        city=s.get("city"), deal_type=s.get("deal_type"),
        rooms=s.get("rooms"), price_min=s.get("price_min"),
        price_max=s.get("price_max"), offset=page*3, limit=3
    )
    total = count_listings(
        city=s.get("city"), deal_type=s.get("deal_type"),
        rooms=s.get("rooms"), price_min=s.get("price_min"),
        price_max=s.get("price_max")
    )
    if not listings:
        send(chat_id, t["no_results"], [[{"text": "◀️ Orqaga", "callback_data": "menu_main"}]])
        return
    nav = []
    if page > 0: nav.append({"text": t["btn_prev"], "callback_data": f"s_page_{page-1}"})
    if (page+1)*3 < total: nav.append({"text": t["btn_next"], "callback_data": f"s_page_{page+1}"})
    for i, l in enumerate(listings):
        lines = []
        if l.get("title"): lines.append(f"<b>{l['title']}</b>")
        if l.get("price"): lines.append(f"💰 ${l['price']}")
        if l.get("rooms"): lines.append(f"🚪 {l['rooms']} xona")
        if l.get("city"): lines.append(f"📍 {l['city']}")
        if l.get("address"): lines.append(l["address"])
        if l.get("description"): lines.append(l["description"][:200])
        if l.get("phone"): lines.append(f"📞 {l['phone']}")
        text = "\n".join(lines) if lines else "—"
        kb = [nav] if nav and i == len(listings)-1 else None
        photos = l.get("photos") or []
        if photos:
            send_photo(chat_id, photos[0], text, kb)
        else:
            send(chat_id, text, kb)

# ===================== WEBHOOK =====================
@app.route("/webhook", methods=["POST"])
def webhook():
    d = request.json
    if not d:
        return "ok"

    # Callback query
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

        if data == "menu_main":
            clear_state(chat_id)
            handle_main_menu(chat_id, lang)
        elif data == "menu_search":
            handle_search(chat_id, lang)
        elif data == "menu_add":
            handle_add(chat_id, lang)
        elif data == "menu_settings":
            handle_settings(chat_id, uid, lang)
        elif data == "menu_help":
            send(chat_id, t["help_text"], [[{"text": "◀️ Orqaga", "callback_data": "menu_main"}]])

        # Til tanlash
        elif data.startswith("lang_"):
            new_lang = data.split("_")[1]
            update_lang(uid, new_lang)
            handle_main_menu(chat_id, new_lang)

        # Qidiruv
        elif data.startswith("s_city_"):
            city = data.replace("s_city_", "")
            state = {"flow": "search", "step": "deal", "search_params": {"city": city}}
            set_state(chat_id, state)
            btns = [[
                {"text": DEAL_TYPES[lang][0], "callback_data": "s_deal_rent"},
                {"text": DEAL_TYPES[lang][1], "callback_data": "s_deal_sale"}
            ]]
            send(chat_id, t["choose_deal"], btns)
        elif data.startswith("s_deal_"):
            deal = data.replace("s_deal_", "")
            state["search_params"]["deal_type"] = deal
            state["step"] = "rooms"
            set_state(chat_id, state)
            btns = [[{"text": r, "callback_data": f"s_rooms_{r}"} for r in ROOMS]]
            send(chat_id, t["choose_rooms"], btns)
        elif data.startswith("s_rooms_"):
            rooms = data.replace("s_rooms_", "")
            state["search_params"]["rooms"] = rooms
            state["step"] = "price"
            set_state(chat_id, state)
            btns = [[{"text": p, "callback_data": f"s_price_{i}"}] for i, p in enumerate(PRICE_LABELS)]
            send(chat_id, t["choose_price"], btns)
        elif data.startswith("s_price_"):
            idx = int(data.replace("s_price_", ""))
            state["search_params"]["price_min"], state["search_params"]["price_max"] = PRICE_RANGES[idx]
            state["step"] = "results"
            set_state(chat_id, state)
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
            kb = [[{"text": t["limit_unlimited"] if l == 0 else f"{l} ta", "callback_data": f"sl_{l}"}] for l in DAILY_LIMITS]
            send(chat_id, t["choose_limit"], kb)
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

    # Message
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

    # Komandalar
    if text == "/start":
        handle_start(chat_id, uid, name, username)
        return "ok"
    if text == "/add":
        handle_add(chat_id, lang)
        return "ok"
    if text == "/settings":
        handle_settings(chat_id, uid, lang)
        return "ok"
    if text == "/help":
        send(chat_id, t["help_text"])
        return "ok"
    if text == "/stats":
        users = sb_count("users")
        listings = sb_count("listings")
        active = sb_count("listings", "is_active=eq.true")
        subs = sb_count("subscriptions", "is_active=eq.true")
        txt = f"{t['stats_title']}\n\n{t['stats_users'].format(count=users)}\n{t['stats_listings'].format(count=listings)}\n{t['stats_active'].format(count=active)}\n{t['stats_subs'].format(count=subs)}"
        send(chat_id, txt)
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
                send(chat_id, "Narxni raqamda kiriting:")
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
                if len(photos) >= 10:
                    state["step"] = "address"
                    set_state(chat_id, state)
                    send(chat_id, t["ask_address"], [[{"text": t["btn_skip"], "callback_data": "nl_skip_addr"}]])
                else:
                    send(chat_id, f"Rasm qabul qilindi ({len(photos)} ta).", [[{"text": f"Tayyor ({len(photos)} ta)", "callback_data": "nl_photos_done"}]])

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

    return "ok"


@app.route("/")
def index():
    return "UyBot ishlayapti!"


@app.route("/set_webhook")
def setup_webhook():
    set_webhook()
    return "Webhook o'rnatildi!"


if __name__ == "__main__":
    set_webhook()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
