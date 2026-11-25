"""Bot-managed partner showcase; never deletes member messages."""
import asyncio
import logging
import discord
from services.discord_hq_blueprint import PITMARK_ORANGE

log = logging.getLogger("pitmark.discord.gateway")
_lock = asyncio.Lock()
BASE = "https://cdn.shopify.com/s/files/1/1067/3913/8641/files/discord-showcase-"
FOOTER = "Pitmark Racing Co. • Leave Your Mark."
ENTRIES = [
    ("Blake Murray | #133", "🏁 OFFICIALLY SPONSORED DRIVER", "Pitmark Racing Co. is proud to sponsor Blake Murray and the #133 in grassroots dirt racing.", "[Follow Blake on Facebook](https://www.facebook.com/share/19ZwJhqXix/)", "blake-133.png?v=1795583374"),
    ("Cross Cannon Motorsports", "🤝 OFFICIAL PARTNER • SIM RACING TEAM", "Veteran-owned iRacing team bringing Pitmark branding to virtual competition.", "[Read the Pitmark feature](https://pitmarkracing.com/blogs/racing-culture/cross-cannon-motorsports-pitmark-iracing-team-feature-2026)", "cross-cannon.png?v=1795583377"),
    ("Matthews Racing", "🏎️ RACING TEAM", "Meet Matthews Racing and follow their racing journey.", "[Visit website](https://matthewsracing.com/)", "matthews.png?v=1795583380"),
    ("B&G Motorsports", "🏎️ MOTORSPORTS TEAM", "Explore B&G Motorsports and their racing program.", "[Visit website](https://bgmotorsports.us/)", "bg-motorsports.png?v=1795583392"),
    ("Edmonton International Raceway", "🏟️ RACE TRACK", "Discover racing in Wetaskiwin and support local motorsports.", "[Visit website](https://www.edmontonraceway.com/)", "edmonton.png?v=1795583383"),
    ("Michael’s Mercer Raceway Park", "🏟️ RACE TRACK", "Celebrate grassroots racing at Mercer Raceway Park.", "[Visit website](https://michaelsmercerraceway.com/)", "mercer.png?v=1795583388"),
    ("TimmyNeutron Racing", "🎮 RACING & CONTENT", "Follow TimmyNeutron Racing and connect with its racing content.", "[Find social channels](https://beacons.ai/timmyneutrongaming)", "timmy-neutron.png?v=1795583396"),
    ("CagedEgo", "🎥 CREATOR & STREAMER", "Connect with CagedEgo through streaming and community content.", "[Twitch](https://www.twitch.tv/CagedEgoV2) • [Kick](https://kick.com/CagedEgo) • [TikTok](https://www.tiktok.com/@rdubdesignz)", "cagedego.png?v=1795583399"),
]

async def sync_showcase(guild, bot_user):
    async with _lock:
        matches = [c for c in guild.text_channels if c.name == "partner-showcase"]
        if len(matches) != 1 or bot_user is None:
            log.warning("Partner showcase skipped: expected exactly one target channel.")
            return
        channel = matches[0]
        messages = [m async for m in channel.history(limit=200) if m.author.id == bot_user.id and m.embeds]
        intro = discord.Embed(title="Pitmark • 🏁 PITMARK PARTNER SHOWCASE", description="Meet the drivers, teams, tracks and creators connected with Pitmark Racing Co. From virtual racing to real-world motorsports, we're building something together.\n\n[Explore our partnerships](https://pitmarkracing.com/pages/partnerships)", color=PITMARK_ORANGE)
        intro.set_footer(text=FOOTER)
        cards = [intro]
        for name, category, description, links, asset in ENTRIES:
            card = discord.Embed(title=name, description=f"**{category}**\n\n{description}\n\n{links}", color=PITMARK_ORANGE)
            card.set_thumbnail(url=BASE + asset)
            card.set_footer(text=FOOTER)
            cards.append(card)
        count = 0
        for idx, card in enumerate(cards):
            existing = next((m for m in messages if m.embeds[0].title == card.title and (idx == 0 or (m.embeds[0].footer.text or "") == FOOTER)), None)
            if existing:
                if existing.embeds[0].to_dict() != card.to_dict():
                    await existing.edit(embed=card, allowed_mentions=discord.AllowedMentions.none())
                message = existing
            else:
                message = await channel.send(embed=card, allowed_mentions=discord.AllowedMentions.none())
            if idx == 0 and not message.pinned:
                try:
                    await message.pin(reason="Pitmark partner directory")
                except discord.HTTPException:
                    log.warning("Partner showcase intro could not be pinned")
            count += 1
        log.info("Partner showcase synced: %s cards in channel %s", count, channel.id)
