#!/usr/bin/env python
import discord
import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

COGS = [ 'dice_roller',
         'card_lookup',
         'list_lookup',
         'test_cog']

def main():
    debug = os.getenv('DEBUG', False)
    log_level = 'DEBUG' if debug else 'INFO'
    logging.basicConfig(
        format='%(asctime)s [%(process)d] Discord - %(levelname)s: %(message)s',
        level=log_level
    )

    discord_token = os.getenv("DISCORD_TOKEN", None)
    if discord_token is None:
        logging.error("No discord token found, exiting.")
        return

    logging.info(f"Discord token: {discord_token}")
    # This bot doesn't do voice, suppress warning about NaCl library
    discord.VoiceClient.warn_nacl = False
    # intents = discord.Intents.default()
    # intents.message_content = True
    bot = discord.Bot(intents=discord.Intents.all(), cache_app_emojis=True)
    for cog in COGS:
        bot.load_extension(f"r2d7.DiscordR3.cogs.{cog}")
    logging.info("Starting Discord client")
    bot.run(discord_token)


if __name__ == "__main__":
    main()
