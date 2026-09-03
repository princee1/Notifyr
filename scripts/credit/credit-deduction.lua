#!lua name=notifyr

redis.register_function('credit-deduction',function(key,args)
    local balance = redis.call("GET", KEYS[1])

    if not balance then
        return {1}
    end

    balance = tonumber(balance)
    local bill_total = tonumber(ARGV[1])
    local overdraft_allowed = ARGV[2] == "1"

    if balance < bill_total and not overdraft_allowed then
        return {2, balance, bill_total}
    end

    local new_balance = balance - bill_total

    redis.call("SET", KEYS[1], new_balance)

    return {0, balance, new_balance}
end)