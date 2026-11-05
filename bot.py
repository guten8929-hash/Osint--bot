import asyncio
import aiohttp
import os
import threading
from flask import Flask
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

# --- Токен и Flask ---
TOKEN = "9204279454:AAHHCP0e2NWsK5Gmo2CeyARKZI92Y-heqwI"
app = Flask(__name__)

@app.route('/')
@app.route('/health')
def health():
    return "Bot is running", 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# --- Логика бота (без изменений) ---
router = Router()

@router.message(Command("start"))
async def cmd_start(m: Message):
    await m.answer("🕵️ OSINT Bot на связи. Готов к работе.")

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
            return await m.answer("❌ Не удалось найти информацию. Проверь IP.")
        text = (
            f"🌐 <b>IP:</b> <code>{data.get('query')}</code>\n"
            f"🏳️ <b>Страна:</b> {data.get('country')}\n"
            f"📍 <b>Регион:</b> {data.get('regionName')}\n"
            f"🏙 <b>Город:</b> {data.get('city')}\n"
            f"📡 <b>Провайдер:</b> {data.get('isp')}\n"
            f"🏢 <b>Организация:</b> {data.get('org')}\n"
            f"🔗 <b>ASN:</b> {data.get('as')}"
        )
        await m.answer(text, parse_mode="HTML")
    except Exception as e:
        await m.answer(f"⚠️ Ошибка сети: {e}")

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
                    text = await response.text()
                    if err_marker.lower() in text.lower():
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
        text = "<b>Найдено:</b>\n" + "\n".join(found)
        text += f"\n\n<i>Не найдено: {', '.join(not_found)}</i>"
        await m.answer(text, parse_mode="HTML", disable_web_page_preview=True)
    else:
        await m.answer("❌ Ничего не найдено.")

@router.message()
async def echo(m: Message):
    await m.answer(f"Эхо: {m.text}")

async def main():
    bot = Bot(TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()
    # Запускаем бота
    asyncio.run(main())
