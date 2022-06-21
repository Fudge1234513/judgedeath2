from dotenv import load_dotenv
import os
import sys

from discord.ext import commands

from cog_overseer import Overseer
from cog_tracker import Tracker


if __name__ == "__main__":
    load_dotenv()
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    STEAM_TOKEN = os.getenv("STEAM_TOKEN")

    bot = commands.Bot(command_prefix=("~", "?"), help_command=None)

    bot.add_cog(Overseer(bot))
    bot.add_cog(Tracker(bot, STEAM_TOKEN))
    with open("data/console.log", "a") as sys.stderr:
        bot.run(DISCORD_TOKEN)
