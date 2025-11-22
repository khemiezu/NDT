# bot.py
import os
import asyncio
import tempfile
import shutil
import logging
import aiohttp
from pathlib import Path
from discord import Intents, File
from discord.ext import commands

# ------------- CONFIG -------------
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")  # set in Railway env
BACKGROUND = os.environ.get("BACKGROUND_PATH", "background.jpg")  # included in repo
FFMPEG = os.environ.get("FFMPEG_PATH", "ffmpeg")  # usually '/usr/bin/ffmpeg' on Linux
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", "2"))  # limit concurrency
# ----------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("overlay-bot")

intents = Intents.default()
intents.message_content = True  # required to read messages in some setups

bot = commands.Bot(command_prefix="!", intents=intents)
semaphore = asyncio.Semaphore(MAX_CONCURRENT)


async def download_attachment(url: str, dest_path: Path):
    """Download file via aiohttp (works with large files)."""
    timeout = aiohttp.ClientTimeout(total=None)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Download failed: {resp.status}")
            with open(dest_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 64):
                    f.write(chunk)


def build_ffmpeg_cmd(background: str, input_video: str, output_file: str):
    """
    Build ffmpeg command:
    - Scale background to 1080x1920 preserving aspect and pad black
    - Scale overlay to width 800 (height auto)
    - Overlay centered
    - 60 FPS, H.264, AAC
    """
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[bg];"
        "[1:v]scale=800:-2[ov];"
        "[bg][ov]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p"
    )

    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-i", background,  # input 0: background image
        "-i", input_video,               # input 1: overlay video
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "1:a?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-r", "60",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        output_file
    ]
    return cmd


@bot.event
async def on_ready():
    logger.info("Bot ready: %s", bot.user)


@bot.event
async def on_message(message):
    # ignore messages from the bot itself
    if message.author == bot.user:
        return

    # if the message has attachments, look for video-like attachments
    if message.attachments:
        # process the first attachment that looks like a video
        for att in message.attachments:
            # basic mime-type check; discord sends content_type sometimes
            if (att.content_type and att.content_type.startswith("video")) or att.filename.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi", ".hevc", ".m4v")):
                # spawn a background task so reading on_message remains fast
                asyncio.create_task(handle_video_mes_
