import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio

# Set up the bot
intents = discord.Intents.default()
intents.messages = True  # Required for reading messages
intents.guilds = True
intents.voice_states = True  # Required for voice channel functionality

bot = commands.Bot(command_prefix='!', intents=intents)

# Set up youtube-dl options
ytdl_format_options = {
    "format": "bestaudio/best",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data):
        super().__init__(source)
        self.data = data
        self.title = data.get("title")
        self.url = ""

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream)
)

        if "entries" in data:  # If it's a playlist, get the first entry
            data = data["entries"][0]

        filename = data["url"] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename), data=data)

@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")

@bot.command()
async def ping(ctx):
    await ctx.send('Pong!')

@bot.command()
async def join(ctx):
    """Join the voice channel."""
    if not ctx.author.voice:
        await ctx.send("You're not in a voice channel!")
        return
    channel = ctx.author.voice.channel
    await channel.connect()

@bot.command()
async def play(ctx, url):
    """Play audio from a YouTube URL or playlist."""
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if not voice_client:
        await ctx.send("I'm not connected to a voice channel!")
        return

    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        voice_client.play(player, after=lambda e: print(f"Player error: {e}") if e else None)

    await ctx.send(f"Now playing: {player.title}")

@bot.command()
async def leave(ctx):
    """Leave the voice channel."""
    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
    if voice_client:
        await voice_client.disconnect()
    else:
        await ctx.send("I'm not connected to a voice channel!")

# Replace 'YOUR_TOKEN_HERE' with your bot's token
bot.run('YOUR_TOKEN_HERE')
