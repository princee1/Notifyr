
path "auth/token/revoke/notifyr-database/*" {
  capabilities = ["update"]
}

path "auth/token/renew/notifyr-database/*" {
  capabilities = ["update"]
}

path "auth/token/revoke/notifyr-minio/*" {
  capabilities = ["update"]
}

path "auth/token/renew/notifyr-minio/*" {
  capabilities = ["update"]
}

path "auth/token/revoke/notifyr-rabbitmq/*" {
  capabilities = ["update"]
}

path "auth/token/renew/notifyr-rabbitmq/*" {
  capabilities = ["update"]
}

path "auth/token/revoke-self" {
  capabilities = ["update"]
}

path "auth/token/renew-self" {
  capabilities = ["update"]
}

# ---- SECRETS ENGINE ----

path "notifyr-secrets/" {
  capabilities = ["list"]
}

path "notifyr-secrets/tokens" {
  capabilities = ["read","list"]
}

path "notifyr-secrets/setting" {
  capabilities = ["read","list","update","create"]
}

path "notifyr-secrets/internal" {
  capabilities = ["read","list"]
}

path "notifyr-secrets/internal/*" {
  capabilities = ["read"]
}

path "notifyr-secrets/communication" {
  capabilities = ["read","list"]
}

path "notifyr-secrets/communication/*" {
  capabilities = ["create", "update", "read", "delete"]
}

path "notifyr-secrets/llm" {
  capabilities = ["read","list"]
}

path "notifyr-secrets/llm/*" {
  capabilities = ["create", "update", "read", "delete"]
}

path "notifyr-secrets/webhook" {
  capabilities = ["read","list"]
}

path "notifyr-secrets/webhook/*" {
  capabilities = ["create", "update", "read", "delete"]
}

path "notifyr-secrets/outbound" {
  capabilities = ["read","list"]
}

path "notifyr-secrets/outbound/*" {
  capabilities = ["create", "update", "read", "delete"]
}

path "notifyr-secrets/messages" {
  capabilities = ["read","list"]
}

path "notifyr-secrets/messages/*" {
  capabilities = ["create", "update", "read", "delete"]
}

path "notifyr-secrets/settings" {
  capabilities = ["create", "update", "read", "delete"]
}

path "notifyr-security/policies/" {
  capabilities = ["list"]
}

path "notifyr-security/policies/*" {
  capabilities = ["create", "update", "read", "delete"]
}

path "notifyr-security/clients/*" {
  capabilities = ["create", "update", "read", "delete","list"]
}

# path "notifyr-security/clients/*/sessions/" {
#   capabilities = ["list"]
# }

# ---- GENERATION ID ENGINE ---- 

path "notifyr-generation/data/generation-id" {
  capabilities = ["create", "update", "read", "delete"]
}

path "notifyr-generation/metadata/generation-id" {
  capabilities = ["read", "list", "delete"]
}

# ---- TRANSIT ENGINE ----

path "transit/" {
  capabilities = ["list"]
}

# Encrypt and decrypt data
path "notifyr-transit/encrypt/*" {
  capabilities = ["update"]
}

path "notifyr-transit/decrypt/*" {
  capabilities = ["update"]
}

path "notifyr-transit/sign/*" {
  capabilities = ["update"]
}

path "notifyr-transit/verify/*" {
  capabilities = ["update"]
}

path "notifyr-transit/keys/*" {
  capabilities = ["read"]
}

# ---- RABBITMQ ENGINE ----

path "notifyr-rabbitmq/creds/celery-ntfr-role" {
  capabilities = ["read"]
}

# ---- DATABASE ENGINE ----

path "notifyr-database/creds/app*" {
  capabilities = ["read"]
}

path "notifyr-database/creds/agentic*" {
  capabilities = ["read"]
}

path "notifyr-database/roles" {
  capabilities = ["list"]
}

# ---- MINIO ENGINE ----

path "notifyr-minio/creds/app*" {
  capabilities = ["read"]
}

path "notifyr-minio/sts/app*" {
  capabilities = ["update","read"]
}
