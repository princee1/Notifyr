REDIS_CONTAINER ?= redis
REDIS_DB ?= 1
COSTS_FILE ?= ./.notifyr/costs.json
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


deploy-server:
	docker compose -f 'docker-compose.yaml' up -d --build --no-deps --scale app=$$(cat ./.notifyr/deploy.json | jq -r '.scaling.app') app
	sleep 3 && clear
	@echo "Deployed app"
	docker compose -f 'docker-compose.yaml' up -d --build --no-deps beat
	sleep 3 && clear
	@echo "Deployed beat"
	docker compose -f 'docker-compose.yaml' up -d --no-deps --scale worker=$$(cat ./.notifyr/deploy.json | jq -r '.scaling.worker') worker
	sleep 3 && clear
	@echo "Deployed worker"
# 	docker compose -f 'docker-compose.yaml' up -d --no-deps --scale balancer=$(cat ./.notifyr/deploy.json | jq -r '.scaling.worker') balancer
	docker compose -f 'docker-compose.yaml' up -d traefik
# 	docker compose up -d dashboard
# 	docker compose up -d dmz
	clear
	@echo "Deployed docker server services"

deploy-data:
	./scripts/minio-creds.sh
	sleep 3 && clear
	./scripts/api_key-creds.sh
	sleep 3 && clear
	docker compose -f 'docker-compose.yaml' up --build vault-init
	sleep 1 && clear
	docker cp vault-init:/tmp/.secrets/  ./
	docker rm vault-init
	sleep 1 && clear
	docker compose -f 'docker-compose.yaml' up -d vault
	sleep 3 && clear
	@echo "Deployed docker services related to the data"

deploy: deploy-data deploy-server
	@echo "==================================="
	@echo "Deployment complete (Data & Server)"
	@echo "==================================="	

tunnel:
	ngrok http --url ${ngrok_url} 8080

prune:
	rm -f -R ./.secrets
	docker stop $$(docker compose -p notifyr ps -q) || true
	docker container prune -f
	docker image rm minio/minio:latest || true
	docker volume rm $$(docker volume ls -q) || true
	sleep 3 && clear
	@echo "Successfully completely prune the notifyr environnement"

purge:
	docker builder prune --all -f

refresh-apikey:
	./scripts/api_key-creds.sh -f
	docker compose -f 'docker-compose.yaml' up -d --no-deps --build app
	clear
	@echo "Successfully Refreshed the api_key"


refresh-cost:
	docker compose -f 'docker-compose.yaml' down traeffik
	docker compose -f 'docker-compose.yaml' up -d --build ofelia
	docker compose -f 'docker-compose.yaml' up -d --build app
	docker compose -f 'docker-compose.yaml' up -d --build worker
	clear && sleep 5
	docker compose -f 'docker-compose.yaml' up -d traeffik
	clear
	@echo "Successfully Refreshed the cost file"

monitor-on:
	docker compose down -d traeffik
	docker compose down -d dashboard
	docker compose down -d dmz
	sleep 3
	docker compose -f 'monitor.docker-compose.yaml' up -d
	clear
	@echo "Mode monitor is on"

monitor-off:
	docker compose -f 'monitor.docker-compose.yaml' down
	clear
	docker compose -f 'docker-compose.yaml' up -d traeffik
	docker compose -f 'docker-compose.yaml' up -d dashboard
	docker compose -f 'docker-compose.yaml' up -d dmz
	clear
	@echo "Mode monitor is off"





