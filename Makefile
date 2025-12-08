REDIS_CONTAINER ?= redis
REDIS_DB ?= 1
COSTS_FILE ?= costs.json
JQ ?= jq
DOCKER ?= docker

ngrok_url = https://elegant-gazelle-leading.ngrok-free.app


.PHONY: topup topup-cost reset-cost

# convenience alias
topup: topup-cost

topup-cost:
	@echo "Topping up phone,sms,email credits into $(REDIS_CONTAINER) DB $(REDIS_DB) from $(COSTS_FILE)"
	@for pair in $$($(JQ) -r '.credits | to_entries[] | select(.key=="phone" or .key=="sms" or .key=="email") | "\(.key)=\(.value)"' $(COSTS_FILE)); do \
		key=$${pair%%=*}; \
		val=$${pair#*=}; \
		echo "+ $$val -> $$key"; \
		$(DOCKER) exec -i $(REDIS_CONTAINER) redis-cli -n $(REDIS_DB) INCRBY "$$key" "$$val"; \
	done

reset-cost:
	@echo "Resetting credits in $(REDIS_CONTAINER) DB $(REDIS_DB) from $(COSTS_FILE)"
	@for pair in $$($(JQ) -r '.credits | to_entries[] | select(.key=="phone" or .key=="sms" or .key=="email")  | "\(.key)=\(.value)"' $(COSTS_FILE)); do \
		key=$${pair%%=*}; \
		val=$${pair#*=}; \
		echo "SET $$key -> $$val"; \
		$(DOCKER) exec -i $(REDIS_CONTAINER) redis-cli -n $(REDIS_DB) SET "$$key" "$$val"; \
	done

reset-cost-hard:
	@echo "Resetting credits in $(REDIS_CONTAINER) DB $(REDIS_DB) from $(COSTS_FILE)"
	@for pair in $$($(JQ) -r '.credits | to_entries[] | "\(.key)=\(.value)"' $(COSTS_FILE)); do \
		key=$${pair%%=*}; \
		val=$${pair#*=}; \
		echo "SET $$key -> $$val"; \
		$(DOCKER) exec -i $(REDIS_CONTAINER) redis-cli -n $(REDIS_DB) SET "$$key" "$$val"; \
	done

setup:
	./scripts/minio-creds.sh
	d
	docker cp vault-init:/tmp/secrets/* ./.notifyr/

tunnel:
	ngrok http --url ${ngrok_url} 8080


clear:
	docker builder prune --all -f


