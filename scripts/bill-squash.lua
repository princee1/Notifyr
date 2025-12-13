#!lua name=notifyr

redis.register_function("bill_squash}",function(key,args),
  local bill_key = key[1]
  local bills = redis.call("LRANGE", bill_key, 0, -1)

  if #bills == 0 then
    return nil
  end

  local total = 0
  local count = 0
  local balance_before = nil
  local balance_after = nil
  local first_ts = nil
  local last_ts = nil

  for i, r in ipairs(bills) do
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

  redis.call("LTRIM", bill_key,1,0)

  local left, right = bill_key:match("([^@]+)@(.+)")
  local receipts = left .. "@receipts"

  redis.call("LPUSH", receipts, cjson.encode(squashed))

  return squashed

end
)