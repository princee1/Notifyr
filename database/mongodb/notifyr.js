const adminDb = db.getSiblingDB('admin');

db = db.getSiblingDB('agentic-notifyr');
db = db.getSiblingDB('app-notifyr');

// Task administrator
adminDb.createUser({
    user: '${NOTIFYR_MONGO_USERNAME}',
    pwd: '${NOTIFYR_MONGO_PASSWORD}',
    roles: [
        { role: 'dbOwner', db: 'notifyr' }
    ]
});