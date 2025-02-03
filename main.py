
import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

print("Current working directory:", os.getcwd())
print("Attempting to load .env file...")
load_dotenv(".env")
print("Environment variables loaded")

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
    'noplaylist': False,  # Allow playlist support
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


class MusicBot:
    def __init__(self):
        self.queues = {}
        self.current_track = {}
        self.loop_mode = {}  # 0: disabled, 1: single track, 2: queue
        self.start_time = {}

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = []
            self.loop_mode[guild_id] = 0
        return self.queues[guild_id]


music_bot = MusicBot()


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.thumbnail = data.get('thumbnail')
        self.requester = None

    @classmethod
    async def from_url(cls, url, *, loop=None, requester=None):
        loop = loop or asyncio.get_event_loop()
        ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

        try:
            print(f"Attempting to extract info for URL: {url}")
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

            if data is None:
                raise ValueError("Could not extract video data")

            # Handle playlists
            if 'entries' in data:
                sources = []
                for entry in data['entries']:
                    if entry:
                        filename = entry['url']
                        source = cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=entry)
                        source.requester = requester
                        sources.append(source)
                return sources
            else:
                filename = data['url']
                source = cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
                source.requester = requester
                return [source]

        except Exception as e:
            print(f"Error in YTDLSource.from_url: {str(e)}")
            raise


@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    print("Bot is ready!")
    await bot.change_presence(activity=discord.Game(name="!help for commands"))


async def check_inactive():
    while True:
        for voice_client in bot.voice_clients:
            if not voice_client.is_playing() and not voice_client.is_paused():
                await voice_client.disconnect()
        await asyncio.sleep(300)  # Check every 5 minutes


@bot.command(name="play", help="Play audio from YouTube URL")
async def play(ctx, *, query):
    if not query:
        await ctx.send("❌ Please provide a URL or search term!")
        return

    try:
        if not ctx.voice_client:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("❌ You need to be in a voice channel first!")
                return

        async with ctx.typing():
            loading_msg = await ctx.send("🔄 Processing... Please wait.")

            if not query.startswith(('http://', 'https://')):
                query = f"ytsearch:{query}"

            sources = await YTDLSource.from_url(query, requester=ctx.author)

            if not sources:
                await loading_msg.edit(content="❌ Could not find any videos. Please try another search.")
                return

            guild_queue = music_bot.get_queue(ctx.guild.id)

            for source in sources:
                guild_queue.append(source)

            if not ctx.voice_client.is_playing():
                await play_next(ctx)
                await loading_msg.edit(content=f"🎵 Now playing: **{sources[0].title}**")
            else:
                plural = 's' if len(sources) > 1 else ''
                await loading_msg.edit(content=f"✅ Added {len(sources)} track{plural} to queue!")

    except Exception as e:
        print(f"Error during playback: {str(e)}")
        await ctx.send(f"❌ An error occurred: {str(e)}")


async def play_next(ctx):
    guild_id = ctx.guild.id
    guild_queue = music_bot.get_queue(guild_id)

    if not guild_queue:
        await ctx.send("Queue finished.")
        return

    if music_bot.loop_mode[guild_id] == 1:  # Single track loop
        current = music_bot.current_track[guild_id]
        if current:
            guild_queue.insert(0, current)
    elif music_bot.loop_mode[guild_id] == 2:  # Queue loop
        if music_bot.current_track[guild_id]:
            guild_queue.append(music_bot.current_track[guild_id])

    next_track = guild_queue.pop(0)
    music_bot.current_track[guild_id] = next_track
    music_bot.start_time[guild_id] = datetime.now()

    embed = discord.Embed(
        title="Now Playing",
        description=f"🎵 **{next_track.title}**",
        color=discord.Color.blue()
    )
    embed.add_field(name="Requested by", value=next_track.requester.mention)
    if next_track.duration:
        embed.add_field(name="Duration", value=str(timedelta(seconds=next_track.duration)))
    if next_track.thumbnail:
        embed.set_thumbnail(url=next_track.thumbnail)

    await ctx.send(embed=embed)

    def after_playing(error):
        if error:
            print(f"Player error: {error}")
            asyncio.run_coroutine_threadsafe(
                ctx.send(f"❌ An error occurred while playing: {str(error)}"),
                bot.loop
            )
        else:
            asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)

    ctx.voice_client.play(
        next_track,
        after=after_playing
    )


@bot.command(name="skip", help="Skip the currently playing track")
async def skip(ctx):
    if not ctx.voice_client:
        return await ctx.send("❌ I'm not connected to a voice channel!")

    if not ctx.voice_client.is_playing():
        return await ctx.send("❌ Nothing is playing right now!")

    ctx.voice_client.stop()
    await ctx.send("⏭️ Skipped the current track!")


@bot.command(name="stop", help="Stop playback and disconnect the bot")
async def stop(ctx):
    if not ctx.voice_client:
        return await ctx.send("❌ I'm not connected to a voice channel!")

    guild_id = ctx.guild.id

    # Clear the queue
    music_bot.queues[guild_id] = []
    music_bot.current_track[guild_id] = None

    # Stop playback and disconnect
    ctx.voice_client.stop()
    await ctx.voice_client.disconnect()
    await ctx.send("⏹️ Playback stopped and queue cleared!")


@bot.command(name="pause", help="Pause the current track")
async def pause(ctx):
    if not ctx.voice_client:
        return await ctx.send("❌ I'm not connected to a voice channel!")

    if not ctx.voice_client.is_playing():
        return await ctx.send("❌ Nothing is playing right now!")

    if ctx.voice_client.is_paused():
        return await ctx.send("⚠️ The track is already paused!")

    ctx.voice_client.pause()
    await ctx.send("⏸️ Paused the current track!")


@bot.command(name="resume", help="Resume playback of a paused track")
async def resume(ctx):
    if not ctx.voice_client:
        return await ctx.send("❌ I'm not connected to a voice channel!")

    if not ctx.voice_client.is_paused():
        return await ctx.send("❌ The track is not paused!")

    ctx.voice_client.resume()
    await ctx.send("▶️ Resumed playback!")


@bot.command(name="queue", help="Display the current music queue")
async def queue(ctx):
    guild_id = ctx.guild.id
    queue = music_bot.get_queue(guild_id)

    if not queue and guild_id not in music_bot.current_track:
        return await ctx.send("📪 Queue is empty and nothing is playing!")

    embed = discord.Embed(
        title="Music Queue",
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )

    # Add current track
    if guild_id in music_bot.current_track and music_bot.current_track[guild_id]:
        current = music_bot.current_track[guild_id]
        duration = str(timedelta(seconds=current.duration)) if current.duration else "Unknown"
        embed.add_field(
            name="🎵 Now Playing",
            value=f"**{current.title}**\nDuration: {duration}\nRequested by: {current.requester.mention}",
            inline=False
        )

    # Add queued tracks
    if queue:
        queue_text = ""
        for i, track in enumerate(queue[:10], 1):
            duration = str(timedelta(seconds=track.duration)) if track.duration else "Unknown"
            queue_text += f"`{i}.` **{track.title}** | {duration} | Requested by: {track.requester.mention}\n"

        if len(queue) > 10:
            queue_text += f"\n*and {len(queue) - 10} more tracks...*"

        embed.add_field(name="📑 Up Next", value=queue_text or "No tracks in queue", inline=False)

    # Add loop mode status
    loop_modes = ["Disabled", "Single Track", "Queue"]
    current_loop = loop_modes[music_bot.loop_mode.get(guild_id, 0)]
    embed.add_field(name="🔄 Loop Mode", value=current_loop, inline=False)

    await ctx.send(embed=embed)


@bot.command(name="clear", help="Clear the music queue")
async def clear(ctx):
    guild_id = ctx.guild.id

    if guild_id not in music_bot.queues or not music_bot.queues[guild_id]:
        return await ctx.send("❌ The queue is already empty!")

    queue_length = len(music_bot.queues[guild_id])
    music_bot.queues[guild_id] = []

    await ctx.send(f"🗑️ Cleared {queue_length} tracks from the queue!")


@bot.command(name="loop", help="Changes loop mode (off/track/queue)")
async def loop(ctx, mode=""):
    guild_id = ctx.guild.id

    if mode.lower() in ["off", "disable", "0"]:
        music_bot.loop_mode[guild_id] = 0
        await ctx.send("🔄 Loop mode: Disabled")
    elif mode.lower() in ["track", "song", "1"]:
        music_bot.loop_mode[guild_id] = 1
        await ctx.send("🔄 Loop mode: Single Track")
    elif mode.lower() in ["queue", "all", "2"]:
        music_bot.loop_mode[guild_id] = 2
        await ctx.send("🔄 Loop mode: Queue")
    else:
        current_mode = ["Disabled", "Single Track", "Queue"][music_bot.loop_mode[guild_id]]
        await ctx.send(f"🔄 Current loop mode: {current_mode}\nUse `!loop off/track/queue` to change")


@bot.command(name="np", help="Shows information about the currently playing track")
async def now_playing(ctx):
    guild_id = ctx.guild.id

    if not ctx.voice_client or not ctx.voice_client.is_playing():
        return await ctx.send("❌ Nothing is playing right now!")

    track = music_bot.current_track[guild_id]
    started = music_bot.start_time[guild_id]
    position = (datetime.now() - started).total_seconds()

    embed = discord.Embed(title="Now Playing", color=discord.Color.blue())
    embed.add_field(name="Title", value=track.title, inline=False)
    embed.add_field(name="Requested by", value=track.requester.mention)

    if track.duration:
        duration = str(timedelta(seconds=int(track.duration)))
        current = str(timedelta(seconds=int(position)))
        embed.add_field(name="Time", value=f"{current}/{duration}")

    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)

    await ctx.send(embed=embed)


@bot.command(name="remove", help="Removes a track from the queue by its number")
async def remove(ctx, position: int):
    guild_id = ctx.guild.id
    queue = music_bot.get_queue(guild_id)

    if not 1 <= position <= len(queue):
        await ctx.send("❌ Invalid track number!")
        return

    removed = queue.pop(position - 1)
    await ctx.send(f"✂️ Removed: **{removed.title}**")


if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("Error: DISCORD_TOKEN not found in environment variables")
        exit(1)
    bot.run(token)
