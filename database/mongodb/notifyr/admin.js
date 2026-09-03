const adminNotifyr = process.env.NOTIFYR_MONGO_USERNAME;
const password = process.env.NOTIFYR_MONGO_PASSWORD;

if (!adminNotifyr || !password) {
  throw new Error("NOTIFYR_MONGO_USERNAME or NOTIFYR_MONGO_PASSWORD is not set");
}

const notifyrDb = db.getSiblingDB("notifyr");

notifyrDb.createUser({
  user: adminNotifyr,
  pwd: password,
  roles: [
    { role: "dbOwner", db: "notifyr" },
    {role:'userAdmin',db:"notifyr"}
  ]
});

notifyrDb.aps.createIndex(
    { next_run_time: 1 },
    { sparse: true, name: "next_run_time_1" }
)

print(`Created MongoDB user: ${adminNotifyr}`);