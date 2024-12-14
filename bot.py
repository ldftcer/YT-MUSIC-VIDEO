from pyrogram import Client, filters
import yt_dlp
import os
import subprocess
import requests
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import re
import logging
import asyncio

# Logging configuration
logging.basicConfig(level=logging.INFO)

# Bot credentials
TOKEN = '7246695508:AAFynFXANrHO-JoQw1Sxdou_ln9M7-NWQIY'
API_ID = '23124608'
API_HASH = '0a612aa8f1c8f5eaf60eaadb73ab8e27'

# Initialize bot
app = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=TOKEN)

# Store user data during sessions
user_data = {}

# Utility: Sanitize filenames
def clean_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', '_', filename)

# Utility: Check if URL is a playlist
def is_playlist(url):
    return "list=" in url

# Start command handler
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_animation(
        animation="https://media.giphy.com/media/3o6Zt481isNVuQI1l6/giphy.gif",
        caption="🎉 Бот YouTube-загрузчик готов к работе! 📽\nОтправьте ссылку на видео, чтобы начать."
    )

# Handle YouTube links
@app.on_message(filters.text & ~filters.command("start"))
async def ask_video_or_audio(client, message):
    url = message.text.strip()
    if not re.match(r'(https?://)?(www\.)?(youtube|youtu\.be)(\.com)?/.+', url):
        await message.reply_text('🚫 Укажите корректную ссылку на YouTube.')
        return

    user_data[message.chat.id] = {'url': url, 'is_downloading': False}

    try:
        ydl_opts = {'format': 'best', 'noplaylist': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            thumbnail = info.get('thumbnail', None)
            title = info.get('title', 'Видео')

            if thumbnail:
                response = requests.get(thumbnail, stream=True)
                if response.status_code == 200:
                    thumb_path = "thumbnail.jpg"
                    with open(thumb_path, 'wb') as f:
                        for chunk in response.iter_content(1024):
                            f.write(chunk)

                    await client.send_photo(
                        message.chat.id,
                        photo=thumb_path,
                        caption=f"🎬 Что вы хотите загрузить: аудио или видео? `{title}`",
                        reply_markup=video_selection_keyboard()
                    )
                    os.remove(thumb_path)
                else:
                    await message.reply_text("⚠️ Не удалось получить миниатюру видео.")
            else:
                await message.reply_text("⚠️ Миниатюра для видео отсутствует.")

    except Exception as e:
        await message.reply_text(f'⚠️ Ошибка при обработке видео: {e}')

# Inline keyboard for video or audio selection
def video_selection_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎥 Видео", callback_data='video')],
        [InlineKeyboardButton("🎵 Аудио", callback_data='audio')]
    ]
    return InlineKeyboardMarkup(keyboard)

# Inline keyboard for video quality selection
def quality_keyboard():
    keyboard = [
        [InlineKeyboardButton("144p", callback_data='144')],
        [InlineKeyboardButton("240p", callback_data='240')],
        [InlineKeyboardButton("360p", callback_data='360')],
        [InlineKeyboardButton("480p", callback_data='480')],
        [InlineKeyboardButton("720p", callback_data='720')],
        [InlineKeyboardButton("1080p", callback_data='1080')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back')]
    ]
    return InlineKeyboardMarkup(keyboard)

# Handle callback queries
@app.on_callback_query()
async def button_click(client, callback_query):
    await callback_query.answer()
    chat_id = callback_query.message.chat.id
    choice = callback_query.data

    if choice == 'video':
        user_data[chat_id]['choice'] = 'video'
        await callback_query.edit_message_text('📺 Выберите качество:', reply_markup=quality_keyboard())

    elif choice in ['144', '240', '360', '480', '720', '1080']:
        user_data[chat_id]['quality'] = choice
        await download_video(chat_id, callback_query)

    elif choice == 'audio':
        user_data[chat_id]['choice'] = 'audio'
        await download_audio(chat_id, callback_query)

    elif choice == 'back':
        await callback_query.edit_message_text('🎬 Выберите, что скачать: аудио или видео.', reply_markup=video_selection_keyboard())

async def download_audio(chat_id, callback_query):
    if user_data[chat_id]['is_downloading']:
        await callback_query.message.reply_text("⏳ Запрос уже обрабатывается. Пожалуйста, подождите.")
        return

    user_data[chat_id]['is_downloading'] = True
    url = user_data[chat_id]['url']
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'noplaylist': True,
    }

    os.makedirs('downloads', exist_ok=True)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            title = clean_filename(info.get('title', 'Без названия'))
            file_name = ydl.prepare_filename(info).replace('.webm', '.mp3').replace('.m4a', '.mp3')
        
        await send_audio_file(callback_query, file_name, title)

    except Exception as e:
        await callback_query.message.reply_text(f'⚠️ Ошибка: {e}')
    finally:
        user_data[chat_id]['is_downloading'] = False

async def send_audio_file(callback_query, file_name, title):
    if os.path.exists(file_name):
        new_file_name = os.path.join('downloads', f"{title}.mp3")
        os.rename(file_name, new_file_name)

        await callback_query.message.reply_audio(
            audio=open(new_file_name, 'rb'),
            title=title,
            performer='YouTube Bot',
            caption="📥 Скачать файл"
        )
        os.remove(new_file_name)
    else:
        await callback_query.message.reply_text(f'⚠️ Файл не найден: {file_name}')

async def download_video(chat_id, callback_query):
    if user_data[chat_id]['is_downloading']:
        await callback_query.message.reply_text("⏳ Запрос уже обрабатывается. Пожалуйста, подождите.")
        return

    user_data[chat_id]['is_downloading'] = True
    url = user_data[chat_id]['url']
    quality = user_data[chat_id]['quality']

    try:
        ydl_opts = {
            'format': f'bestvideo[height<={quality}]+bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'noplaylist': True,
        }

        os.makedirs('downloads', exist_ok=True)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=True)
            title = clean_filename(info.get('title', 'Без названия'))
            file_name = ydl.prepare_filename(info)

        compressed_file = os.path.join('downloads', f"{title}_compressed.mp4")
        command = [
            'ffmpeg', '-i', file_name, '-vf', 'scale=1280:720', '-c:v', 'libx264',
            '-preset', 'fast', '-crf', '28', '-c:a', 'aac', compressed_file
        ]
        await asyncio.to_thread(subprocess.run, command, check=True)

        if os.path.exists(compressed_file):
            await callback_query.message.reply_video(
                video=open(compressed_file, 'rb'),
                caption=f"📥 {title}"
            )
            os.remove(compressed_file)
        else:
            await callback_query.message.reply_text(f'⚠️ Файл не найден: {compressed_file}')

        if os.path.exists(file_name):
            os.remove(file_name)

    except Exception as e:
        await callback_query.message.reply_text(f'⚠️ Ошибка: {e}')
    finally:
        user_data[chat_id]['is_downloading'] = False

# Run the bot
if __name__ == "__main__":
    app.run()
