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

notifyr:
	./scripts/minio-creds.sh
	docker compose -f 'docker-compose.yaml' up --build vault-init
	docker cp vault-init:/tmp/secrets/  ./.notifyr/
	docker rm vault-init
	docker compose -f 'docker-compose.yaml' up -d vault
	sleep 10 && echo "Waiting for initialization..."
	clear
	docker compose -f 'docker-compose.yaml' up -d --no-deps --scale app=$$(cat ./.notifyr/deploy.json | jq -r '.scaling.app') app
	docker compose -f 'docker-compose.yaml' up -d --no-deps beat
	docker compose -f 'docker-compose.yaml' up -d --no-deps --scale worker=$$(cat ./.notifyr/deploy.json | jq -r '.scaling.worker') worker
# 	docker compose -f 'docker-compose.yaml' up -d --no-deps --scale balancer=$(cat ./.notifyr/deploy.json | jq -r '.scaling.worker') balancer
	docker compose -f 'docker-compose.yaml' up -d traeffik
# 	docker compose up -d dashboard
# 	docker compose up -d dmz
	clear
	echo "Setup done"

tunnel:
	ngrok http --url ${ngrok_url} 8080

clear:
	docker stop $$(docker compose -p notifyr ps)
	docker container prune -f
	rm -f -R ./.notifyr/secrets
	docker volume rm $$(docker volume ls -q)

purge:
	docker builder prune --all -f

monitor-on:
	docker compose down -d traeffik
	docker compose down -d dashboard
	docker compose down -d dmz
	sleep 4
	docker compose -f 'monitor.docker-compose.yaml' up

monitor-off:
	docker compose -f 'docker-compose.yaml' up traeffik
	docker compose -f 'docker-compose.yaml' up -d dashboard
	docker compose -f 'docker-compose.yaml' up -d dmz
	sleep 4
	docker compose -f 'monitor.docker-compose.yaml' down



