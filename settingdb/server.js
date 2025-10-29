const jsonServer = require('json-server');
const fs = require('fs');
const path = require('path');

const VAULT_SHARED_FILE = '/vault/api-key/setting-db-api-key.txt'
const settingsFile = path.join(__dirname, VAULT_SHARED_FILE);

let apiKey = null;

const yargs = require('yargs/yargs');
const { hideBin } = require('yargs/helpers');

const argv = yargs(hideBin(process.argv))
  .option('host', {
    type: 'string',
    default: '0.0.0.0',
    describe: 'Host to bind the server',
  })
  .option('port', {
    type: 'number',
    default: 3000,
    describe: 'Port to run the server',
  })
  .option('db', {
    type: 'string',
    default: path.join(__dirname, '/data/db.json'),
    describe: 'Path to the database file',
  })
  .argv;

const HOST = argv.host;
const PORT = argv.port;
const DB_FILE = argv.db;


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
const router = jsonServer.router(DB_FILE); // Your database file
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

server.listen(PORT, HOST, () => {
  console.log(`JSON Server is running on port ${PORT}`);
});
