const { Client, GatewayIntentBits } = require('discord.js');
const { REST } = require('@discordjs/rest');
const { Routes } = require('discord-api-types/v10');
const mongoose = require('mongoose');
const User = require('./models/User'); // Model database pengguna
require('dotenv').config();

const client = new Client({ intents: [GatewayIntentBits.Guilds] });

const commands = [
    {
        name: 'balance',
        description: 'Cek saldo Rebels kamu',
    },
    {
        name: 'transfer',
        description: 'Transfer Rebels ke pengguna lain',
        options: [
            {
                name: 'user',
                type: 6, // USER
                description: 'Pilih pengguna yang ingin dikirimi uang',
                required: true
            },
            {
                name: 'amount',
                type: 4, // INTEGER
                description: 'Jumlah uang yang ingin ditransfer',
                required: true
            }
        ]
    },
    {
        name: 'leaderboard',
        description: 'Lihat 10 pengguna dengan saldo tertinggi',
    }
];

// Mengupdate Slash Commands
const rest = new REST({ version: '10' }).setToken(process.env.TOKEN);
(async () => {
    try {
        console.log('🔄 Mengupdate slash commands...');
        await rest.put(Routes.applicationCommands(process.env.CLIENT_ID), { body: commands });
        console.log('✅ Slash commands berhasil diperbarui!');
    } catch (error) {
        console.error('❌ Gagal mengupdate commands:', error);
    }
})();

// Koneksi ke database MongoDB
mongoose.connect(process.env.MONGO_URI, { useNewUrlParser: true, useUnifiedTopology: true })
    .then(() => console.log('✅ Database MongoDB terhubung'))
    .catch(err => console.error('❌ Gagal menghubungkan ke MongoDB:', err));

client.once('ready', () => {
    console.log(`🚀 Bot ${client.user.tag} siap digunakan!`);
});

client.on('interactionCreate', async interaction => {
    if (!interaction.isCommand()) return;

    const { commandName, options } = interaction;
    const userId = interaction.user.id;

    // 🏦 **Command /balance** (Cek saldo)
    if (commandName === 'balance') {
        let user = await User.findOne({ userId });
        if (!user) {
            user = await User.create({ userId, balance: 0 });
        }

        await interaction.reply({
            embeds: [{
                title: '🏦 Saldo Rebels',
                description: `💰 **Saldo:** ${user.balance} Rebels`,
                color: 0xffd700,
                fields: [{ name: 'User ID', value: userId }],
                footer: { text: 'Rebels System' }
            }]
        });
    }

    // 💸 **Command /transfer** (Transfer uang)
    else if (commandName === 'transfer') {
        const targetUser = options.getUser('user');
        const amount = options.getInteger('amount');

        if (targetUser.id === userId) {
            return interaction.reply({ content: '❌ Kamu tidak bisa mentransfer ke diri sendiri!', ephemeral: true });
        }

        let sender = await User.findOne({ userId });
        let receiver = await User.findOne({ userId: targetUser.id });

        if (!sender || sender.balance < amount) {
            return interaction.reply({ content: '❌ Saldo kamu tidak cukup!', ephemeral: true });
        }

        if (!receiver) {
            receiver = await User.create({ userId: targetUser.id, balance: 0 });
        }

        // Update saldo dengan findOneAndUpdate
        await User.findOneAndUpdate({ userId }, { $inc: { balance: -amount } });
        await User.findOneAndUpdate({ userId: targetUser.id }, { $inc: { balance: amount } });

        await interaction.reply({
            embeds: [{
                title: '💸 Transfer Berhasil!',
                description: `✅ **${amount} Rebels** telah dikirim ke ${targetUser.tag}`,
                color: 0x00ff00,
                fields: [
                    { name: 'Pengirim', value: `<@${userId}>`, inline: true },
                    { name: 'Penerima', value: `<@${targetUser.id}>`, inline: true },
                    { name: 'Jumlah', value: `${amount} Rebels`, inline: true }
                ],
                footer: { text: 'Rebels System' }
            }]
        });
    }

    // 🏆 **Command /leaderboard** (Leaderboard 10 saldo tertinggi)
    else if (commandName === 'leaderboard') {
        const topUsers = await User.find().sort({ balance: -1 }).limit(10);
        
        if (topUsers.length === 0) {
            return interaction.reply({ content: '❌ Tidak ada data di leaderboard.', ephemeral: true });
        }

        let leaderboard = topUsers.map((user, index) => {
            return `**${index + 1}.** <@${user.userId}> - ${user.balance} Rebels`;
        }).join("\n");

        await interaction.reply({
            embeds: [{
                title: '🏆 Rebels Leaderboard',
                description: leaderboard,
                color: 0x1e90ff,
                footer: { text: 'Rebels System' }
            }]
        });
    }
});

client.login(process.env.TOKEN);
