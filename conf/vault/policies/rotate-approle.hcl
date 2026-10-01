
path "auth/token/renew-self" {
  capabilities = ["update"]
}

path "auth/approle/role/notifyr-app-role/secret-id" {
  capabilities = ["update","create","read"]
}

path "auth/approle/role/notifyr-dmz-role/secret-id" {
  capabilities = ["update","create","read"]
}

path "transit/keys/*/rotate" {
  capabilities = ["update"]
}

path "notifyr-database/rotate-root/*" {
  capabilities=["update"]
}

path "notifyr-minio/config/rotate-root/" {
  capabilities = ["update"]
}

path "notifyr-config/*" {
  capabilities = ["update","read","create","list","delete"]
}
