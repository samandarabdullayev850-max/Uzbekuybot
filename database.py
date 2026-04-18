from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_user(telegram_id):
    res = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
    return res.data[0] if res.data else None

def create_user(telegram_id, full_name, username=None):
    supabase.table("users").insert({"telegram_id": telegram_id, "full_name": full_name, "username": username, "language": "uz", "is_banned": False}).execute()

def update_user_language(telegram_id, language):
    supabase.table("users").update({"language": language}).eq("telegram_id", telegram_id).execute()

def get_or_create_user(telegram_id, full_name, username=None):
    user = get_user(telegram_id)
    if not user:
        create_user(telegram_id, full_name, username)
        user = get_user(telegram_id)
    return user

def get_listings(city=None, deal_type=None, rooms=None, price_min=None, price_max=None, offset=0, limit=5):
    query = supabase.table("listings").select("*").eq("is_active", True)
    if city: query = query.eq("city", city)
    if deal_type: query = query.eq("deal_type", deal_type)
    if rooms: query = query.eq("rooms", rooms)
    if price_min is not None: query = query.gte("price", price_min)
    if price_max is not None: query = query.lte("price", price_max)
    res = query.order("published_at", desc=True).range(offset, offset + limit - 1).execute()
    return res.data

def count_listings(city=None, deal_type=None, rooms=None, price_min=None, price_max=None):
    query = supabase.table("listings").select("id", count="exact").eq("is_active", True)
    if city: query = query.eq("city", city)
    if deal_type: query = query.eq("deal_type", deal_type)
    if rooms: query = query.eq("rooms", rooms)
    if price_min is not None: query = query.gte("price", price_min)
    if price_max is not None: query = query.lte("price", price_max)
    return query.execute().count or 0

def add_listing(data):
    res = supabase.table("listings").insert(data).execute()
    return res.data[0] if res.data else None

def get_subscription(user_id):
    res = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None

def save_subscription(user_id, data):
    existing = get_subscription(user_id)
    if existing:
        supabase.table("subscriptions").update(data).eq("user_id", user_id).execute()
    else:
        data["user_id"] = user_id
        supabase.table("subscriptions").insert(data).execute()

def get_active_subscriptions():
    res = supabase.table("subscriptions").select("*, users(telegram_id, language)").eq("is_active", True).execute()
    return res.data

def already_sent(user_id, listing_id):
    res = supabase.table("sent_notifications").select("id").eq("user_id", user_id).eq("listing_id", listing_id).execute()
    return len(res.data) > 0

def mark_sent(user_id, listing_id):
    supabase.table("sent_notifications").insert({"user_id": user_id, "listing_id": listing_id}).execute()

def count_sent_today(user_id):
    from datetime import date
    today = date.today().isoformat()
    res = supabase.table("sent_notifications").select("id", count="exact").eq("user_id", user_id).gte("sent_at", today).execute()
    return res.count or 0
