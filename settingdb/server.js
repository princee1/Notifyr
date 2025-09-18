const jsonServer = require('json-server');
const fs = require('fs');
const path = require('path');

const VAULT_SHARED_FILE = 'vault/shared/setting-db-api-key.json'
const settingsFile = path.join(__dirname, VAULT_SHARED_FILE);

let apiKey = null;

function loadApiKey() {
  try {
    const apiKey = fs.readFileSync(settingsFile, 'utf-8');
    console.log('API key updated from file:', apiKey ? '[hidden]' : 'null');
  } catch (err) {
    console.error('Error reading API key file:', err.message);
    apiKey = null;
  }
}

loadApiKey();

fs.watch(settingsFile, (eventType) => {
  if (eventType === 'change') {
    console.log('Settings file changed, reloading API key...');
    loadApiKey();
  }
});

const server = jsonServer.create();
const router = jsonServer.router('db.json'); // Your database file
const middlewares = jsonServer.defaults();

server.use((req, res, next) => {
  const clientKey = req.header('X-SETTING-DB-API-KEY');

  if (!clientKey || clientKey !== apiKey) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  next();
});

server.use(middlewares);
server.use(router);

const PORT = 3000;
server.listen(PORT, () => {
  console.log(`JSON Server is running on port ${PORT}`);
});
