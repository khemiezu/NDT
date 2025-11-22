import os
import discord
import asyncio
import subprocess
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
BACKGROUND_PATH = "background.jpg"
FFMPEG = "/usr/bin/ffmpeg"

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Bot is ready: {bot.user}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if not message.attachments:
        return

    att = message.attachments[0]

    if not att.filename.lower().endswith((".mp4", ".mov", ".m4v")):
        return

    await message.channel.send(f"Downloading `{att.filename}` ...")

    tmp = f"/tmp/overlay-{os.urandom(4).hex()}"
    os.makedirs(tmp, exist_ok=True)

    input_path = f"{tmp}/input{os.path.splitext(att.filename)[1]}"
    output_path = f"{tmp}/output.mp4"

    await att.save(input_path)

    await message.channel.send("Processing video with FFmpeg, please wait...")

    # NEW FIXED FILTER
    filter_complex = (
        "[1:v]scale=800:-2,format=yuv420p[ov];"
        "[0:v][ov]overlay=(W-w)/2:(H-h)/2:shortest=1"
    )

    ffmpeg_cmd = [
        FFMPEG,
        "-y",
        "-i", BACKGROUND_PATH,
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "1:a?",           # Audio optional
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-r", "60",
        "-c:a", "aac",
        "-b:a", "128k",
        output_path
    ]

    proc = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if proc.returncode != 0:
        await message.channel.send(
            "**FFmpeg ERROR:**\n```"
            + proc.stderr.decode(errors="ignore")[:1800]
            + "```"
        )
        return

    await message.channel.send("Uploading final video...")
    await message.channel.send(file=discord.File(output_path))

    try:
        os.remove(input_path)
        os.remove(output_path)
        os.rmdir(tmp)
    except:
        pass
