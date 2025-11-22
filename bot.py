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

    # Only accept videos
    if not att.filename.lower().endswith((".mp4", ".mov", ".m4v")):
        return

    await message.channel.send(f"Downloading `{att.filename}` ...")

    # Make temp dir
    tmp = f"/tmp/overlay-{os.urandom(4).hex()}"
    os.makedirs(tmp, exist_ok=True)

    input_path = f"{tmp}/input{os.path.splitext(att.filename)[1]}"
    output_path = f"{tmp}/output.mp4"

    # download
    await att.save(input_path)

    await message.channel.send("Processing video with FFmpeg, please wait...")

    # FIXED FILTER — WORKS FOR ALL iPHONE VIDEOS
    ffmpeg_cmd = [
        FFMPEG,
        "-y",
        "-i", BACKGROUND_PATH,
        "-i", input_path,
        "-filter_complex",
        (
            "scale2ref=w=800:h=trunc(ow/a/2)*2[ov][bg];"  # ensure even height
            "[bg][ov]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p"
        ),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-r", "60",            # force 60fps
        output_path
    ]

    # run ffmpeg
    try:
        proc = subprocess.run(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            await message.channel.send(
                "**FFmpeg ERROR:**\n```"
                + proc.stderr.decode(errors="ignore")[:1900]
                + "```"
            )
            return
    except Exception as e:
        await message.channel.send(f"FFmpeg crashed:\n`{e}`")
        return

    await message.channel.send("Uploading final video...")
    await message.channel.send(file=discord.File(output_path))

    # cleanup
    try:
        os.remove(input_path)
        os.remove(output_path)
        os.rmdir(tmp)
    except:
        pass


bot.run(TOKEN)
