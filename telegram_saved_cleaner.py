import asyncio
import os
import random
import time
import json
from groq import Groq
from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError, RPCError
from telethon.tl.functions.messages import CreateForumTopicRequest, GetForumTopicsRequest, ForwardMessagesRequest

# ====================== CONFIG ======================
CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

config = load_config()

GROQ_API_KEY = config.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
API_ID = config.get("API_ID") or os.getenv("TELEGRAM_API_ID")
API_HASH = config.get("API_HASH") or os.getenv("TELEGRAM_API_HASH")
GROUP_ID = config.get("GROUP_ID")

# ===================================================

client = None
groq_client = None
topic_cache = {}

ALLOWED_TOPICS = [
    "🤖 هوش مصنوعی", "📸 عکاسی", "💰 مالی", "🔧 ابزار", 
    "📚 یادگیری", "🛒 خرید", "📝 یادداشت شخصی", "💼 کار", 
    "🎥 ویدیو", "📦 متفرقه", "🗑️ Delete Only"
]


async def get_or_create_topic(topic_name: str):
    global client
    topic_name = topic_name.strip()[:45]

    if topic_name in topic_cache:
        return topic_cache[topic_name]

    for t in ALLOWED_TOPICS:
        if t.lower() in topic_name.lower() or topic_name.lower() in t.lower():
            topic_name = t
            break
    else:
        topic_name = "📦 متفرقه"

    try:
        input_peer = await client.get_input_entity(GROUP_ID)
        result = await client(GetForumTopicsRequest(
            peer=input_peer, offset_date=None, offset_id=0, offset_topic=0, limit=100
        ))
        for topic in getattr(result, 'topics', []):
            if getattr(topic, 'title', None) == topic_name:
                topic_cache[topic_name] = topic.id
                print(f"   🔍 پیدا شد: {topic_name}")
                return topic.id
    except:
        pass

    try:
        input_peer = await client.get_input_entity(GROUP_ID)
        result = await client(CreateForumTopicRequest(
            peer=input_peer,
            title=topic_name,
            random_id=random.randint(0, 2**63 - 1),
        ))
        topic_id = None
        for u in getattr(result, 'updates', []):
            if hasattr(u, 'id'):
                topic_id = u.id
                break
        if topic_id:
            topic_cache[topic_name] = topic_id
            print(f"   ✅ ایجاد شد: {topic_name}")
            return topic_id
    except:
        pass

    return None


def classify_message(text: str) -> tuple:
    if not text or len(text.strip()) < 5:
        return "📦 متفرقه", False

    prompt = f"""پیام زیر را بررسی کن:

{text[:700]}

ابتدا تصمیم بگیر:
- آیا این پیام موقتی، تاریخ‌گذشته، تبلیغاتی، اسپم، یا بی‌ارزش است؟ (بله/خیر)

اگر بله → Delete Only = True و برچسب = "🗑️ Delete Only"
اگر خیر → برچسب مناسب انتخاب کن.

پاسخ فقط به این شکل:
Delete Only: بله/خیر
برچسب: ..."""

    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=40
        )
        response = completion.choices[0].message.content.strip()

        is_delete_only = False
        label = "📦 متفرقه"

        for line in response.splitlines():
            if "delete only" in line.lower() or "حذف" in line:
                if "بله" in line or "yes" in line.lower():
                    is_delete_only = True
            if "برچسب" in line.lower():
                for t in ALLOWED_TOPICS:
                    if t in line:
                        label = t
                        break

        if is_delete_only:
            label = "🗑️ Delete Only"

        return label, is_delete_only
    except:
        return "📦 متفرقه", False


async def forward_to_topic(msg, topic_id):
    try:
        await client(ForwardMessagesRequest(
            from_peer=await client.get_input_entity('me'),
            id=[msg.id],
            to_peer=await client.get_input_entity(GROUP_ID),
            random_id=[random.getrandbits(63)],
            top_msg_id=topic_id,
        ))
        return True
    except:
        await client.forward_messages(GROUP_ID, messages=[msg])
        return True


async def main():
    global client, groq_client

    print("=== Telegram Saved Messages Organizer ===\n")

    # گرفتن تنظیمات اولیه
    if not GROQ_API_KEY:
        GROQ_API_KEY = input("GROQ_API_KEY: ").strip()
        config["GROQ_API_KEY"] = GROQ_API_KEY
    if not API_ID:
        API_ID = int(input("TELEGRAM_API_ID: ").strip())
        config["API_ID"] = API_ID
    if not API_HASH:
        API_HASH = input("TELEGRAM_API_HASH: ").strip()
        config["API_HASH"] = API_HASH
    if not GROUP_ID:
        GROUP_ID = int(input("GROUP_ID (مثال: -1001234567890): ").strip())
        config["GROUP_ID"] = GROUP_ID

    save_config(config)
    groq_client = Groq(api_key=GROQ_API_KEY)

    client = TelegramClient('session', API_ID, API_HASH, proxy=PROXY)

    try:
        await client.start()
        print("✅ اتصال موفق به تلگرام")
    except SessionPasswordNeededError:
        pwd = input("رمز دو مرحله‌ای: ")
        await client.sign_in(password=pwd)

    num = input("\nتعداد پیام (عدد یا all): ").strip().lower()
    limit = None if num in ['all', ''] else int(num)

    processed = 0
    async for msg in client.iter_messages('me', limit=limit):
        processed += 1
        print(f"\n[{processed}] پیام ID: {msg.id}")

        try:
            text = (msg.message or "") + (" [رسانه]" if msg.media else "")
            label, is_delete_only = classify_message(text)
            print(f"   برچسب: {label} | Delete Only: {is_delete_only}")

            topic_id = await get_or_create_topic(label)

            await forward_to_topic(msg, topic_id)
            print(f"   ✅ فوروارد شد {'به Delete Only' if is_delete_only else ''}")

            await client.delete_messages('me', [msg.id])
            print("   🗑️ حذف از Saved Messages")

            await asyncio.sleep(random.uniform(2.8, 5.5))

        except FloodWaitError as e:
            print(f"⏳ FloodWait: {e.seconds} ثانیه")
            await asyncio.sleep(e.seconds + 10)
        except Exception as e:
            print(f"❌ خطا: {e}")
            await asyncio.sleep(5)

        if limit and processed >= limit:
            break

    await client.disconnect()
    print("✅ اتمام اسکریپت")


if __name__ == "__main__":
    asyncio.run(main())
