"""Pirate bot for Discord, powered by Claude.

Needs two environment variables:
  DISCORD_TOKEN      - the bot token from the Discord Developer Portal
  ANTHROPIC_API_KEY  - an API key from console.anthropic.com
"""

import os
from collections import defaultdict, deque

import discord
from anthropic import AsyncAnthropic

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5")

SYSTEM_PROMPT = """You are Captain Barnacle, the pirate who runs this Discord server.
Talk like a friendly pirate ("Arr", "matey", "ye") but keep your answers clear and useful.
Keep replies short: a few sentences, never more than 150 words.
Stay good-natured and family-friendly. You are an AI character, and you say so if asked.
Several people may be in the conversation; each message starts with the speaker's name."""

claude = AsyncAnthropic()  # picks up ANTHROPIC_API_KEY automatically

intents = discord.Intents.default()
intents.message_content = True  # must also be switched on in the Developer Portal
intents.members = True          # needed for the welcome message on join
bot = discord.Client(intents=intents)

# Last 10 exchanges per channel, so the captain remembers the conversation.
history = defaultdict(lambda: deque(maxlen=10))


async def ask_claude(channel_id: int, speaker: str, text: str) -> str:
    messages = []
    for user_turn, bot_turn in history[channel_id]:
        messages.append({"role": "user", "content": user_turn})
        messages.append({"role": "assistant", "content": bot_turn})

    user_turn = f"{speaker}: {text}"
    messages.append({"role": "user", "content": user_turn})

    response = await claude.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=messages,
    )
    reply = "".join(b.text for b in response.content if b.type == "text").strip()
    reply = reply or "Arr, me parrot swallowed me words. Try again, matey."

    history[channel_id].append((user_turn, reply))
    return reply[:2000]  # Discord's message length limit


@bot.event
async def on_ready():
    print(f"Captain {bot.user} is aboard and listening.")


@bot.event
async def on_member_join(member: discord.Member):
    channel = member.guild.system_channel
    if channel is None:
        return
    try:
        greeting = await ask_claude(
            channel.id, member.display_name, "(has just joined the server. Welcome them aboard.)"
        )
        await channel.send(f"{member.mention} {greeting}")
    except Exception as e:
        print(f"Welcome failed: {e!r}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions
    if not (is_dm or is_mentioned):
        return

    text = (
        message.content.replace(f"<@{bot.user.id}>", "")
        .replace(f"<@!{bot.user.id}>", "")
        .strip()
    ) or "Ahoy!"

    async with message.channel.typing():
        try:
            reply = await ask_claude(message.channel.id, message.author.display_name, text)
        except Exception as e:
            print(f"Claude error: {e!r}")
            reply = "Arr, the seas be rough. Try again in a moment, matey."

    await message.reply(reply, mention_author=False)


bot.run(DISCORD_TOKEN)
