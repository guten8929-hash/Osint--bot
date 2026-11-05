import asyncio
import aiohttp
import os
import threading
import phonenumbers
import hashlib
import re
import html
from phonenumbers import geocoder, carrier, timezone
from flask import Flask
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

TOKEN = "9204279454:AAHHCP0e2NWsK5Gmo2CeyARKZI92Y-heqwI"

# --- НАСТРОЙКА FLASK ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
@app.route('/health')
def health():
    return "Bot is running", 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
# ---------------------------------

router = Router()

# --- БАЗОВЫЕ КОМАНДЫ ---
@router.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer(
        "🕵️ OSINT Bot на связи.\n\n"
        "Доступные команды:\n"
        "/ip <ip> — гео по IP\n"
        "/user <ник> — поиск по платформам\n"
        "/phone <номер> — инфо о номере\n"
        "/email <почта> — проверка email\n"
        "/tg <@ник> — парсинг Telegram\n"
        "Любой другой текст — эхо."
    )

# --- МОДУЛЬ IP ---
@router.message(Command("ip"))
async def cmd_ip(m: Message):
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await m.answer("Использование: /ip 8.8.8.8")
    ip = parts[1].strip()
    await m.answer(f"🔎 Ищу информацию по {ip}...")
    url = f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp,org,as,query&lang=ru"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
        if data.get("status") != "success":
            return await m.answer("❌ Не удалось найти информацию.")
        text = (
            f"🌐 <b>IP:</b> <code>{data.get('query')}</code>\n"
            f"🏳️ <b>Страна:</b> {data.get('country')}\n"
            f"📍 <b>Регион:</b> {data.get('regionName')}\n"
            f"🏙 <b>Город:</b> {data.get('city')}\n"
            f"📡 <b>Провайдер:</b> {data.get('isp')}\n"
            f"🔗 <b>ASN:</b> {data.get('as')}"
        )
        await m.answer(text, parse_mode="HTML")
    except Exception as e:
        await m.answer(f"⚠️ Ошибка: {e}")

# --- МОДУЛЬ ТЕЛЕФОНА ---
@router.message(Command("phone"))
async def cmd_phone(m: Message):
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await m.answer("Использование: /phone +79101234567")
    
    phone_str = parts[1].strip()
    try:
        pn = phonenumbers.parse(phone_str, "RU")
        if not phonenumbers.is_valid_number(pn):
            return await m.answer("❌ Невалидный номер телефона.")
            
        country = geocoder.description_for_number(pn, "ru")
        operator = carrier.name_for_number(pn, "ru")
        tz = timezone.time_zones_for_number(pn)
        line_type = "Мобильный" if phonenumbers.number_type(pn) == 1 else "Стационарный/Другой"
        
        text = (
            f"📱 <b>Номер:</b> <code>{phonenumbers.format_number(pn, phonenumbers.PhoneNumberFormat.INTERNATIONAL)}</code>\n"
            f"🏳️ <b>Страна/Регион:</b> {country if country else 'Неизвестно'}\n"
            f"📡 <b>Оператор:</b> {operator if operator else 'Неизвестно'}\n"
            f"📞 <b>Тип линии:</b> {line_type}\n"
            f"🕒 <b>Часовой пояс:</b> {', '.join(tz)}"
        )
        await m.answer(text, parse_mode="HTML")
    except Exception as e:
        await m.answer(f"⚠️ Ошибка парсинга: {e}")

# --- МОДУЛЬ EMAIL ---
@router.message(Command("email"))
async def cmd_email(m: Message):
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await m.answer("Использование: /email test@example.com")
    
    email = parts[1].strip().lower()
    await m.answer(f"🔎 Проверяю <code>{email}</code>...", parse_mode="HTML")
    
    text = f"📧 <b>Email:</b> <code>{email}</code>\n\n"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    async with aiohttp.ClientSession() as session:
        # Gravatar
        email_hash = hashlib.md5(email.encode('utf-8')).hexdigest()
        gravatar_url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"
        try:
            async with session.get(gravatar_url, headers=headers, timeout=5) as r:
                if r.status == 200:
                    text += "✅ <b>Gravatar:</b> Аккаунт существует (есть аватарка)\n"
                else:
                    text += "❌ <b>Gravatar:</b> Не найден\n"
        except:
            text += "⚠️ <b>Gravatar:</b> Ошибка проверки\n"

        # XposedOrNot (Утечки)
        breach_url = f"https://api.xposedornot.com/v1/breach-analytics?email={email}"
        try:
            async with session.get(breach_url, headers=headers, timeout=10) as r:
                if r.status == 200:
                    data = await r.json()
                    breaches = data.get("ExposedBreaches", {}).get("breaches_details", [])
                    if breaches:
                        text += f"\n🔴 <b>Найдено в {len(breaches)} утечках:</b>\n"
                        for b in breaches[:5]:
                            text += f"— {b.get('breach')} ({b.get('xposed_date')})\n"
                    else:
                        text += "\n✅ <b>Утечек не найдено.</b>\n"
                elif r.status == 404:
                    text += "\n✅ <b>Утечек не найдено.</b>\n"
                else:
                    text += f"\n⚠️ <b>Утечки:</b> Ошибка API ({r.status})\n"
        except Exception:
            text += f"\n⚠️ <b>Утечки:</b> Ошибка сети\n"

    await m.answer(text, parse_mode="HTML", disable_web_page_preview=True)

# --- МОДУЛЬ USERNAME ---
SITES = {
    "GitHub": {"url": "https://github.com/{}", "err": None},
    "Reddit": {"url": "https://www.reddit.com/user/{}", "err": "Sorry, nobody on Reddit goes by that name"},
    "Twitch": {"url": "https://www.twitch.tv/{}", "err": "Sorry. Unless you've got a time machine"},
    "Instagram": {"url": "https://www.instagram.com/{}/", "err": "Sorry, this page isn't available"},
    "TikTok": {"url": "https://www.tiktok.com/@{}", "err": "Couldn't find this account"},
    "Steam": {"url": "https://steamcommunity.com/id/{}", "err": "The specified profile could not be found"},
    "VK": {"url": "https://vk.com/{}", "err": "Ничего не найдено"},
}

async def check_site(session, name, url, err_marker):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with session.get(url, timeout=8, headers=headers, allow_redirects=True) as response:
            if response.status == 200:
                if err_marker:
                    page_text = await response.text()
                    if err_marker.lower() in page_text.lower():
                        return (name, url, False)
                return (name, url, True)
            return (name, url, False)
    except Exception:
        return (name, url, False)

@router.message(Command("user"))
async def cmd_user(m: Message):
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await m.answer("Использование: /user <никнейм>")
    username = parts[1].strip().lstrip('@')
    await m.answer(f"🔎 Ищу ник <code>{username}</code>...", parse_mode="HTML")
    found = []
    not_found = []
    async with aiohttp.ClientSession() as session:
        tasks = [check_site(session, name, data["url"].format(username), data["err"]) for name, data in SITES.items()]
        results = await asyncio.gather(*tasks)
        for name, url, is_found in results:
            if is_found:
                found.append(f"✅ <a href='{url}'>{name}</a>")
            else:
                not_found.append(name)
    if found:
        res_text = "<b>Найдено:</b>\n" + "\n".join(found)
        res_text += f"\n\n<i>Не найдено: {', '.join(not_found)}</i>"
        await m.answer(res_text, parse_mode="HTML", disable_web_page_preview=True)
    else:
        await m.answer("❌ Ничего не найдено.")

# --- МОДУЛЬ TELEGRAM ---
@router.message(Command("tg"))
async def cmd_tg(m: Message):
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await m.answer("Использование: /tg @username или /tg t.me/username")
    
    query = parts[1].strip()
    if "t.me/" in query:
        query = query.split("t.me/")[-1].split("/")[0].split("?")[0]
    query = query.lstrip('@')

    url = f"https://t.me/{query}"
    await m.answer(f"🔎 Парсю Telegram-профиль <code>{query}</code>...", parse_mode="HTML")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as r:
                if r.status != 200:
                    return await m.answer("❌ Профиль/канал не найден (или закрыт).")
                
                page_html = await r.text()
                
                title_match = re.search(r'<meta property="og:title" content="(.*?)"', page_html)
                desc_match = re.search(r'<meta property="og:description" content="(.*?)"', page_html)
                img_match = re.search(r'<meta property="og:image" content="(.*?)"', page_html)
                subs_match = re.search(r'<div class="tgme_page_extra">(.*?)</div>', page_html)

                title = html.unescape(title_match.group(1)) if title_match else "Неизвестно"
                desc = html.unescape(desc_match.group(1)) if desc_match else "Нет описания"
                img_url = img_match.group(1) if img_match else None
                
                if subs_match:
                    subs_text = subs_match.group(1).replace("subscribers", "подписчиков").replace("members", "участников")
                else:
                    subs_text = "Нет данных (личный аккаунт или скрыто)"

                text = (
                    f"🆔 <b>Username:</b> @{query}\n"
                    f"📛 <b>Имя/Название:</b> {title}\n"
                    f"📝 <b>Био/Описание:</b> {desc}\n"
                    f"👥 <b>Статистика:</b> {subs_text}\n"
                    f"🔗 <b>Ссылка:</b> <a href='{url}'>{url}</a>"
                )
                
                if img_url:
                    await m.answer_photo(photo=img_url, caption=text, parse_mode="HTML")
                else:
                    await m.answer(text, parse_mode="HTML", disable_web_page_preview=True)
                    
    except Exception as e:
        await m.answer(f"⚠️ Ошибка парсинга: {e}")

# --- ЭХО ---
@router.message()
async def echo(m: Message):
    await m.answer(f"Эхо: {m.text}")

# --- ЗАПУСК ---
async def main():
    bot = Bot(TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
