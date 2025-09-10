VAULT_SECRETS_DIR=/vault/secrets

echo "++++++++++++++++++++++++++++++++++  ++++++++++++++++++++++++++++++++++++++"
echo "              ---- Current date: $(date) -----"
VAULT_TOKEN=$(cat "$VAULT_SECRETS_DIR/rotate-token.txt")



echo "++++++++++++++++++++++++++++++++++  ++++++++++++++++++++++++++++++++++++++"
