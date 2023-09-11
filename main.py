import discord
from discord.ext import commands
import aiosqlite
import os

# Define the conversion rate
CONVERSION_RATE = 1  # 1 INR = 1 M-Buck

# Initialize the Discord bot
intents = discord.Intents.default()
intents.typing = False
intents.presences = False

bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize the SQLite database
async def setup_db():
    db = await aiosqlite.connect('bot_database.db')
    cursor = await db.cursor()
    await cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, discord_id INTEGER UNIQUE, phone_number TEXT, balance REAL)')
    await cursor.execute('CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY, user_id INTEGER, channel_id INTEGER, status TEXT)')
    await db.commit()
    await db.close()

# Ensure the database is set up when the bot is ready
@bot.event
async def on_ready():
    await setup_db()
    print(f'Logged in as {bot.user.name}')

# Register command to create a user account
@bot.command()
async def register(ctx, phone_number: str):
    user_id = ctx.author.id
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute('INSERT OR IGNORE INTO users (discord_id, phone_number, balance) VALUES (?, ?, ?)', (user_id, phone_number, 0))
        await db.commit()
        if cursor.rowcount == 0:
            await ctx.send('You are already registered.')
        else:
            await ctx.send('Registration complete. You now have an account.')

# Check balance command (only in personal chat)
@bot.command()
async def balance(ctx):
    user_id = ctx.author.id
    if isinstance(ctx.channel, discord.DMChannel):
        async with aiosqlite.connect('bot_database.db') as db:
            cursor = await db.execute('SELECT balance FROM users WHERE discord_id = ?', (user_id,))
            row = await cursor.fetchone()
            if row is not None:
                await ctx.send(f'Your balance is {row[0]} M-Bucks.')
            else:
                await ctx.send('You are not registered. Use `!register` to create an account.')
    else:
        await ctx.send("You can only check your balance in a personal chat (DM).")

# Cash-in command with conversion rate
@bot.command()
async def cashin(ctx, amount_inr: int):
    user_id = ctx.author.id

    # Check if the user is registered
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute('SELECT balance FROM users WHERE discord_id = ?', (user_id,))
        row = await cursor.fetchone()
        if row is None:
            await ctx.send('You are not registered. Use `!register` to create an account.')
            return

        balance = row[0]
        if amount_inr <= 0:
            await ctx.send("Invalid amount.")
            return

        # Calculate the amount in M-Bucks based on the conversion rate
        amount_mbucks = amount_inr * CONVERSION_RATE

        # Update the user's balance
        new_balance = balance + amount_mbucks
        await db.execute('UPDATE users SET balance = ? WHERE discord_id = ?', (new_balance, user_id))
        await db.commit()

        # Notify the user about the cash-in
        cashin_channel = bot.get_channel(YOUR_CASHIN_CHANNEL_ID)  # Replace with your channel ID
        await cashin_channel.send(f'@{ctx.author.name}, {amount_inr} INR cashed in, resulting in {amount_mbucks} M-Bucks added to your balance.')

# Cashout command with conversion rate
@bot.command()
async def cashout(ctx, amount_inr: int):
    user_id = ctx.author.id

    # Check if the user is registered
    async with aiosqlite.connect('bot_database.db') as db:
        cursor = await db.execute('SELECT balance FROM users WHERE discord_id = ?', (user_id,))
        row = await cursor.fetchone()
        if row is None:
            await ctx.send('You are not registered. Use `!register` to create an account.')
            return

        balance = row[0]
        if amount_inr <= 0:
            await ctx.send("Invalid amount.")
            return

        # Calculate the amount in M-Bucks based on the conversion rate
        amount_mbucks = amount_inr * CONVERSION_RATE

        if amount_mbucks > balance:
            await ctx.send("Insufficient balance.")
            return

        # Deduct the amount in M-Bucks from the user's balance
        new_balance = balance - amount_mbucks
        await db.execute('UPDATE users SET balance = ? WHERE discord_id = ?', (new_balance, user_id))
        await db.commit()

        # Notify the user about the cash-out
        cashout_channel = bot.get_channel(YOUR_CASHOUT_CHANNEL_ID)  # Replace with your channel ID
        await cashout_channel.send(f'@{ctx.author.name}, {amount_inr} INR cashed out, resulting in {amount_mbucks} M-Bucks deducted from your balance.')

# Transfer M-Bucks to another user
@bot.command()
async def transfer(ctx, recipient: discord.User, amount: int):
    sender_id = ctx.author.id
    recipient_id = recipient.id

    # Check if the sender and recipient are registered
    async with aiosqlite.connect('bot_database.db') as db:
        sender_cursor = await db.execute('SELECT balance FROM users WHERE discord_id = ?', (sender_id,))
        sender_row = await sender_cursor.fetchone()
        recipient_cursor = await db.execute('SELECT balance FROM users WHERE discord_id = ?', (recipient_id,))
        recipient_row = await recipient_cursor.fetchone()

        if sender_row is None:
            await ctx.send('You are not registered. Use `!register` to create an account.')
            return
        if recipient_row is None:
            await ctx.send(f'{recipient.display_name} is not registered.')
            return

        sender_balance = sender_row[0]
        recipient_balance = recipient_row[0]

        if amount <= 0 or sender_balance < amount:
            await ctx.send("Invalid amount or insufficient balance.")
            return

        # Deduct the amount from the sender's balance
        new_sender_balance = sender_balance - amount
        await db.execute('UPDATE users SET balance = ? WHERE discord_id = ?', (new_sender_balance, sender_id))

        # Add the amount to the recipient's balance
        new_recipient_balance = recipient_balance + amount
        await db.execute('UPDATE users SET balance = ? WHERE discord_id = ?', (new_recipient_balance, recipient_id))

        await db.commit()

        # Notify the sender and recipient about the transfer
        await ctx.send(f'You have transferred {amount} M-Bucks to {recipient.display_name}. Your new balance is {new_sender_balance} M-Bucks.')
        await recipient.send(f'You have received {amount} M-Bucks from {ctx.author.display_name}. Your new balance is {new_recipient_balance} M-Bucks.')

# Run the bot (replace 'YOUR_BOT_TOKEN' with your actual bot token)
bot.run('YOUR_BOT_TOKEN')
