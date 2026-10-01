
path "auth/token/renew-self" {
    capabilities = ["update"]
}

path "notifyr-minio/creds/dmz*" {
    capabilities = ["read"]
}

path "notifyr-minio/sts/dmz*" {
    capabilities = ["update","read"]
}
