const adminNotifyr = process.env.NOTIFYR_MONGO_USERNAME;
const password = process.env.NOTIFYR_MONGO_PASSWORD;

if (!adminNotifyr || !password) {
  throw new Error("NOTIFYR_MONGO_USERNAME or NOTIFYR_MONGO_PASSWORD is not set");
}

const adminDb = db.getSiblingDB("notifyr");

adminDb.createUser({
  user: adminNotifyr,
  pwd: password,
  roles: [
    { role: "dbOwner", db: "notifyr" },
    {role:'userAdmin',db:"notifyr"}
  ]
});

print(`Created MongoDB user: ${adminNotifyr}`);