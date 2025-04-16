const assets = Runtime.getAssets();
const { NotifyrAuthService } = require(assets["/service.js"].path);

const CALL_TYPE = "call";
const SMS_TYPE = "sms";

function setCallLog(params) {
  subject_id=params.subject_id ?? null

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
    To,
    From,
    subject_id,
  };

  if (temp.RecordingSid === undefined)
      temp.RecordingSid = null;

  if (CallStatus === "completed") {
    return { Duration, CallDuration, "RecordingDuration":RecordingDuration??null, ...temp };
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
  let body;

  if (service.type === CALL_TYPE) {
    url = "/twilio/call/incoming/status/";
    body = setCallLog(event);
  } else if (service.type === SMS_TYPE) {
    url = "/twilio/sms/incoming/status/";
    body = setSmsLog(event);
  } else {

  }
  
  console.log(body)
  await service.sendLogStatus(body, url);

  // return callback(null,{})
};
