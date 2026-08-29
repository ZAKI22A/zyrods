import discord
from discord.ext import commands
import asyncio
from utils.Tools import *
from utils import emojis
from utils.cv2_compat import embed_to_view
from utils.database import get_anti_db
from cogs.commands.logging import LOG_DEFINITIONS, CATEGORY_NAME, build_pro_embed
from utils.database import open_connection

DB_FILE = "logging.db"

class SetupView(discord.ui.View):
    def __init__(self, cog, ctx, role):
        super().__init__(timeout=120)
        self.cog = cog
        self.ctx = ctx
        self.role = role
        self.done_logging = False
        self.done_antinuke = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(f"{emojis.CROSSICON} Only {self.ctx.author.mention} can use this.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Enable All", style=discord.ButtonStyle.success, emoji="⚡")
    async def enable_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.run_full_setup(interaction, self.role, self.ctx)
        self.disable_all_items()
        try:
            await interaction.edit_original_response(view=self)
        except Exception:
            pass
        self.stop()

    @discord.ui.button(label="Logging Only", style=discord.ButtonStyle.primary, emoji=str(emojis.LOGGING))
    async def logging_only(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.setup_logging_only(interaction, self.ctx)
        self.done_logging = True
        if self.done_logging and self.done_antinuke:
            self.disable_all_items()
        else:
            button.disabled = True
            button.label = "Logging ✓"
        try:
            await interaction.edit_original_response(view=self)
        except Exception:
            pass

    @discord.ui.button(label="AntiNuke Only", style=discord.ButtonStyle.danger, emoji=str(emojis.SECURITY))
    async def antinuke_only(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.setup_antinuke_only(interaction, self.role, self.ctx)
        self.done_antinuke = True
        button.disabled = True
        button.label = "AntiNuke ✓"
        try:
            await interaction.edit_original_response(view=self)
        except Exception:
            pass

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray, emoji=f"{emojis.DELETE}")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.disable_all_items()
        await interaction.response.edit_message(content="Cancelled.", view=self)
        self.stop()


class SetupAll(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = 0x000000

    def get_avatar(self, user):
        return user.display_avatar.url if user.display_avatar else user.default_avatar.url

    async def setup_logging_only(self, interaction, ctx):
        guild = ctx.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, read_message_history=True, manage_channels=True)
        }
        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
        if not category:
            category = await guild.create_category(CATEGORY_NAME, overwrites=overwrites, reason="Auto Setup - Logging")

        db = await open_connection(DB_FILE)
        for channel_name, (db_key, emoji, title, desc, color) in LOG_DEFINITIONS.items():
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if not channel or channel.category != category:
                if channel:
                    try:
                        await channel.edit(category=category, sync_permissions=True)
                    except Exception:
                        channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
                else:
                    channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
                await asyncio.sleep(0.2)
            await db.execute("REPLACE INTO log_channels (guild_id, log_type, channel_id) VALUES (?, ?, ?)", (guild.id, db_key, channel.id))
            # intro embed
            banner = guild.banner.url if guild.banner else None
            intro = build_pro_embed(guild, ctx.author, title, emoji, f"> **{desc}**\n> Auto configured via `+setup`", color, [("📡 Status", f"{emojis.TICK} Active", True), ("🔧 Channel", channel.mention, True)], banner, guild.icon.url if guild.icon else ctx.author.display_avatar.url)
            try:
                await channel.send(view=embed_to_view(intro))
            except Exception:
                pass
        await db.commit()
        await db.close()

        embed = discord.Embed(description=f"{emojis.TICK} Logging setup completed: `{len(LOG_DEFINITIONS)}` channels under {category.mention}", color=0x57F287)
        embed.set_author(name="Logging Enabled", icon_url=self.get_avatar(ctx.author))
        try:
            await interaction.followup.send(view=embed_to_view(embed), ephemeral=True)
        except Exception:
            await ctx.send(view=embed_to_view(embed))

    async def setup_antinuke_only(self, interaction, role, ctx):
        guild = ctx.guild
        db = await get_anti_db()

        # Enable antinuke
        async with db.execute("SELECT status FROM antinuke WHERE guild_id = ?", (guild.id,)) as cur:
            row = await cur.fetchone()
        if not row or not row[0]:
            await db.execute("INSERT OR REPLACE INTO antinuke (guild_id, status) VALUES (?, ?)", (guild.id, True))
            # enable limits if table exists
            try:
                from cogs.commands.antinuke import DEFAULT_LIMITS, TIME_WINDOW
                for action, limit in DEFAULT_LIMITS.items():
                    await db.execute("INSERT OR REPLACE INTO limit_settings (guild_id, action_type, action_limit, time_window) VALUES (?, ?, ?, ?)", (guild.id, action, limit, TIME_WINDOW))
            except Exception:
                pass
            await db.commit()
        else:
            await interaction.followup.send(f"{emojis.ICONS_WARNING} Antinuke already enabled.", ephemeral=True)
            # still whitelist role
            pass

        # Whitelist all members with the given role + fix permissions
        count = 0
        for member in role.members:
            async with db.execute("SELECT user_id FROM whitelisted_users WHERE guild_id = ? AND user_id = ?", (guild.id, member.id)) as cur:
                exists = await cur.fetchone()
            if not exists:
                await db.execute("INSERT INTO whitelisted_users (guild_id, user_id) VALUES (?, ?)", (guild.id, member.id))
            await db.execute("UPDATE whitelisted_users SET ban=?, kick=?, prune=?, botadd=?, serverup=?, memup=?, chcr=?, chdl=?, chup=?, rlcr=?, rldl=?, rlup=?, meneve=?, mngweb=?, mngstemo=? WHERE guild_id=? AND user_id=?",
                             (True, True, True, True, True, True, True, True, True, True, True, True, True, True, True, guild.id, member.id))
            count += 1
        await db.commit()

        embed = discord.Embed(description=f"{emojis.TICK} Antinuke enabled and whitelisted role {role.mention} (`{count}` members). All protections active.", color=0x57F287)
        embed.set_author(name="AntiNuke Enabled", icon_url=self.get_avatar(ctx.author))
        embed.add_field(name="Protected Modules", value=f"{emojis.ENABLED_160063} Anti Ban/Kick/Bot/Channel/Role/Guild/Webhook/Everyone", inline=False)
        try:
            await interaction.followup.send(view=embed_to_view(embed), ephemeral=True)
        except Exception:
            await ctx.send(view=embed_to_view(embed))

    async def run_full_setup(self, interaction, role, ctx):
        await self.setup_logging_only(interaction, ctx)
        await asyncio.sleep(0.5)
        await self.setup_antinuke_only(interaction, role, ctx)
        # Final summary
        guild = ctx.guild
        banner = guild.banner.url if guild.banner else None
        embed = build_pro_embed(
            guild=guild, user=ctx.author,
            title="Full Setup Completed", emoji="⚡",
            description=f"> All systems configured automatically for **{guild.name}**",
            color=0x000000,
            fields=[
                ("📁 Logging", f"{emojis.TICK} `{len(LOG_DEFINITIONS)}` channels in `SYSTEM-LOGS`", True),
                ("🛡️ AntiNuke", f"{emojis.TICK} Enabled + {role.mention} whitelisted", True),
                ("👤 Moderator", ctx.author.mention, True),
            ],
            banner_url=banner,
            thumbnail_url=guild.icon.url if guild.icon else ctx.author.display_avatar.url
        )
        try:
            await interaction.followup.send(view=embed_to_view(embed))
        except Exception:
            await ctx.send(view=embed_to_view(embed))

    @commands.command(name="autosetup", aliases=["setupall", "allsetup", "fullsetup"], help="One-click full server setup: logging + antinuke")
    @blacklist_check()
    @ignore_check()
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(administrator=True)
    @commands.cooldown(1, 30, commands.BucketType.guild)
    @commands.guild_only()
    async def setup(self, ctx, role: discord.Role = None):
        if role is None:
            embed = discord.Embed(
                title=f"{emojis.ICONS_WARNING} Missing Role",
                description=f"Please mention a role to whitelist for AntiNuke.\n\n**Usage:** `{ctx.prefix}setup @AdminRole`\n**Example:** `{ctx.prefix}setup @Staff`\n\nThis role's members will be whitelisted from antinuke punishments.",
                color=0x000000
            )
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_avatar(ctx.author))
            return await ctx.send(view=embed_to_view(embed))

        if role >= ctx.guild.me.top_role:
            embed = discord.Embed(description=f"{emojis.CROSSICON} Role {role.mention} is higher than my top role. Move my role above it.", color=0x000000)
            return await ctx.send(view=embed_to_view(embed))

        banner = ctx.guild.banner.url if ctx.guild.banner else None
        embed = build_pro_embed(
            guild=ctx.guild, user=ctx.author,
            title="Zyro Auto Setup", emoji=str(emojis.GEAR),
            description=f"> **One-click setup for your server**\n\nThis will automatically:\n"
                        f"{emojis.TICK} Create `{len(LOG_DEFINITIONS)}` logging channels in `SYSTEM-LOGS` (auto mode)\n"
                        f"{emojis.TICK} Enable **AntiNuke** with full protection\n"
                        f"{emojis.TICK} Whitelist {role.mention} (`{len(role.members)}` members)\n\n"
                        f"-# Click a button below to proceed. Use **Enable All** for full setup.",
            color=0x000000,
            fields=[
                ("🎯 Target Role", role.mention, True),
                ("👥 Members", f"`{len(role.members)}`", True),
                ("⚙️ Mode", "`Auto`", True),
            ],
            banner_url=banner,
            thumbnail_url=ctx.guild.icon.url if ctx.guild.icon else ctx.author.display_avatar.url
        )
        view = SetupView(self, ctx, role)
        await ctx.send(view=embed_to_view(embed, view=view))
