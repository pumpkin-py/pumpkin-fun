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

    def _get_useful_data(self, json):
        """
        example json: https://wttr.in/praha?lang=sk&format=j1
        get useful data from json as list of individual days"""

        weather = []
        # get individual days to extract data
        num_of_forecast_days = 2 # number of days to get forecast for (including current day, max is 3)
        day_phases = { # dict for getting the data from json easier (when you don't wan't some phase of day comment it)
            "Morning": 2,
            "Day": 4,
            # "Evening": 6,
            "Night": 7
        }
        for i in range(num_of_forecast_days):
            cur_day = json['weather'][i]
            day_dict = {
                "date": cur_day['date'],
            }
            for k, v in day_phases.items():
                day_dict.update({k: {
                    "state": cur_day['hourly'][v]['weatherDesc'][0]['value'],
                    "temp": cur_day['hourly'][v]['tempC'],
                    "feels_like": cur_day['hourly'][v]['FeelsLikeC'],
                    "wind_speed": cur_day['hourly'][v]['windspeedKmph']
                }})

            weather.append(day_dict)
        return weather

    def _create_embeds(self, ctx, name):
        """create embeds for scrollable embed"""
        url = f"https://wttr.in/{name}?format=j1"
        request = requests.get(url)
        # check status code of request for failures (lazy way)
        if request.status_code != 200:
            # return error embed
            return utils.discord.create_embed(
                author=ctx.message.author,
                title='Error occured while getting weather info.',
                error=True,
            )

        # create day embeds
        days = self._get_useful_data(request.json())
        embeds = []
        for day in days:
            embed = utils.discord.create_embed(
                author=ctx.message.author,
                title=f"Weather forecast for {day['date']}",
            )
            for k, v in day.items():
                if type(v) == str:
                    continue
                infoStr = f"""
                    - Temperature: {v['temp']} ˚C
                    - Feels like: {v['feels_like']} ˚C
                    - Wind speed: {v['wind_speed']} km/s"""
                embed.add_field(name=k + f": {v['state']}", value=infoStr, inline=False)   

            embeds.append(embed)
            
        # get last "map" emebed
        embed = utils.discord.create_embed(
                author=ctx.message.author,
                title="Weather map for today",
            )
        img_url = f"https://v3.wttr.in/{name}.png"
        embed.set_image(url=img_url)
        embeds.append(embed)
        return embeds

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

        embeds = self._create_embeds(ctx, name)
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
