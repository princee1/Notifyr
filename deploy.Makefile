REDIS_CONTAINER ?= redis
REDIS_DB ?= 1
COSTS_FILE ?= costs.json
JQ ?= jq
DOCKER ?= docker

.PHONY: topup topup-cost reset-cost

# convenience alias
topup: topup-cost

topup-cost:
	@echo "Topping up phone,sms,email credits into $(REDIS_CONTAINER) DB $(REDIS_DB) from $(COSTS_FILE)"
	@$(JQ) -r '.credits | to_entries[] | select(.key=="phone" or .key=="sms" or .key=="email") | "\(.key) \(.value)"' $(COSTS_FILE) | \
        while read key val; do \
            echo "+ $$val -> $$key"; \
            $(DOCKER) exec -i $(REDIS_CONTAINER) redis-cli -n $(REDIS_DB) INCRBY "$$key" "$$val"; \
        done

# reset-cost: set each credit key in Redis to the amount defined in costs.json
reset-cost:
	@echo "Resetting credits in $(REDIS_CONTAINER) DB $(REDIS_DB) from $(COSTS_FILE)"
	@$(JQ) -r '.credits | to_entries[] | "\(.key) \(.value)"' $(COSTS_FILE) | \
        while read key val; do \
            echo "SET $$key -> $$val"; \
            $(DOCKER) exec -i $(REDIS_CONTAINER) redis-cli -n $(REDIS_DB) SET "$$key" "$$val"; \
        done