import asyncio
import json
import logging
import os

import aiofiles
import inquirer
import yaml
from aiolimiter import AsyncLimiter
from colorama import Fore, Style, init
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import (DocumentAttributeVideo, MessageMediaDocument,
                               MessageMediaPhoto)
from tqdm.asyncio import tqdm

init(autoreset=True)

# Setup logging
logging.basicConfig(filename='telegram_downloader.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load configuration
def load_config():
    with open('config.yaml', 'r') as f:
        return yaml.safe_load(f)

config = load_config()

api_id = config['api_id']
api_hash = config['api_hash']
phone_number = config['phone_number']

client = TelegramClient('session', api_id, api_hash)

MAX_CONCURRENT_DOWNLOADS = config['max_concurrent_downloads']
RATE_LIMIT = config['rate_limit']
HISTORY_FILE = 'download_history.json'

rate_limiter = AsyncLimiter(RATE_LIMIT['max_rate'], RATE_LIMIT['time_period'])

def process_channel_input(channel_input):
    if channel_input.startswith('@'):
        return channel_input
    elif channel_input.lstrip('-').isdigit():
        num = int(channel_input)
        return num if num > 0 else int(f"-100{abs(num)}")
    return channel_input

def load_download_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_download_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

async def list_media(channel, limit=None):
    logger.info(f"Scanning for media in channel: {channel}")
    media = []
    async for message in tqdm(client.iter_messages(channel, limit=limit), desc="Scanning messages"):
        if message.media:
            if isinstance(message.media, MessageMediaDocument):
                if 'video' in message.file.mime_type:
                    video_attr = next((attr for attr in message.document.attributes if isinstance(attr, DocumentAttributeVideo)), None)
                    if video_attr:
                        media.append({
                            'type': 'video',
                            'name': message.file.name,
                            'size': message.file.size,
                            'id': message.id,
                            'width': video_attr.w,
                            'height': video_attr.h,
                            'duration': video_attr.duration
                        })
                else:
                    media.append({
                        'type': 'document',
                        'name': message.file.name,
                        'size': message.file.size,
                        'id': message.id
                    })
            elif isinstance(message.media, MessageMediaPhoto):
                # Handle different types of photo sizes
                sizes = message.photo.sizes
                largest_size = max(sizes, key=lambda s: getattr(s, 'size', 0) if hasattr(s, 'size') else 0)
                photo_size = getattr(largest_size, 'size', 0)
                
                media.append({
                    'type': 'photo',
                    'id': message.id,
                    'size': photo_size
                })
    return media

async def download_media(message, download_dir, semaphore, history):
    media_type = 'photo' if isinstance(message.media, MessageMediaPhoto) else 'file'
    filename = f"{message.id}.jpg" if media_type == 'photo' else message.file.name
    path = os.path.join(download_dir, filename)
    temp_path = f"{path}.part"
    
    if os.path.exists(path) or str(message.id) in history.get(str(message.chat_id), {}):
        logger.info(f"File {filename} already exists or was previously downloaded. Skipping.")
        return 0

    async with semaphore:
        try:
            downloaded_size = 0
            if os.path.exists(temp_path):
                downloaded_size = os.path.getsize(temp_path)
            
            with tqdm(total=message.file.size, initial=downloaded_size, unit='B', unit_scale=True, desc=filename, ncols=100) as progress_bar:
                async def progress_callback(current, total):
                    progress_bar.update(current - progress_bar.n)
                
                await rate_limiter.acquire()
                await message.download_media(file=temp_path, progress_callback=progress_callback)
            
            os.rename(temp_path, path)
            logger.info(f"Downloaded: {filename}")
            
            history.setdefault(str(message.chat_id), {})[str(message.id)] = {
                'filename': filename,
                'size': message.file.size,
                'timestamp': message.date.isoformat()
            }
            save_download_history(history)
            
            return 1
        except asyncio.TimeoutError:
            logger.error(f"Timeout while downloading {filename}. Retrying...")
            return await download_media(message, download_dir, semaphore, history)
        except Exception as e:
            logger.error(f"Error downloading {filename}: {str(e)}")
            return 0

async def download_media_list(channel, selected_media, download_dir='downloads'):
    os.makedirs(download_dir, exist_ok=True)

    logger.info(f"Downloading selected media to {download_dir}")
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    history = load_download_history()
    
    tasks = [download_media(await client.get_messages(channel, ids=media['id']), download_dir, semaphore, history)
             for media in selected_media]
    
    results = await asyncio.gather(*tasks)
    downloaded = sum(results)
    
    logger.info(f"Download complete. Total media downloaded: {downloaded}")

async def display_channel_info(channel):
    try:
        channel_entity = await client.get_entity(channel)
        logger.info(f"Channel Information: {channel_entity.title}")
        print(f"{Fore.CYAN}Channel Information:")
        print(f"Title: {channel_entity.title}")
        print(f"Username: {channel_entity.username or 'N/A'}")
        if hasattr(channel_entity, 'participants_count'):
            print(f"Participants: {channel_entity.participants_count}")
    except Exception as e:
        logger.error(f"Error fetching channel information: {str(e)}")

def get_media_quality(media):
    if media['type'] != 'video':
        return 'N/A'
    if media['width'] >= 1920 or media['height'] >= 1080:
        return 'HD'
    elif media['width'] >= 1280 or media['height'] >= 720:
        return 'HD Ready'
    else:
        return 'SD'

def get_media_display_name(media, downloaded=False):
    name = media.get('name', f"Unknown-{media['id']}")
    if media['type'] == 'photo':
        name = f"Photo-{media['id']}"
    
    size = f"{media['size'] / 1024 / 1024:.2f} MB"
    media_type = media['type'].capitalize()
    quality = get_media_quality(media)
    
    if downloaded:
        return f"{Fore.GREEN}{name} ({size}) - {media_type} - {quality} [DOWNLOADED]{Style.RESET_ALL}"
    else:
        return f"{name} ({size}) - {media_type} - {quality}"

async def main_menu():
    channel = None
    media = []
    download_history = load_download_history()
    
    while True:
        if not channel:
            channel_input = input(f"{Fore.CYAN}Enter channel ID or username (or 'exit' to quit): ")
            if channel_input.lower() == 'exit':
                break
            channel = process_channel_input(channel_input)
            logger.info(f"Processed channel identifier: {channel}")
            await display_channel_info(channel)
            
            limit = input(f"{Fore.CYAN}Enter message limit (or press Enter for no limit): ")
            limit = int(limit) if limit else None
            
            media = await list_media(channel, limit)
            
            if not media:
                logger.warning("No media found in the specified range.")
                channel = None
                continue
        
        choices = [
            inquirer.List('action',
                          message="What would you like to do?",
                          choices=[
                              ('Select and download media', 'download'),
                              ('Change channel', 'change_channel'),
                              ('Exit', 'exit')
                          ],
                          ),
        ]
        answers = inquirer.prompt(choices)
        
        if answers['action'] == 'exit':
            break
        elif answers['action'] == 'change_channel':
            channel = None
            media = []
            continue
        
        # Update the display names with download status
        channel_history = download_history.get(str(channel), {})
        media_choices = [
            (get_media_display_name(m, str(m['id']) in channel_history), m['id'])
            for m in media
        ]
        
        media_selection = [
            inquirer.Checkbox('selected_media',
                              message="Select media to download",
                              choices=media_choices)
        ]
        
        selected = inquirer.prompt(media_selection)['selected_media']
        selected_media = [m for m in media if m['id'] in selected]
        
        if selected_media:
            total_size = sum(m['size'] for m in selected_media)
            logger.info(f"Total download size: {total_size / 1024 / 1024:.2f} MB")
            
            download_dir = input(f"{Fore.CYAN}Enter download directory (or press Enter for default '{config['default_download_dir']}'): ")
            download_dir = download_dir or config['default_download_dir']
            await download_media_list(channel, selected_media, download_dir)
            
            # Update download history
            channel_history = download_history.setdefault(str(channel), {})
            for m in selected_media:
                channel_history[str(m['id'])] = {
                    'filename': m.get('name', f"Unknown-{m['id']}"),
                    'size': m['size'],
                    'timestamp': m.get('date', 'Unknown date')
                }
            save_download_history(download_history)
        else:
            logger.warning("No media selected for download.")
        
        print(f"{Fore.YELLOW}Returning to media selection...")

async def main():
    await client.start(phone=phone_number)
    logger.info("Client Created")
    
    if not await client.is_user_authorized():
        await client.send_code_request(phone_number)
        try:
            code = input(f"{Fore.YELLOW}Enter the code: ")
            await client.sign_in(phone_number, code)
        except SessionPasswordNeededError:
            password = input(f"{Fore.YELLOW}Enter your 2FA password: ")
            await client.sign_in(password=password)

    await main_menu()
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())