import discord
from discord import app_commands
from discord.ext import commands
from pymongo import MongoClient
import os

# Load token dan MongoDB URI dari .env
TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# Koneksi ke MongoDB
client = MongoClient(MONGO_URI)
db = client["school_of_rebels"]
collection = db["point"]

# Daftar kasta berdasarkan Student Points dan role Discord
RANKS = [
    ("Wretch", 0, 1355387300166766702),
    ("Ember", 50, 1355654614019477695),
    ("Seeker", 150, 1355654906723307601),
    ("Adept", 400, 1355655113946955899),
    ("Harbinger", 1000, 1355655268058402856),
    ("Sentinel", 2000, 1355655434194911303),
    ("Dominion", 4000, 1355655562947461320),
    ("Sovereign", 8000, 1355655788944949520),
]

# Fungsi untuk mendapatkan kasta berdasarkan Student Points
def get_rank(points):
    for rank, min_points, _ in reversed(RANKS):
        if points >= min_points:
            return rank
    return "Wretch"

# Fungsi untuk mendapatkan nama role berdasarkan kasta
def get_role(rank):
    for r, _, role_name in RANKS:
        if r == rank:
            return role_name
    return None

# Aktifkan intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True  # Wajib agar bot bisa mengelola role
bot = commands.Bot(command_prefix="!", intents=intents)

# Sinkronisasi Slash Commands
@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ Bot berhasil login sebagai {bot.user} | {len(synced)} commands synced")
    except Exception as e:
        print(f"❌ Gagal sinkronisasi: {e}")

# 📌 Fungsi untuk update role user saat naik kasta
async def update_role(member: discord.Member, new_rank: str):
    guild = member.guild
    new_role_name = get_role(new_rank)

    if new_role_name:
        new_role = discord.utils.get(guild.roles, name=new_role_name)
        if new_role:
            # Hapus role lama jika ada
            for r, _, role_name in RANKS:
                old_role = discord.utils.get(guild.roles, name=role_name)
                if old_role and old_role in member.roles and old_role != new_role:
                    await member.remove_roles(old_role)
            
            # Tambahkan role baru
            await member.add_roles(new_role)
            print(f"✅ {member.name} naik kasta menjadi {new_rank}, role {new_role_name} ditambahkan!")

# 📌 Slash command untuk membuat sesi belajar
@bot.tree.command(name="study", description="Buat atau selesaikan sesi belajar")
@app_commands.describe(action="create (membuat) atau complete (menyelesaikan)")
async def study(interaction: discord.Interaction, action: str):
    user_id = interaction.user.id
    user_name = interaction.user.name
    member = interaction.guild.get_member(user_id)

    # Cek apakah user sudah terdaftar di database
    user_data = collection.find_one({"user_id": user_id})

    if not user_data:
        # Jika user belum terdaftar, tambahkan ke database dengan rank default
        collection.insert_one({
            "user_id": user_id,
            "name": user_name,
            "student_points": 0,
            "rank": "Wretch",
            "active_study": False
        })
        user_data = collection.find_one({"user_id": user_id})

    if action.lower() == "create":
        if user_data["active_study"]:
            await interaction.response.send_message(f"⚠️ Kamu sudah memiliki sesi belajar yang aktif!", ephemeral=True)
            return
        
        # Set sesi belajar aktif
        collection.update_one({"user_id": user_id}, {"$set": {"active_study": True}})
        await interaction.response.send_message(f"📚 {interaction.user.mention} telah memulai sesi belajar! Gunakan `/study complete` untuk menyelesaikannya.")
    
    elif action.lower() == "complete":
        if not user_data["active_study"]:
            await interaction.response.send_message(f"⚠️ Kamu belum memulai sesi belajar!", ephemeral=True)
            return

        # Tambah Student Points
        points_gained = 10  # Student Points yang didapat
        new_points = user_data["student_points"] + points_gained

        # Cek apakah rank berubah
        new_rank = get_rank(new_points)
        rank_message = ""
        if new_rank != user_data["rank"]:
            rank_message = f"🎖️ Selamat! Kamu naik kasta menjadi **{new_rank}**!"
            await update_role(member, new_rank)  # Update role di Discord

        # Update database
        collection.update_one({"user_id": user_id}, {
            "$set": {"active_study": False, "student_points": new_points, "rank": new_rank}
        })

        await interaction.response.send_message(
            f"🎉 {interaction.user.mention} telah menyelesaikan sesi belajar dan mendapatkan **{points_gained} Student Points**!\n"
            f"📊 Total Student Points: **{new_points}**\n"
            f"{rank_message}"
        )
    
    else:
        await interaction.response.send_message("❌ Perintah tidak valid! Gunakan `/study create` atau `/study complete`.", ephemeral=True)

# 📌 Slash command untuk melihat leaderboard
@bot.tree.command(name="leaderboard", description="Lihat peringkat Student Points tertinggi")
async def leaderboard(interaction: discord.Interaction):
    top_students = collection.find().sort("student_points", -1).limit(10)  # Ambil top 10
    leaderboard_text = "**🏆 Leaderboard Student Points 🏆**\n"

    rank = 1
    for student in top_students:
        leaderboard_text += f"**{rank}. {student['name']}** - {student['student_points']} Student Points ({student['rank']})\n"
        rank += 1

    await interaction.response.send_message(leaderboard_text)

# Jalankan bot
bot.run(TOKEN)
