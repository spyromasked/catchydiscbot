import discord
from discord.ext import commands, tasks
import asyncio
from collections import defaultdict
from database import Database

db = Database()

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_message_counts = defaultdict(list)  # Tracks messages for spam detection
        self.vc_start_times = defaultdict(lambda: None)  # Tracks VC time
        self.send_leaderboard.start()  # Start the automatic leaderboard task

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return  # Ignore bot messages

        user_id = message.author.id
        db.update_messages(user_id)  # Update message count in database

        # Spam detection (5 messages in 10 seconds)
        self.user_message_counts[user_id].append(message.created_at.timestamp())
        self.user_message_counts[user_id] = [t for t in self.user_message_counts[user_id] if t > message.created_at.timestamp() - 10]

        if len(self.user_message_counts[user_id]) >= 5:
            embed = discord.Embed(
                title="<:currencypaw:1346100210899619901> Spam Warning!",
                description=f"{message.author.mention}, you are sending messages too fast!",
                color=discord.Color.red()
            )
            warning = await message.channel.send(content=message.author.mention, embed=embed)  # Mention user
            await asyncio.sleep(5)
            await warning.delete()  # Auto-delete warning after 5 sec

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        user_id = member.id

        # User joins VC
        if before.channel is None and after.channel is not None:
            self.vc_start_times[user_id] = asyncio.get_event_loop().time()

        # User leaves VC
        elif before.channel is not None and after.channel is None and self.vc_start_times[user_id] is not None:
            elapsed_time = int(asyncio.get_event_loop().time() - self.vc_start_times.pop(user_id))
            db.update_vc_time(user_id, elapsed_time)  # Update VC time in database

    @commands.command(name="stats")
    async def stats(self, ctx, member: discord.Member = None):
        """Show message and VC stats of a user."""
        member = member or ctx.author
        messages_sent, vc_time = db.get_user_stats(member.id)

        embed = discord.Embed(title=f"<:currencypaw:1346100210899619901> Stats for {member.display_name}", color=discord.Color.blue())
        embed.add_field(name="<:currencypaw:1346100210899619901> Total Messages Sent", value=f"{messages_sent:,}", inline=False)
        embed.add_field(name="<:currencypaw:1346100210899619901> Total VC Time", value=f"{vc_time // 3600}h {vc_time % 3600 // 60}m {vc_time % 60}s", inline=False)
        embed.set_thumbnail(url=member.avatar.url)

        await ctx.send(embed=embed)

    @commands.command(name="topchat")
    async def top_chat(self, ctx):
        """Show top users by message count."""
        top_users = db.get_top_chatters(50)

        pages = []
        if not top_users:
            pages.append(discord.Embed(title="<:currencypaw:1346100210899619901> Top Chat Users", description="No data available yet.", color=discord.Color.gold()))
        else:
            for i in range(0, len(top_users), 5):  # Paginate 5 users per page
                embed = discord.Embed(title="<:currencypaw:1346100210899619901> Top Chat Users", color=discord.Color.gold())
                for rank, (user_id, messages) in enumerate(top_users[i:i+5], start=i+1):
                    user = self.bot.get_user(user_id) or f"User {user_id}"
                    embed.add_field(name=f"<:currencypaw:1346100210899619901> #{rank} {user}", value=f"- {messages:,} messages", inline=False)
                pages.append(embed)

        await self.paginate(ctx, pages)

    @commands.command(name="topvc")
    async def top_vc(self, ctx):
        """Show top users by VC time."""
        top_users = db.get_top_vc(50)

        pages = []
        if not top_users:
            pages.append(discord.Embed(title="<:currencypaw:1346100210899619901> Top VC Users", description="No data available yet.", color=discord.Color.purple()))
        else:
            for i in range(0, len(top_users), 5):  # Paginate 5 users per page
                embed = discord.Embed(title="<:currencypaw:1346100210899619901> Top VC Users", color=discord.Color.purple())
                for rank, (user_id, vc_time) in enumerate(top_users[i:i+5], start=i+1):
                    user = self.bot.get_user(user_id) or f"User {user_id}"
                    embed.add_field(name=f"- #{rank} {user}", value=f"<:currencypaw:1346100210899619901> {vc_time // 3600}h {vc_time % 3600 // 60}m {vc_time % 60}s", inline=False)
                pages.append(embed)

        await self.paginate(ctx, pages)

    async def paginate(self, ctx, pages):
        """Handles pagination for embeds."""
        if not pages:
            return

        current_page = 0
        message = await ctx.send(embed=pages[current_page])

        if len(pages) == 1:
            return  # No need for pagination

        await message.add_reaction("◀")
        await message.add_reaction("▶")

        def check(reaction, user):
            return user == ctx.author and reaction.message.id == message.id and reaction.emoji in ["◀", "▶"]

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=60, check=check)
                await message.remove_reaction(reaction.emoji, user)

                if reaction.emoji == "▶" and current_page < len(pages) - 1:
                    current_page += 1
                    await message.edit(embed=pages[current_page])
                elif reaction.emoji == "◀" and current_page > 0:
                    current_page -= 1
                    await message.edit(embed=pages[current_page])
            except asyncio.TimeoutError:
                await message.clear_reactions()
                break

    @tasks.loop(minutes=5)
    async def send_leaderboard(self):
        channel = self.bot.get_channel(1349397400212603033)  # Your channel ID here
        if channel:
            top_users = db.get_top_chatters(50)
            embed_message = discord.Embed(title="Leaderboard", color=discord.Color.green())

            for rank, (user_id, messages) in enumerate(top_users, start=1):
                user = self.bot.get_user(user_id) or f"User {user_id}"
                embed_message.add_field(name=f"#{rank} {user}", value=f"- {messages:,} messages", inline=False)

            await channel.send(embed=embed_message)

    @send_leaderboard.before_loop
    async def before_send_leaderboard(self):
        await self.bot.wait_until_ready()  # Ensure the bot is ready before starting the task

async def setup(bot):
    await bot.add_cog(Leaderboard(bot))
