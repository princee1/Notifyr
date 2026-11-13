
path "auth/token/renew-self" {
    capabilities = ["update"]
}

path "auth/token/revoke/notifyr-database/creds/ncs-redis-ntfr-role-dynamic/*" {
    capabilities = ["update"]
}

path "auth/token/renew/notifyr-database/creds/ncs-redis-ntfr-role-dynamic/*" {
    capabilities = ["update"]
}

path "notifyr-database/creds/ncs-redis-ntfr-role-dynamic" {
    capabilities = ["read"]
}
