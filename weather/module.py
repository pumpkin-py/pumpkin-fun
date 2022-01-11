from typing import Optional
import requests

from nextcord.ext import commands

import pie.database.config
from pie import check, i18n, logger, utils

from .database import Place

_ = i18n.Translator("modules/fun").translate
guild_log = logger.Guild.logger()
config = pie.database.config.Config.get()


class Weather(commands.Cog):
    """Weather and forecast"""

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def _create_embeds(ctx, url):
        # create embeds
        request = requests.get(url)
        if request.status_code != 200:
            return utils.discord.create_embed(
                author=ctx.message.author,
                title="Error occured while getting weather info.",
                error=True,
            )
        data = request.json()
        em1 = utils.discord.create_embed(
            author=ctx.message.author,
            title="Current weather",
        )
        em1.add_field(name="Feels like:", value=data['current_condition'][0]['FeelsLikeC'], inline=True)
        em2 = utils.discord.create_embed(
            author=ctx.message.author,
            title="Current weather",
        )
        em2.add_field(name="Feels like:", value=data['current_condition'][0]['temp_C'], inline=True)
        return [em1, em2]

    @commands.guild_only()
    @commands.check(check.acl)
    @commands.command(name="set-weather-place")
    async def set_weather_place(self, ctx, *, name: str):
        """Set preferred place for weather and forecast information."""
        if not self._place_is_valid(name):
            await ctx.reply(_(ctx, "That's not valid place name."))
            return
        Place.set(ctx.guild.id, ctx.author.id, name)
        await guild_log.debug(
            ctx.author, ctx.channel, f"Preferred weather place set to {name}."
        )
        await ctx.reply(
            _(ctx, "Your preferred weather place set to **{place}**.").format(
                place=name
            )
        )

    @commands.guild_only()
    @commands.check(check.acl)
    @commands.command(name="unset-weather-place")
    async def unset_weather_place(self, ctx):
        """Unset preferred place for weather and forecast information."""
        if Place.remove(ctx.guild.id, ctx.author.id) == 0:
            await ctx.reply(_(ctx, "You don't have any place preference saved."))
            return
        await guild_log.debug(ctx.author, ctx.channel, "Preferred weather place unset.")
        await ctx.reply(_(ctx, "Your preferred weather place was removed."))

    @commands.guild_only()
    @commands.check(check.acl)
    @commands.command(name="set-guild-weather-place")
    async def set_guild_weather_place(self, ctx, *, name: str):
        """Set guild's preferred place for weather and forecast information."""
        if not self._place_is_valid(name):
            await ctx.reply(_(ctx, "That's not valid place name."))
            return
        Place.set(ctx.guild.id, None, name)
        await guild_log.info(
            ctx.author, ctx.channel, f"Guild's preferred weather place set to {name}."
        )
        await ctx.reply(
            _(ctx, "Guild's preferred weather place set to **{place}**.").format(
                place=name
            )
        )

    @commands.guild_only()
    @commands.check(check.acl)
    @commands.command(name="unset-guild-weather-place")
    async def unset_guild_weather_place(self, ctx):
        """Unset guild's preferred place for weather and forecast information."""
        if Place.remove(ctx.guild.id, None) == 0:
            await ctx.reply(
                _(ctx, "This server doesn't have any place preference saved.")
            )
            return
        await guild_log.debug(
            ctx.author, ctx.channel, "Guild's preferred weather place unset."
        )
        await ctx.reply(_(ctx, "Guild's preferred weather place was removed."))

    @commands.check(check.acl)
    @commands.group(name="weather")
    async def weather(self, ctx, name: Optional[str] = None):
        """Get weather information on any place."""
        if name is None:
            # try to get user preference
            place = Place.get(ctx.guild.id, ctx.author.id)
            if place is not None:
                name = place.name
        if name is None:
            # try to get guild preference
            place = Place.get(ctx.guild.id, None)
            if place is not None:
                name = place.name
        if name is None:
            await ctx.reply(_(ctx, "You have to specify a place or set a preference."))
            return

        url = f"https://wttr.in/{name}?format=j1"

        embeds = self._create_embeds(ctx, url)
        if not isinstance(embeds, list):
            await ctx.reply(embed=embeds)
            return
        scrollEmbed = utils.ScrollableEmbed(ctx, embeds)
        await scrollEmbed.scroll()

    def _place_is_valid(self, name: str) -> bool:
        if "&" in name:
            return False
        return True


def setup(bot) -> None:
    bot.add_cog(Weather(bot))
