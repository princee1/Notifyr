#!lua name=notifyr

redis.register_function(
  'credit_transaction}',
  function(keys, args)

    local credit_key  = keys[1]
    local bill_key = keys[2]

    local op        = args[1]
    local value     = tonumber(args[2])
    local request_id = args[3]
    local created_at = args[4]

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
      definition = (op == "set" and "Set balance" or "Topup"),
      credit = credit_key,
      created_at = created_at,
      total = value,
      balance_before = before,
      balance_after = after
    }))

    return after
  end
)
