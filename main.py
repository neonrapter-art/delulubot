import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import datetime
import discord
from discord.ext import commands
from discord import app_commands
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- BOT SETUP ---
class ModerationBot(commands.Bot):
    def __init__(self):
        # We require all intents (Make sure to enable them in the Discord Developer Portal!)
        super().__init__(command_prefix="!", intents=discord.Intents.all())
        
    async def setup_hook(self):
        # Keeps the verification button working even if the bot restarts
        self.add_view(VerifyView())
        await self.tree.sync()

bot = ModerationBot()

# Temporary in-memory storage for 6-digit codes
verification_codes = {}

# --- EMAIL SYSTEM ---
def send_verification_email(to_email, code):
    # This securely pulls the email and password from Render's dashboard
    sender_email = os.getenv("neonrapter@gmail.com")
    sender_password = os.getenv("ljod dlfg sjam mof")
    
    # Fallback for testing if email isn't set up yet
    if not sender_email or not sender_password:
        print(f"TEST MODE: Verification code for {to_email} is {code}")
        return True
        
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_email
        msg['Subject'] = "Discord Server Verification Code"
        
        body = f"Your Discord server verification code is: {code}\n\nPlease enter this in the Discord popup to gain access."
        msg.attach(MIMEText(body, 'plain'))
        
        # Connects to Gmail (Change smtp.gmail.com if using Yahoo/Outlook)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

# --- UI FORMS (MODALS) ---
class CodeModal(discord.ui.Modal, title="Enter Verification Code"):
    code = discord.ui.TextInput(label="6-Digit Code from your Email", max_length=6, min_length=6)

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        if user_id in verification_codes and verification_codes[user_id] == self.code.value:
            # Securely fetches the role ID from Render
            role_id = int(os.getenv("936148506937282560", 0))
            role = interaction.guild.get_role(role_id)
            
            if role:
                await interaction.user.add_roles(role)
                del verification_codes[user_id]
                await interaction.response.send_message("✅ You are verified! You now have access to the server.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Admin Error: The Verified role ID is missing or incorrect.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Invalid code. Please click 'Verify Email' to try again.", ephemeral=True)

class EmailModal(discord.ui.Modal, title="Email Verification"):
    email = discord.ui.TextInput(label="Your Email Address", placeholder="user@example.com")

    async def on_submit(self, interaction: discord.Interaction):
        code = str(random.randint(100000, 999999))
        verification_codes[interaction.user.id] = code
        
        success = send_verification_email(self.email.value, code)
        if success:
            await interaction.response.send_message("✅ A code was sent to your email. Click below to enter it.", view=CodeView(), ephemeral=True)
        else:
            await interaction.response.send_message("❌ Failed to send email. Admins might not have configured it yet.", ephemeral=True)

# --- BUTTONS ---
class CodeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Enter Code", style=discord.ButtonStyle.green, custom_id="enter_code_btn")
    async def enter_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CodeModal())

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Verify Email", style=discord.ButtonStyle.primary, custom_id="verify_email_btn")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmailModal())

# --- ADMIN SLASH COMMANDS ---
@bot.tree.command(name="setup_verification", description="Admin: Spawn the verification panel here")
@app_commands.default_permissions(administrator=True) # Locks command to Admins
async def setup_verification(interaction: discord.Interaction):
    embed = discord.Embed(title="Server Verification", description="Click the button below to verify your email and unlock the server.", color=discord.Color.blue())
    await interaction.channel.send(embed=embed, view=VerifyView())
    await interaction.response.send_message("Verification panel spawned.", ephemeral=True)

@bot.tree.command(name="ban", description="Admin: Ban a user")
@app_commands.default_permissions(administrator=True)
async def ban_user(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 {member.mention} was banned. Reason: {reason}")

@bot.tree.command(name="kick", description="Admin: Kick a user")
@app_commands.default_permissions(administrator=True)
async def kick_user(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 {member.mention} was kicked. Reason: {reason}")

@bot.tree.command(name="blindness", description="Admin: Mutes and text-mutes a user")
@app_commands.default_permissions(administrator=True)
@app_commands.choices(duration=[
    app_commands.Choice(name="5 Minutes", value=5),
    app_commands.Choice(name="1 Hour", value=60),
    app_commands.Choice(name="1 Day", value=1440),
])
async def blindness(interaction: discord.Interaction, member: discord.Member, duration: app_commands.Choice[int], reason: str = "No reason provided"):
    try:
        # Timeout disables chatting in text channels and speaking in VC natively
        await member.timeout(datetime.timedelta(minutes=duration.value), reason=reason)
        await interaction.response.send_message(f"🔇 {member.mention} has been given **blindness** for {duration.name}. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("❌ I cannot restrict this user (they might be an admin).", ephemeral=True)

class AnnouncementModal(discord.ui.Modal, title="Create Announcement"):
    ann_title = discord.ui.TextInput(label="Title", max_length=100)
    ann_content = discord.ui.TextInput(label="Message", style=discord.TextStyle.paragraph, max_length=2000)

    def __init__(self, target_channel: discord.TextChannel):
        super().__init__()
        self.target_channel = target_channel

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title=self.ann_title.value, description=self.ann_content.value, color=discord.Color.gold())
        embed.set_footer(text=f"Announced by {interaction.user.display_name}")
        await self.target_channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Announcement sent to {self.target_channel.mention}", ephemeral=True)

@bot.tree.command(name="announcement", description="Admin: Create a formatted announcement popup")
@app_commands.default_permissions(administrator=True)
async def announcement(interaction: discord.Interaction, channel: discord.TextChannel):
    # Opens a text box so the admin can type long paragraphs comfortably
    await interaction.response.send_modal(AnnouncementModal(channel))

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# --- WEB SERVER FOR RENDER (KEEPS BOT ONLINE) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_health_check():
    # Render assigns a dynamic port, defaulting to 10000 if not found
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# Starts the web server in the background so it doesn't block the bot
threading.Thread(target=run_health_check, daemon=True).start()

# --- START BOT ---
# Securely fetches the bot token from Render
bot.run(os.getenv("MTU1MjkyNjE1ODg2NDI1NzA5NA.GMkoAm.IuCyXvaxbMOPfqpSeRfJKO7AwS84AybmRv44hU"))
