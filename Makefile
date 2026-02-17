# ==============================================================================
# 1. Configuration Variables
# ==============================================================================

# Essential Utilities/Containers
REDIS_CONTAINER ?= redis
JQ              ?= jq
DOCKER          ?= docker

# Docker Compose Configuration
# Use a variable for the docker-compose file path to avoid repetition
DOCKER_COMPOSE_FILE ?= docker-compose.yaml
DOCKER_COMPOSE_BASE = $(DOCKER) compose -f '$(DOCKER_COMPOSE_FILE)'
DOCKER_COMPOSE_MONITOR = $(DOCKER) compose -f 'monitor.docker-compose.yaml'

# Deployment Paths
DEPLOY_CONFIG   = ./.notifyr/deploy.json
SECRETS_DIR     = ./.secrets

# Other Services
ngrok_url = https://elegant-gazelle-leading.ngrok-free.app


# ==============================================================================
# 2. Helper Functions (DRY Principle)
# ==============================================================================

# Helper to run docker compose command and log the action
define COMPOSE_RUN
	@echo "--- 🛠️  $(1): Running $(2) $3..."
	$(DOCKER_COMPOSE_BASE) $(2) $3
	@echo "--- ✅  $(1): Completed."
	@echo ""
	@sleep 1 
endef

# Helper to run a service with scaling logic
define COMPOSE_SCALE
	@echo "--- 🛠️  Scaling and deploying $(1)..."
	$(DOCKER_COMPOSE_BASE) up -d --scale $(1)=$$(cat $(DEPLOY_CONFIG) | $(JQ) -r '.scaling.$(1)') $(1)
	@echo "--- ✅  $(1): Deployed and scaled."
	@echo ""
	@sleep 3
endef


# ==============================================================================
# 3. Core Deployment Targets
# ==============================================================================

.PHONY: deploy deploy-data deploy-server tunnel prune purge refresh-apikey refresh-cost monitor-on monitor-off

notifyr-app:
	$(call COMPOSE_SCALE,app)

deploy-beat:
	@if [ "$$(cat $(DEPLOY_CONFIG) | $(JQ) -r '.scaling.worker')" -gt 0 ]; then \
		echo "--- 🛠️ Creating the beat server because at least one worker will be deployed"; \
		$(DOCKER_COMPOSE_BASE) up -d beat; \
		echo "--- ✅ Beat service is deployed"; \
	else \
		echo "--- ⏭️ No workers is expected no need for the beat service"; \
	fi

deploy-agentic:
	@if [ "$$(cat $(DEPLOY_CONFIG) | $(JQ) -r '.capabilities.agentic')" = "true" ]; then \
		echo "================================================="; \
		echo "🛠️ Creating the agentic service because the ai functionality is required"; \
		echo "================================================="; \
		$(DOCKER_COMPOSE_BASE) up -d agentic; \
		echo "--- ✅ agentic service is deployed"; \
	else \
		echo "--- ⏭️ Agentic Service: Skipped (value = False)"; \
	fi

deploy-agentic-data:
	@if [ "$$(cat $(DEPLOY_CONFIG) | $(JQ) -r '.capabilities.agentic')" = "true" ]; then \
		if [ "$$(cat $(DEPLOY_CONFIG) | $(JQ) -r '.database.qdrant')" = "true" ]; then \
			echo "--- 🛠️ Creating the vector database Qdrant"; \
			docker compose up -d qdrant; \
			echo "--- ✅ Qdrant service is deployed"; \
		fi; \
		if [ "$$(cat $(DEPLOY_CONFIG) | $(JQ) -r '.database.graphiti')" = "true" ]; then \
			echo "--- 🛠️ Creating the knowledge graph database"; \
			docker compose up -d neo4j; \
			echo "--- ✅ Neo4j service is deployed"; \
		fi; \
	else \
		echo "--- ⏭️ Agentic Service: Skipped (value = False)"; \
	fi
	@echo ""
	
build:
	@echo "================================================="
	@echo "🛠️  Building Docker services in $(DOCKER_COMPOSE_FILE)..."
	@echo "================================================="
	docker compose build minio
	docker compose build mongodb
	docker compose build postgres
	docker compose build redis
	docker compose build memcached
	docker compose build rabbitmq
	docker compose build vault-init
	docker compose build app
	docker compose build beat
	docker compose build agentic
	docker compose build ncs
	docker compose build neo4j
	docker compose build memgraph
	docker compose build ofelia
	docker compose build traeffik
	docker compose build qdrant
	$(DOCKER_COMPOSE_BASE) build
	@echo "================================================="
	@echo "🎉  All images built successfully!"
	@echo "================================================="

# Target to deploy all server components
deploy-server: deploy-beat
	@echo "================================================="
	@echo "🚀 Starting Server Services Deployment"
	@echo "================================================="

# 	# Deploy and Scale Core Application Services
	$(call COMPOSE_SCALE,app)
	$(call COMPOSE_SCALE,worker)
# 	$(call COMPOSE_RUN, Beat Service, up -d, balancer)

# 	# Deploy Infrastructure Services (Traefik/Gateway)
	$(call COMPOSE_RUN, Traefik, up -d, traefik)
	$(call COMPOSE_RUN, Ofelia Scheduler ,up -d, ofelia)

	@echo "================================================="
	@echo "✅ Server Services Deployment Complete"
	@echo "================================================="

server-down:
	$(call COMPOSE_RUN, Beat Service,down, beat)
	$(call COMPOSE_RUN, App Service,down, app)
	$(call COMPOSE_RUN, Worker Service,down, worker)


# Target to deploy all data components and run setup jobs
deploy-data:
	@echo "================================================="
	@echo "💾 Starting Data & Secrets Setup"
	@echo "================================================="

# 	# 1. Create Initial Secrets
	@echo "--- 🔑 Initializing Minio Credentials..."
	./scripts/generate-creds.sh minio
	@echo "--- ✅ Minio Credentials ready."

	@echo "--- 🔑 Initializing API Key Credentials..."
	./scripts/generate-creds.sh api-key
	@echo "--- ✅ API Key Credentials ready."

	@echo "--- 🔑 Initializing MongoDB Replicas Keyfile"
	./scripts/generate-creds.sh mongodb
	@echo "--- ✅ MongoDB keyfile ready."
	@sleep 3 && clear

	$(call COMPOSE_RUN, MongoDB Setup, up -d, mongodb)
	@echo "waiting for mongodb to setup... " && sleep 5 && clear
	$(MAKE) deploy-agentic-data
	


# 	# 2. Vault Initialization
	$(call COMPOSE_RUN, Vault Init, up, vault-init)
	
# 	# 3. Extract Secrets and Cleanup Init Container
	@echo "--- 📦 Copying secrets from vault-init container..."
	$(DOCKER) cp vault-init:/tmp/$(SECRETS_DIR) $(shell dirname $(SECRETS_DIR))/
	$(DOCKER) rm vault-init
	@echo "--- ✅ Secrets copied and vault-init removed."
	@sleep 1 && clear
	
# 	# 4. Deploy Persistent Vault
	$(call COMPOSE_RUN, Vault Persistent, up -d, vault)
	@sleep 3 && clear

# 	# 5. Run Initial NCS Setup
	@clear && echo "Waiting 30 sec for the vault to be unsealed..." & sleep 30
	$(call COMPOSE_RUN, NCS Setup, run -e ALLOWED_INIT=on --rm , ncs /ncs-utils.sh initialize)
	$(call COMPOSE_RUN, NCS Always On, up -d, ncs)
	@echo "--- ✅ Initial NCS Setup (Hard Reset) complete."
	@sleep 3 && clear
	@echo "================================================="
	@echo "✅ Data & Secrets Setup Complete"
	@echo "================================================="


# Main deployment target
deploy: deploy-data deploy-agentic deploy-server
	@sleep 10 && clear
	@echo "\n================================================="
	@echo "🟢 FULL DEPLOYMENT COMPLETE (Data & Server) 🟢"
	@echo "================================================="

agentic: deploy-data deploy-agentic
	@echo "\n================================================="
	@echo "🚀 Starting AGENTIC-ONLY Deployment"
	@echo "================================================="
	@echo "--- 🛠️  Stopping dependent services for AGENTIC deployment..."
	@sleep 30 && clear
	$(DOCKER_COMPOSE_BASE) down postgres
	$(DOCKER_COMPOSE_BASE) down rabbitmq
	$(DOCKER_COMPOSE_BASE) down minio
	$(DOCKER_COMPOSE_BASE) down ncs
	@echo "\n================================================="
	@echo "🟢 AGENTIC DEPLOYMENT COMPLETE 🟢"
	@echo "================================================="


# ==============================================================================
# 4. Maintenance & Utility Targets
# ==============================================================================

tunnel:
	@echo "🌐 Starting ngrok tunnel to ${ngrok_url}"
	ngrok http --url=${ngrok_url} http://api.notifyr.io:80

prune:
	@read -p "Are you sure you want to hard prune the notifyr environment? [y/N] " answer; \
	if [ "$$answer" = "y" ] || [ "$$answer" = "Y" ]; then \
		echo "================================================="; \
		echo "🧹 Cleaning up notifyr environment (Hard Prune)"; \
		echo "================================================="; \
		echo "--- 🗑️  Removing local secrets directory: $(SECRETS_DIR)"; \
		rm -f -R $(SECRETS_DIR); \
		echo "--- 🛑 Stopping all notifyr project containers..."; \
		$(DOCKER) stop $$($(DOCKER_COMPOSE_BASE) ps -q) || true; \
		echo "--- 🗑️  Pruning stopped containers..."; \
		$(DOCKER) container prune -f; \
		echo "--- 🗑️  Removing all anonymous volumes..."; \
		$(DOCKER) volume rm $$(docker volume ls -q) || true; \
		sleep 3; \
		echo "================================================="; \
		echo "✅ notifyr environment completely pruned."; \
		echo "================================================="; \
	else \
		echo "❌ Prune aborted."; \
	fi


purge:
	@echo "🧹 Pruning Docker builder cache (all)"
	$(DOCKER) builder prune --all -f
	@echo "✅ Docker build cache purged."


refresh-apikey:
	@echo "================================================="
	@echo "🔄 Refreshing API Key and Redeploying App"
	@echo "================================================="
	@echo "--- 🔑 Creating new API Key..."
	./scripts/generate-creds.sh api-key --force
	@echo "--- 🚀 Redeploying 'app' service with new build..."
	$(call COMPOSE_RUN, App Update, up -d, app)
	@echo "================================================="
	@echo "✅ API Key Refreshed."
	@echo "================================================="


refresh-cost:
	@echo "================================================="
	@echo "💰 Refreshing Cost File and Top-up"
	@echo "================================================="
	
	$(call COMPOSE_RUN, Traefik Down, down, traeffik)

	$(call COMPOSE_RUN, App Update, up -d --build, app)
	$(call COMPOSE_RUN, Worker Update, up -d --build,worker)
	@sleep 5 && clear

	$(call COMPOSE_RUN, NCS Topup, run --rm, ncs /ncs-utils.sh topup)

	$(call COMPOSE_RUN, Traefik Up, up -d, traeffik)

	@echo "================================================="
	@echo "✅ Cost File Refreshed and NCSs Topped Up."
	@echo "================================================="


update:
	@echo "================================================="
	@echo "💰 Removing old Notifyr container"
	@echo "================================================="
	$(call COMPOSE_RUN, App Service, build, app)
	$(call COMPOSE_SCALE,app)
	$(call COMPOSE_RUN, Beat Service, up -d --build --no-deps, beat)
	$(call COMPOSE_SCALE,worker)
	@echo "================================================="
	@echo "✅ New container deployed with updated code"
	@echo "================================================="


# ==============================================================================
# 5. Monitoring Targets
# ==============================================================================

monitor-on:
	@echo "================================================="
	@echo "👁️  SWITCHING TO MONITORING MODE: ON"
	@echo "================================================="
	
# 	# 1. Stop web-facing/DMZ services from base compose
	$(call COMPOSE_RUN, Base Services Down, down, traeffik dashboard dmz)
	
	@sleep 3 && clear
	
# 	# 2. Start monitoring stack
	@echo "--- 🚀 Starting monitoring stack from 'monitor.docker-compose.yaml'..."
	$(DOCKER_COMPOSE_MONITOR) up -d
	@echo "--- ✅ Monitoring stack deployed."
	
	@echo "================================================="
	@echo "✅ Mode Monitor is ON."
	@echo "================================================="


monitor-off:
	@echo "================================================="
	@echo "👁️  SWITCHING TO MONITORING MODE: OFF"
	@echo "================================================="
	
# 	# 1. Stop monitoring stack
	@echo "--- 🛑 Stopping monitoring stack..."
	$(DOCKER_COMPOSE_MONITOR) down
	@echo "--- ✅ Monitoring stack stopped."

# 	# 2. Restart web-facing/DMZ services on base compose
	$(call COMPOSE_RUN, Base Services Up, up -d, traeffik dashboard dmz)
	
	@echo "================================================="
	@echo "✅ Mode Monitor is OFF."
	@echo "================================================="