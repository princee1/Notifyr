local key = KEYS[1]
local receipts = redis.call("LRANGE", key, 0, -1)

if #receipts == 0 then
  return nil
end

local total = 0
local count = 0
local balance_before = nil
local balance_after = nil
local first_ts = nil
local last_ts = nil

for i, r in ipairs(receipts) do
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

redis.call("LTRIM", key,1,0)

local key = "credit[notifyr:receipts]2025-12"
local left, right = s:match("([^%[]+)%[(.+)")
local result = left .. "/summary"

redis.call("LPUSH", result, cjson.encode(squashed))

return squashed
