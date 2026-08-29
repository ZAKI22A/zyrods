import discord
from utils import emojis
from datetime import datetime, timezone


def _now():
    return datetime.now(timezone.utc)


def build_admin_dm_embed(
    guild, member, title, emoji, description, color, fields=None
):
    """
    Professional DM embed sent to the affected user.
    - Author: server name + icon (top)
    - Thumbnail: small top-right (member avatar)
    - Image: rectangular banner at bottom
    - Footer: member + timestamp
    NOTE: NEVER reveals the staff member who issued the action.
    """
    embed = discord.Embed(
        title=f"{emoji}  {title}",
        description=description,
        color=color,
        timestamp=_now(),
    )
    if guild and guild.icon:
        embed.set_author(name=guild.name, icon_url=guild.icon.url)
    elif guild:
        embed.set_author(name=guild.name)

    if member and hasattr(member, "display_avatar"):
        try:
            embed.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass

    if guild and guild.banner:
        embed.set_image(url=guild.banner.url)

    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

    embed.set_footer(
        text=f"{guild.name if guild else 'Zyro'}  •  {_now().strftime('%Y-%m-%d %H:%M UTC')}",
        icon_url=member.display_avatar.url if member and hasattr(member, "display_avatar") else None,
    )
    return embed


async def send_admin_dm(member, title, description, color, fields=None, emoji=None):
    """
    Send a professional DM embed to the affected member without revealing the staff.
    Returns True if the DM was sent, False otherwise.
    """
    if not member:
        return False
    guild = getattr(member, "guild", None)
    embed = build_admin_dm_embed(
        guild=guild,
        member=member,
        title=title,
        emoji=emoji or str(emojis.NOTIFICATION if hasattr(emojis, "NOTIFICATION") else emojis.USER),
        description=description,
        color=color,
        fields=fields,
    )
    try:
        await member.send(embed=embed)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False
    except Exception:
        return False
