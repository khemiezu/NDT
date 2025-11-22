import os
import asyncio
import tempfile
import shutil
import logging
import aiohttp
from pathlib import Path
from discord import Intents, File
from discord.ext import commands

# ------------ CONFIG ------------
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
BACKGROUND = os.environ.get("BACKGROUND_PATH", "background.jpg")
FFMPEG = os.environ.get("FFMPEG_PATH", "ffmpeg")
MAX_CONCURRENT = int(os.environ.get("MAX_CONCURRENT", "2"))
# --------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("overlaybot")

intents = Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
semaphore = asyncio.Semaphore(MAX_CONCURRENT)


async def download_attachment(url: str, dest: Path):
    timeout = aiohttp.ClientTimeout(total=None)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Download failed: {resp.status}")
            with open(dest, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)


def build_ffmpeg(background: str, input_video: str, output: str):
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[bg];"
        "[1:v]scale=800:-2[ov];"
        "[bg][ov]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p"
    )

    return [
        FFMPEG, "-y",
        "-loop", "1", "-i", background,
        "-i", input_video,
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
        output
    ]


@bot.event
async def on_ready():
    logger.info(f"Bot is ready: {bot.user}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.attachments:
        for att in message.attachments:
            filename = att.filename.lower()
            if (
                (att.content_type and att.content_type.startswith("video"))
                or filename.endswith((".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"))
            ):
                asyncio.create_task(handle_video_message(message, att))
                break

    await bot.process_commands(message)


async def handle_video_message(message, attachment):
    async with semaphore:
        tmp = Path(tempfile.mkdtemp(prefix="overlay-"))
        try:
            input_path = tmp / ("input" + Path(attachment.filename).suffix)
            output_path = tmp / "output.mp4"

            await message.channel.send(f"Downloading `{attachment.filename}` ...")
            await download_attachment(attachment.url, input_path)

            await message.channel.send("Processing video, please wait...")

            cmd = build_ffmpeg(BACKGROUND, str(input_path), str(output_path))

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            out, err = await proc.communicate()

            if proc.returncode != 0 or not output_path.exists():
                logger.error(err.decode(errors="ignore"))
                await message.channel.send("FFmpeg failed to process the video.")
                return

            try:
                await message.channel.send("Uploading result...")
                await message.channel.send(file=File(str(output_path)))
            except Exception as e:
                await message.channel.send(f"Upload failed: {e}")

        except Exception as e:
            logger.exception(e)
            await message.channel.send(f"Error: {e}")
        finally:
            try:
                shutil.rmtree(tmp)
            except:
                pass


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN not set")
        exit(1)
    bot.run(DISCORD_TOKEN)
