#!lua name=notifyr

redis.register_function('credit_transaction', function(keys, args)

    local credit_key = keys[1]
    local bill_key   = keys[2]

    local op         = args[1]
    local value      = tonumber(args[2])
    local issuer     = args[3]
    local request_id = args[4]
    local created_at = args[5]

    if not value then
        return redis.error_reply("value must be numeric")
    end

    local before = tonumber(redis.call("GET", credit_key) or "0")
    local after

    if op == "incr" then
        after = before + value
        redis.call("INCRBY", credit_key, value)

    elseif op == "set" then
        after = value
        redis.call("SET", credit_key, value)

    else
        return redis.error_reply("invalid operation: " .. tostring(op))
    end

    redis.call("LPUSH", bill_key, cjson.encode({
        request_id = request_id,
        issuer = issuer,
        definition = (op == "set" and "Set balance" or "Topup"),
        created_at = created_at,
        purchase_total = 0,
        refund_total = value,
        total = -value,
        balance_before = before,
        balance_after = after
    }))

    return after
end)


redis.register_function('bill_squash', function(keys, args)

    local bill_key = keys[1]
    local credit_key = keys[2]
    local bills = redis.call("LRANGE", bill_key, 0, -1)

    if #bills == 0 then
        local before = tonumber(redis.call("GET", credit_key) or "0")

        local squashed = {
            total_amount =0,
            count = 0,
            balance_before = before,
            balance_after = before,
            from = nil,
            to = nil
        }

        redis.call("LPUSH", receipts, cjson.encode(squashed))
        return squashed
    end

    local total = 0
    local count = 0
    local balance_before = nil
    local balance_after = nil
    local first_ts = nil
    local last_ts = nil

    for _, r in ipairs(bills) do
        local obj = cjson.decode(r)

        if obj.amount then
            total = total + obj.amount
        end

        if not balance_before then
            balance_before = obj.balance_before
        end

        balance_after = obj.balance_after
        count = count + 1

        local ts = obj.created_at
        if not first_ts then first_ts = ts end
        last_ts = ts
    end

    local squashed = {
        total_amount = total,
        count = count,
        balance_before = balance_before,
        balance_after = balance_after,
        from = first_ts,
        to = last_ts
    }

    -- Clear bills list
    redis.call("LTRIM", bill_key, 1, 0)

    local left = bill_key:match("([^@]+)")
    local receipts = left .. "@receipts"

    redis.call("LPUSH", receipts, cjson.encode(squashed))

    return squashed
end)
