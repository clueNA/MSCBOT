import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from dotenv import load_dotenv

print("Current working directory:", os.getcwd())
print("Attempting to load .env file...")
load_dotenv("C:\\Users\\rupan\\PycharmProjects\\MSCBOT\\.env")  # Replace with your .env file path
print("Environment variables loaded")
print("Token value:", os.getenv('DISCORD_TOKEN'))

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'force-ipv4': True,
    'extractaudio': True,
    'audioformat': 'mp3',
    'audioquality': '192',
    'prefer_ffmpeg': True,
    'keepvideo': False
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

queues = {}

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None):
        loop = loop or asyncio.get_event_loop()
        ytdl = yt_dlp.YoutubeDL(ytdl_format_options)
        try:
            print(f"Attempting to extract info for URL: {url}")
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
            if data is None:
                raise ValueError("Could not extract video data")
            if 'entries' in data:
                data = data['entries'][0]
            if 'url' in data:
                print("Successfully extracted audio URL")
                filename = data['url']
                print(f"Using FFmpeg options: {ffmpeg_options}")
                return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
            else:
                raise ValueError("Could not extract audio URL from video")

        except Exception as e:
            print(f"Error in YTDLSource.from_url: {str(e)}")
            raise

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    print("Bot is ready!")
    await bot.change_presence(activity=discord.Game(name="!help for commands"))

@bot.command(name="play", help="Play audio from YouTube URL")
async def play(ctx, *, url):
    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []
    try:
        if not ctx.voice_client:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("❌ You need to be in a voice channel first!")
                return
        async with ctx.typing():
            try:
                loading_msg = await ctx.send("🔄 Processing video... Please wait.")
                player = await YTDLSource.from_url(url)
                if player is None:
                    await loading_msg.edit(content="❌ Could not process this video. Please try another URL.")
                    return
                queues[guild_id].append(player)
                if not ctx.voice_client.is_playing():
                    await play_next(ctx)
                    await loading_msg.edit(content=f"🎵 Now playing: **{player.title}**")
                else:
                    await loading_msg.edit(content=f"✅ Added to queue: **{player.title}**")
            except Exception as e:
                print(f"Error during playback: {str(e)}")
                await loading_msg.edit(content=f"❌ Error processing video: {str(e)}")
    except Exception as e:
        print(f"General error: {str(e)}")
        await ctx.send(f"❌ An error occurred: {str(e)}")

async def play_next(ctx):
    guild_id = ctx.guild.id
    if queues[guild_id]:
        player = queues[guild_id].pop(0)
        def after_playing(error):
            if error:
                print(f"Player error: {error}")
                asyncio.run_coroutine_threadsafe(ctx.send(f"❌ An error occurred while playing: {str(error)}"), bot.loop)
            else:
                asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)
        ctx.voice_client.play(player, after=after_playing)
    else:
        if ctx.voice_client:
            await ctx.send("Queue finished.")
            # Optionally disconnect after queue finishes:
            # await ctx.voice_client.disconnect()

@bot.command(name="clear", help="Clears the current queue")
async def clear_queue(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues:
        queues[guild_id].clear()
        await ctx.send("✅ Queue cleared!")
    else:
        await ctx.send("❌ No queue to clear.")

@bot.command(name="skip", help="Skips the current song")
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏩ Skipped the current song.")
    else:
        await ctx.send("❌ Nothing is playing to skip.")

@bot.command(name="queue", help="Displays the current queue")
async def view_queue(ctx):
    guild_id = ctx.guild.id
    if guild_id in queues:
        if queues[guild_id]:
            queue_list = ""
            for i, player in enumerate(queues[guild_id]):
                queue_list += f"{i+1}. **{player.title}**\n"
            embed = discord.Embed(title="Current Queue", description=queue_list, color=discord.Color.blue())
            await ctx.send(embed=embed)
        else:
            await ctx.send("The queue is currently empty.")
    else:
        await ctx.send("There is no queue for this server.")

@bot.command(name="join")
async def join(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ You're not in a voice channel!")
        return
    channel = ctx.author.voice.channel
    if ctx.voice_client is not None:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()
    await ctx.send(f"✅ Joined {channel.name}")

@bot.command(name="leave")
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Left the voice channel")
    else:
        await ctx.send("❌ I'm not in a voice channel!")

@bot.command(name="pause")
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ Paused the current song")
    else:
        await ctx.send("❌ Nothing is playing right now")

@bot.command(name="resume")
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ Resumed the song")
    else:
        await ctx.send("❌ Nothing is paused right now")

@bot.command(name="stop")
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.send("⏹️ Stopped the current song")
    else:
        await ctx.send("❌ Nothing is playing right now")

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if token:
        print("Token found in environment variables")
        bot.run(token)
    else:
        print("Token not found in environment variables, using direct token")
        bot.run('RePlAcE_ThIs') #REPLACE THIS
