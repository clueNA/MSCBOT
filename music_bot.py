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
    'noplaylist': False,
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
    'keepvideo': False,
    'playlist_items': '1-50',
    'extract_flat': 'in_playlist',
    'lazy_playlist': True,
    'concurrent_fragment_downloads': 3,
    'buffersize': 1024,
    'postprocessor_args': ['-threads', '4'],
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -reconnect_attempts 5',
    'options': '-vn -threads 4 -bufsize 2048k'
}


class MusicBot:
    def __init__(self):
        self.queues = {}
        self.current_track = {}
        self.start_time = {}
        self.processing_playlists = {}
        self.voice_states = {}

    def get_queue(self, guild_id):
        if guild_id not in self.queues:
            self.queues[guild_id] = []
            self.processing_playlists[guild_id] = False
        return self.queues[guild_id]


music_bot = MusicBot()


class YTDLSource(discord.PCMVolumeTransformer):
    MAX_RETRIES = 3

    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.duration = data.get('duration')
        self.thumbnail = data.get('thumbnail')
        self.requester = None

    @classmethod
    async def create_source(cls, entry, requester, retry_count=0):
        try:
            filename = entry.get('url') or entry.get('webpage_url')
            if not filename:
                raise ValueError("No valid URL found in entry")

            source = cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=entry)
            source.requester = requester
            return source
        except Exception as e:
            if retry_count < cls.MAX_RETRIES:
                print(f"Error creating source, retrying ({retry_count + 1}/{cls.MAX_RETRIES}): {str(e)}")
                await asyncio.sleep(1)
                return await cls.create_source(entry, requester, retry_count + 1)
            print(f"Failed to create source after {cls.MAX_RETRIES} attempts: {str(e)}")
            return None

    @classmethod
    async def from_url(cls, ctx, url, *, loop=None, requester=None):
        loop = loop or asyncio.get_event_loop()
        ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

        try:
            processing_msg = await ctx.send("🔄 Processing request...")
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

            if data is None:
                await processing_msg.edit(content="❌ Could not extract video data")
                return []

            if 'entries' in data:
                await processing_msg.edit(content=f"📋 Processing playlist: {data.get('title', 'Unknown Playlist')}")
                entries = list(filter(None, data['entries']))

                if not entries:
                    await processing_msg.edit(content="❌ No valid entries found in playlist")
                    return []

                first_source = await cls.create_source(entries[0], requester)
                sources = [first_source] if first_source else []

                if len(entries) > 1:
                    guild_id = ctx.guild.id
                    music_bot.processing_playlists[guild_id] = True
                    loop.create_task(cls._process_playlist_items(ctx, entries[1:], requester, guild_id))

                await processing_msg.edit(
                    content=f"✅ Added first track from playlist\n💫 Processing remaining {len(entries) - 1} tracks in background")
                return sources
            else:
                source = await cls.create_source(data, requester)
                await processing_msg.edit(content=f"✅ Processed track: {data.get('title', 'Unknown')}")
                return [source] if source else []

        except Exception as e:
            print(f"Error in from_url: {str(e)}")
            await processing_msg.edit(content=f"❌ Error: {str(e)}")
            return []

    @classmethod
    async def _process_playlist_items(cls, ctx, entries, requester, guild_id):
        try:
            queue = music_bot.get_queue(guild_id)
            total = len(entries)
            processed = 0

            for entry in entries:
                if entry:
                    source = await cls.create_source(entry, requester)
                    if source:
                        queue.append(source)
                        processed += 1
                        if processed % 5 == 0:
                            await ctx.send(f"📥 Playlist loading progress: {processed}/{total} tracks")
                    await asyncio.sleep(0.5)

            music_bot.processing_playlists[guild_id] = False
            await ctx.send(f"✅ Finished processing playlist: Added {processed} tracks to queue")

        except Exception as e:
            print(f"Error processing playlist items: {str(e)}")
            await ctx.send(f"⚠️ Error while processing some playlist items: {str(e)}")
            music_bot.processing_playlists[guild_id] = False


async def play_next(ctx):
    guild_id = ctx.guild.id
    guild_queue = music_bot.get_queue(guild_id)

    if not guild_queue:
        await ctx.send("Queue finished.")
        return

    retry_count = 0
    max_retries = 3

    while retry_count < max_retries:
        try:
            next_track = guild_queue.pop(0)
            music_bot.current_track[guild_id] = next_track
            music_bot.start_time[guild_id] = datetime.now()

            new_source = await YTDLSource.create_source(next_track.data, next_track.requester)
            if not new_source:
                await ctx.send("⚠️ Failed to load track, skipping...")
                return await play_next(ctx)

            embed = discord.Embed(
                title="Now Playing",
                description=f"🎵 **{next_track.title}**",
                color=discord.Color.blue()
            )
            if next_track.duration:
                embed.add_field(name="Duration", value=str(timedelta(seconds=next_track.duration)))
            if next_track.thumbnail:
                embed.set_thumbnail(url=next_track.thumbnail)

            await ctx.send(embed=embed)

            def after_playing(error):
                if error:
                    print(f"Player error: {error}")
                    asyncio.run_coroutine_threadsafe(
                        handle_player_error(ctx, error),
                        bot.loop
                    )
                else:
                    asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)

            ctx.voice_client.play(new_source, after=after_playing)
            return

        except Exception as e:
            retry_count += 1
            print(f"Error in play_next (attempt {retry_count}/{max_retries}): {str(e)}")
            await asyncio.sleep(1)

    await ctx.send("❌ Failed to play track after multiple attempts. Skipping...")
    await play_next(ctx)


async def handle_player_error(ctx, error):
    try:
        if isinstance(error, discord.ClientException):
            await ctx.send("⚠️ A playback error occurred. Attempting to recover...")
            if ctx.voice_client and ctx.voice_client.is_connected():
                await ctx.voice_client.disconnect()
                await asyncio.sleep(1)
                await ctx.author.voice.channel.connect()

        await play_next(ctx)
    except Exception as e:
        await ctx.send(f"❌ Failed to recover from error: {str(e)}")


@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    print("Bot is ready!")
    await bot.change_presence(activity=discord.Game(name="!help for commands"))


@bot.event
async def on_disconnect():
    print("Bot disconnected. Attempting to reconnect...")


@bot.event
async def on_resumed():
    print("Bot successfully resumed connection.")
    for guild in bot.guilds:
        if guild.voice_client and not guild.voice_client.is_connected():
            try:
                await guild.voice_client.disconnect()
                if guild.me.voice and guild.me.voice.channel:
                    await guild.me.voice.channel.connect()
            except Exception as e:
                print(f"Error restoring voice connection in {guild.name}: {e}")


@bot.command(name="play", help="Play audio from YouTube URL")
async def play(ctx, *, query):
    if not query:
        await ctx.send("❌ Please provide a URL or search term!")
        return

    try:
        if not ctx.voice_client:
            if ctx.author.voice:
                try:
                    await ctx.author.voice.channel.connect()
                except discord.ClientException:
                    if ctx.guild.voice_client:
                        await ctx.guild.voice_client.disconnect()
                    await asyncio.sleep(1)
                    await ctx.author.voice.channel.connect()
            else:
                await ctx.send("❌ You need to be in a voice channel first!")
                return

        if not query.startswith(('http://', 'https://')):
            query = f"ytsearch:{query}"

        sources = await YTDLSource.from_url(ctx, query, requester=ctx.author)

        if not sources:
            return

        guild_queue = music_bot.get_queue(ctx.guild.id)
        guild_queue.extend(sources)

        if not ctx.voice_client.is_playing():
            await play_next(ctx)

    except Exception as e:
        print(f"Error during playback: {str(e)}")
        await ctx.send(f"❌ An error occurred: {str(e)}")
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            await asyncio.sleep(1)
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()


@bot.command(name="skip", help="Skip the current track")
async def skip(ctx):
    if not ctx.voice_client:
        return await ctx.send("❌ Not connected to a voice channel!")

    if not ctx.voice_client.is_playing():
        return await ctx.send("❌ Nothing is playing!")

    ctx.voice_client.stop()
    await ctx.send("⏭️ Skipped!")


@bot.command(name="stop", help="Stop and clear the queue")
async def stop(ctx):
    if not ctx.voice_client:
        return await ctx.send("❌ Not connected to a voice channel!")

    guild_id = ctx.guild.id
    music_bot.queues[guild_id] = []
    music_bot.current_track[guild_id] = None
    ctx.voice_client.stop()
    await ctx.voice_client.disconnect()
    await ctx.send("⏹️ Stopped and cleared queue!")


@bot.command(name="queue", help="Display the current queue")
async def queue(ctx):
    guild_id = ctx.guild.id
    queue = music_bot.get_queue(guild_id)

    if not queue and guild_id not in music_bot.current_track:
        return await ctx.send("📪 Queue is empty!")

    embed = discord.Embed(
        title="Music Queue",
        color=discord.Color.blue()
    )

    if guild_id in music_bot.current_track and music_bot.current_track[guild_id]:
        current = music_bot.current_track[guild_id]
        duration = str(timedelta(seconds=current.duration)) if current.duration else "Unknown"
        embed.add_field(
            name="🎵 Now Playing",
            value=f"**{current.title}**\nDuration: {duration}",
            inline=False
        )

    if queue:
        queue_text = ""
        for i, track in enumerate(queue[:10], 1):
            duration = str(timedelta(seconds=track.duration)) if track.duration else "Unknown"
            queue_text += f"`{i}.` **{track.title}** | {duration}\n"

        if len(queue) > 10:
            queue_text += f"\n*and {len(queue) - 10} more tracks...*"

        embed.add_field(name="📑 Up Next", value=queue_text or "No tracks in queue", inline=False)

    await ctx.send(embed=embed)


@bot.command(name="clear", help="Clear the queue")
async def clear(ctx):
    guild_id = ctx.guild.id
    if guild_id not in music_bot.queues or not music_bot.queues[guild_id]:
        return await ctx.send("❌ Queue is already empty!")

    queue_length = len(music_bot.queues[guild_id])
    music_bot.queues[guild_id] = []
    await ctx.send(f"🗑️ Cleared {queue_length} tracks!")


@bot.command(name="np", help="Show current track")
async def now_playing(ctx):
    guild_id = ctx.guild.id

    if not ctx.voice_client or not ctx.voice_client.is_playing():
        return await ctx.send("❌ Nothing is playing!")

    track = music_bot.current_track[guild_id]

    embed = discord.Embed(title="Now Playing", color=discord.Color.blue())
    embed.add_field(name="Title", value=track.title, inline=False)

    if track.duration:
        duration = str(timedelta(seconds=int(track.duration)))
        embed.add_field(name="Duration", value=duration)

    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)

    await ctx.send(embed=embed)


async def check_inactive():
    while True:
        try:
            for voice_client in bot.voice_clients:
                if voice_client and not voice_client.is_playing() and not voice_client.is_paused():
                    await voice_client.disconnect()
                    guild = voice_client.guild
                    if guild.id in music_bot.queues:
                        music_bot.queues[guild.id].clear()
                    if guild.id in music_bot.current_track:
                        music_bot.current_track[guild.id] = None
                    print(f"Disconnected from {guild.name} due to inactivity")
            await asyncio.sleep(300)  # Check every 5 minutes
        except Exception as e:
            print(f"Error in check_inactive: {e}")
            await asyncio.sleep(300)


@bot.command(name="remove", help="Remove a track from the queue")
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

    bot.loop.create_task(check_inactive())
    bot.run(token)
