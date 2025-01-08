# Discord Music Bot

A simple Discord bot to play music from YouTube, manage a queue, and control playback in voice channels.

## Features

- Play audio from YouTube URLs.
- Queue management (add, view, skip, clear).
- Control playback (pause, resume, stop).
- Join and leave voice channels automatically.

## Prerequisites

Before running the bot, make sure you have the following:

1. Python 3.8 or later.
2. The required Python packages:
   - `discord.py`
   - `yt-dlp`
   - `python-dotenv`
   - `PyNaCl`
   - `ffmpeg` (installed on your system and added to PATH).

## Setup

1. Clone the repository or copy the script.
2. Install the required dependencies:
   ```bash
   pip install discord.py yt-dlp python-dotenv pynacl
3. Install `ffmpeg`:
   - On Windows: Download from [FFmpeg](https://www.ffmpeg.org/) and add to PATH.
   - On macOS: Use Homebrew: `brew install ffmpeg`.
   - On Linux: Install via your package manager: `sudo apt install ffmpeg`.
4. Create a `.env` file in the project directory with your Discord bot token:
   ```bash
   DISCORD_TOKEN=your_bot_token_here
   ```
5. Run the bot:
   ```bash
   python music_bot.py
   ```
## Commands
### General Commands
<table>
  <thead>
    <tr>
      <th>Command</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>!help</code></td>
      <td>Show all available commands.</td>
    </tr>
    <tr>
      <td><code>!join</code></td>
      <td>Bot joins your voice channel.</td>
    </tr>
    <tr>
      <td><code>!leave</code></td>
      <td>Bot leaves the voice channel.</td>
    </tr>
  </tbody>
</table>

### Music Playback Commands
<table>
  <thead>
    <tr>
      <th>Command</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td><code>!play &lt;url&gt;</code></td>
      <td>Play or queue audio from a YouTube URL.</td>
    </tr>
    <tr>
      <td><code>!queue</code></td>
      <td>Display the current queue.</td>
    </tr>
    <tr>
      <td><code>!skip</code></td>
      <td>Skip the currently playing song.</td>
    </tr>
    <tr>
      <td><code>!clear</code></td>
      <td>Clear the queue.</td>
    </tr>
    <tr>
      <td><code>!pause</code></td>
      <td>Pause the current song.</td>
    </tr>
    <tr>
      <td><code>!resume</code></td>
      <td>Resume the paused song.</td>
    </tr>
    <tr>
      <td><code>!stop</code></td>
      <td>Stop playback and clear the queue.</td>
    </tr>
  </tbody>
</table>

## Example Usage
1. Join a voice channel.
2. Use `!play <YouTube URL>` to start playing music.
3. Use `!queue` to view the current queue.
4. Manage playback with commands like `!skip` or `!pause`.

## Troubleshooting
- Error: "Could not extract video data"
  - Ensure the YouTube URL is valid, and `yt-dlp` is installed and up-to-date.

- Bot does not join voice channel:
  - Verify you are in a voice channel and the bot has permission to join.

- Bot does not respond:
  - Ensure the bot is running, and the token in `.env` is correct.

## Acknowledgments
- `discord.py`: For Discord API integration.
- `yt-dlp`: For YouTube video and audio extraction.
- `FFmpeg`: For audio processing.
- `PyNaCl`: For voice support in discord.py.


