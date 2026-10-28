ui = true
disable_mlock = true

storage "raft" {
  path    = "/vault/data"
  node_id = "vault-node-1"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  cluster_address = "127.0.0.1:8201"
  tls_disable = "true"
}

api_addr     = "http://127.0.0.1:8200"
cluster_addr = "http://127.0.0.1:8201"

audit "file" {
  path   = "/vault/logs/audit.log"
  format = "json"
}

plugin_directory = "/etc/vault/plugins"