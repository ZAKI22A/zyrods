from utils import emojis

import discord
from discord.ext import commands
from discord import ui
from utils.Tools import *
from utils.cv2_compat import embed_to_view, embeds_to_view, sync_panel_message

class KickView(ui.View):
    def __init__(self, member):
        super().__init__(timeout=120)
        self.member = member
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await sync_panel_message(self)

    @ui.button(style=discord.ButtonStyle.gray, emoji=f"{emojis.DELETE}")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

class Kick(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    @commands.hybrid_command(
        name="kick",
        help="Kicks a member from the server.",
        usage="kick <member> [reason]",
        aliases=["kickmember"])
    @blacklist_check()
    @ignore_check()
    @top_check()
    @commands.has_permissions(kick_members=True)
    @bot_has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick_command(self, ctx, member: discord.Member, *, reason: str = None):
        reason = reason or "No reason provided"

        if member == ctx.author:
            return await ctx.reply("You cannot kick yourself.")

        if member == ctx.bot.user:
            return await ctx.reply("You cannot kick me.")

        if not ctx.author == ctx.guild.owner:
            if member == ctx.guild.owner:
                return await ctx.reply("I cannot kick the server owner.")

            if ctx.author.top_role <= member.top_role:
                return await ctx.reply("You cannot kick a member with a higher or equal role.")

        if ctx.guild.me.top_role <= member.top_role:
            return await ctx.reply("I cannot kick a member with a higher or equal role.")

        if member not in ctx.guild.members:
            embed = discord.Embed(
                description=f"**Member Not Found:** The specified member does not exist in this server.",
                color=self.color
            )
            view = KickView(member)
            message = await ctx.send(view = embed_to_view(embed, view = view))
            view.message = message
            return

        
        dm_status = "Yes"
        try:
            from utils.admin_dm import send_admin_dm
            from utils import emojis as _emo
            _dm_ok = await send_admin_dm(
                member,
                title="Server Kick",
                emoji=str(_emo.EMOJI_7CLUB_BAN),
                description=f"You have been **kicked** from **{ctx.guild.name}**.",
                color=0xED4245,
                fields=[
                    ("Server", ctx.guild.name, True),
                    ("Reason", f"`{reason}`", False),
                ],
            )
            if not _dm_ok:
                dm_status = "No"
        except discord.Forbidden:
            dm_status = "No"
        except discord.HTTPException:
            dm_status = "No"

        
        await member.kick(reason=f"Kicked by {ctx.author} | Reason: {reason}")

        from cogs.commands.logging import build_pro_embed
        _banner = ctx.guild.banner.url if ctx.guild.banner else None
        embed = build_pro_embed(
            guild=ctx.guild, user=member,
            title="Successfully Kicked", emoji=str(emojis.EMOJI_7CLUB_BAN),
            description=f"{member.mention} was kicked from **{ctx.guild.name}**.",
            color=0xED4245,
            fields=[
                ("Target", f"{member.mention} `({member.id})`", True),
                ("Reason", f"`{reason}`", False),
                ("DM Sent", f"`{dm_status}`", True),
            ],
            banner_url=_banner,
            thumbnail_url=member.display_avatar.url if member.display_avatar else None,
        )

        view = KickView(member)
        message = await ctx.send(view = embed_to_view(embed, view = view))
        view.message = message


"""
@Author: Sonu Jana
    + Discord: me.sonu
    + Community: https://discord.gg/stVsvE9rhT (Zyro)
    + for any queries reach out Community or DM me.
"""