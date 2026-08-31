import os
import random
import asyncio
import subprocess
import shutil
import concurrent.futures

import discord
from discord.ext import tasks
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# ⚠️ ПАПКА С АУДИО (путь для Railway)
AUDIO_FOLDER = "/app/audio_koshchey"
os.makedirs(AUDIO_FOLDER, exist_ok=True)

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

if not DISCORD_TOKEN:
    print("❌ ОШИБКА: Не задан DISCORD_TOKEN!")
    raise SystemExit(1)

if not DEEPSEEK_API_KEY:
    print("❌ ОШИБКА: Не задан DEEPSEEK_API_KEY!")
    raise SystemExit(1)

deepseek = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = discord.Client(intents=intents)
conversation = {}

KOSHCHEY_PHRASES = [
    "А вот сейчас я тебе подробно на твою предъяву и отвечу.",
    "Ты меня сейчас при всех крысой назвал? По сути, так получается?",
    "А скажи, пожалуйста, ты это сам увидел, или тебе кто-то напел? Вопрос простой.",
    "Ну, люди-то зря не говорят. Говорят, кур доят.",
    "Я здесь, за эту улицу стою! Пацаны мне всё, и я всё пацанам, кто меня знает, тот в курсе!",
    "Я здесь людей воспитывал, тебя в люди выводил.",
    "Беспредельщик ты и есть, вы людских понятий не знаете.",
    "Что ты думаешь, я тупой что-ли?",
    "Здесь вы ходите королями, а там за забором ты быстро калоши переобуешь.",
    "Я бы тебе пояснил, если бы не твой брат.",
    "Дом там, где люди.",
    "Да надоело быть чушпаном, хочу с пацанами.",
    "Даешь слово пацана?",
    "А если бы тебя твой кореш подставил, чтоб ты сделал?",
    "Знаешь как с козлами поступают?",
    "Ты чё, брат, беспредел решил устроить?",
    "Я за понятия! Ты по понятиям или как?",
    "Слышь, ты че там борзеешь?",
    "Я бы на твоём месте не спешил с выводами.",
    "Ты думаешь, я тупой что ли? Я всё вижу.",
    "Ты меня за кого держишь? За чушпана?",
    "Я, брат, не из тех, кто просто так слова бросает.",
    "Ты это при всех сказал? Ну, давай, повтори.",
    "Я тебя предупреждаю: не доводи до греха.",
    "Пацаны, вы че там? Опять беспредел?",
    "На зоне за такие слова быстро объясняют.",
    "Ты че, думаешь, я шучу? Я никогда не шучу.",
    "Я, брат, ответственный человек. За слова отвечаю.",
    "Ты моё слово пацана слышал? Вот и молчи.",
    "Я тебя в люди вывел, а ты…",
    "Смотри, брат, не переступи черту.",
    "Ты чё, забыл, кто здесь главный?",
]

SYSTEM_PROMPT = (
    "Ты — Кощей из 'Слова пацана'. Ты сидишь в чате с пацанами.\n"
    "Ты вступаешь в разговор по любой теме, если можешь сказать что-то по делу.\n"
    "Ты говоришь как Кощей — резко, по понятиям, с авторитетом.\n"
    "Отвечай по-русски, коротко, резко, по-пацански.\n"
)

TRIGGER_WORDS = [
    "привет", "здарова", "брат", "пацан", "работа", "деньги", "школа",
    "устал", "спать", "еда", "кофе", "чай", "машина", "дорога",
    "игра", "кино", "сериал", "футбол", "спорт", "интернет",
    "кринж", "рофл", "лол", "хайп", "вайб", "чил", "беспредел",
    "понятия", "чушпан", "авторитет", "разборка", "кореш",
]

async def ask_ai(user_text, channel_id):
    history = conversation.setdefault(channel_id, [])
    history.append({"role": "user", "content": user_text})

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history[-15:]
    ]

    try:
        response = await deepseek.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            max_tokens=350,
            temperature=1.0
        )
    except Exception as e:
        print(f"DeepSeek ошибка: {e}")
        return None

    answer = response.choices[0].message.content.strip()
    if not answer:
        return None

    history.append({"role": "assistant", "content": answer})
    return answer

def should_respond(message_content):
    content_lower = message_content.lower()
    for word in TRIGGER_WORDS:
        if word in content_lower:
            return True
    if len(message_content) > 20:
        return random.random() < 0.5
    return random.random() < 0.3

async def play_voice_phrase(channel):
    try:
        # Подключаемся к голосу (как в музыкальном боте)
        vc = channel.guild.voice_client
        if vc and vc.is_connected():
            await vc.move_to(channel)
        else:
            vc = await channel.connect()
        print("✅ Подключился к голосовому каналу")

        # Ищем файлы в папке
        audio_files = [f for f in os.listdir(AUDIO_FOLDER) if f.endswith(('.mp3', '.wav'))]
        if not audio_files:
            await channel.send("❌ Нет аудиофайлов!")
            await vc.disconnect()
            return

        # Выбираем случайный файл
        audio_file = random.choice(audio_files)
        audio_path = os.path.join(AUDIO_FOLDER, audio_file)
        print(f"🎵 Играю: {audio_path}")

        # БЕРЁМ ПАРАМЕТРЫ ИЗ МУЗЫКАЛЬНОГО БОТА (этот момент важен!)
        source = discord.FFmpegPCMAudio(
            audio_path,
            executable="/usr/bin/ffmpeg",  # Путь к ffmpeg (как в музыкальном боте)
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn"
        )

        # Ставим на воспроизведение
        vc.play(source)

        # Ждём, пока играет
        while vc.is_playing():
            await asyncio.sleep(0.5)

        await asyncio.sleep(0.5)
        await vc.disconnect()
        print("✅ Отключился")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        try:
            await channel.send(f"❌ Ошибка: {e}")
        except:
            pass
        try:
            await vc.disconnect()
        except:
            pass

@bot.event
async def on_ready():
    print(f"✅ Кощей (с голосом) запущен: {bot.user}")
    if not random_chat.is_running():
        random_chat.start()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.content.lower() in ["!зайди", "!голос", "!озвучь"]:
        if message.author.voice and message.author.voice.channel:
            channel = message.author.voice.channel
            await message.channel.send(f"🔊 Захожу в {channel.name}...")
            await play_voice_phrase(channel)
        else:
            await message.channel.send("❌ Ты должен быть в голосовом канале!")
        return

    if bot.user in message.mentions:
        text = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
        if not text:
            text = "чё скажешь?"
        async with message.channel.typing():
            await asyncio.sleep(random.uniform(0.5, 1.5))
            answer = await ask_ai(text, message.channel.id) or random.choice(KOSHCHEY_PHRASES)
            await message.reply(answer[:2000])
        return

    if should_respond(message.content):
        async with message.channel.typing():
            await asyncio.sleep(random.uniform(1.0, 3.0))
            answer = await ask_ai(message.content, message.channel.id) or random.choice(KOSHCHEY_PHRASES)
            if random.random() < 0.5:
                await message.reply(answer[:2000])
            else:
                await message.channel.send(answer[:2000])

@tasks.loop(minutes=5)
async def random_chat():
    if CHANNEL_ID == 0:
        return
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        return
    try:
        await channel.send(random.choice(KOSHCHEY_PHRASES))
    except Exception as e:
        print(f"Ошибка отправки: {e}")

@random_chat.before_loop
async def before_random_chat():
    await bot.wait_until_ready()

bot.run(DISCORD_TOKEN)
