const adminNotifyr = process.env.NOTIFYR_MONGO_USERNAME;
const password = process.env.NOTIFYR_MONGO_PASSWORD;
const vaultpass = process.env.VAULTPASS;

if (!adminNotifyr || !password) {
  throw new Error("NOTIFYR_MONGO_USERNAME or NOTIFYR_MONGO_PASSWORD is not set");
}

const notifyrDb = db.getSiblingDB("notifyr");

notifyrDb.createUser({
  user: adminNotifyr,
  pwd: password,
  roles: [
    { role: "dbOwner", db: "notifyr" },
    { role: 'userAdmin', db: "notifyr" }
  ]
});

const vault_user = 'vault_ntfr_jobs_static_user';

notifyrDb.createUser({
  user: vault_user,
  pwd: vaultpass,
  roles: [
    { "role": "readWrite", "db": "notifyr", "collection": "aps" },
    { "role": "readWrite", "db": "notifyr", "collection": "celery" },
    { "role": "readWrite", "db": "notifyr", "collection": "tasks" }]
});

notifyrDb.aps.createIndex(
  { next_run_time: 1 },
  { sparse: true, name: "next_run_time_1" }
)

print(`Created MongoDB user: ${adminNotifyr}`);