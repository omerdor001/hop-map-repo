const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    }
});

client.once('ready', async () => {
    console.log('Client is ready!');
    const number = ''; // international format: country code + number without leading 0
    await client.sendMessage(`${number}@c.us`, 'Hello');
});

client.on('qr', qr => {
    qrcode.generate(qr, {small: true});
});

client.on('message_create', (message) => {
	if (message.body === '!ping') {
		// send back "pong" to the chat the message was sent in
		client.sendMessage(message.from, 'pong');
	}
});


client.initialize();
