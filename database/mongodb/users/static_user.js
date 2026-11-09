const vaultpass = process.env.VAULTPASS;

const appDb = db.getSiblingDB("app");
const agenticDb = db.getSiblingDB("agentic");
const creditDb = db.getSiblingDB("credit");
const adminDb = db.getSiblingDB('admin')

const app_vault_user = 'vault_ntfr_app_static_user';
const agentic_vault_user = 'vault_ntfr_agentic_static_user';
const credit_vault_user = 'vault_ntfr_credit_static_user';

adminDb.createUser({
    user: app_vault_user,
    pwd: vaultpass,
    roles: [
        { "role": "readWrite", "db": "app", "collection": "communication" },
        { "role": "readWrite", "db": "app", "collection": "webhook" },
        { "role": "readWrite", "db": "app", "collection": "custom" },
        { "role": "readWrite", "db": "app", "collection": "outbound" },
        { "role": "readWrite", "db": "app", "collection": "errorProfile" },
        { "role": "readWrite", "db": "app", "collection": "workflow" }]
});

adminDb.createUser({
    user: agentic_vault_user,
    pwd: vaultpass,
    roles: [
        { "role": "readWrite", "db": "agentic", "collection": "agent" },
        { "role": "readWrite", "db": "agentic", "collection": "llm" },
        { "role": "readWrite", "db": "agentic", "collection": "chat" },
        { "role": "readWrite", "db": "agentic", "collection": "tool" },
        { "role": "readWrite", "db": "agentic", "collection": "store" },
        { "role": "readWrite", "db": "agentic", "collection": "chat_write" }]
});

// adminDb.createUser({
//     user: credit_vault_user,
//     pwd: vaultpass,
//     roles: []
// });