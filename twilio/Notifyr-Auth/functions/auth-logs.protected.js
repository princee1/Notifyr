const assets = Runtime.getAssets();
const { NotifyrAuthService } = require(assets["/service.js"].path);

const CALL_TYPE = "call";
const SMS_TYPE = "sms";

function setCallLog(params) {
  const {
    CallSid,
    RecordingSid,
    Duration,
    CallDuration,
    RecordingDuration,
    Direction,
    Timestamp,
    AccountSid,
    CallStatus,
    ToCity,
    SipResponse,
    To,
    From,
    SequenceNumber,
  } = params;

  temp = {
    CallSid,
    RecordingSid,
    Direction,
    Timestamp,
    AccountSid,
    CallStatus,
    SequenceNumber,
    ToCity,
    SipResponse,
    To,
    From,
  };
  if (CallStatus === "completed") {
    return { Duration, CallDuration, RecordingDuration, ...temp };
  }
  return temp;
}

function setSmsLog(params) {
  const { MessageSid, AccountSid, To, From, SmsSid, SmsStatus, MessageStatus } =
    params;
  return { MessageSid, AccountSid, To, From, SmsSid, SmsStatus, MessageStatus };
}

exports.handler = async function (context, event, callback) {
  
  const service = new NotifyrAuthService(context, event);
  const type = service.type;
  
  let url = String(service.url);
  let body;

  if (type === CALL_TYPE) {
    url += "/call-incoming/status";
    body = setCallLog(event);
  } else if (type === SMS_TYPE) {
    url += "/sms-incoming/status";
    body = setSmsLog(event);
  } else {

  }
  console.log(body);
  await service.sendLogStatus(body, url);

  // return callback(null,{})
};
