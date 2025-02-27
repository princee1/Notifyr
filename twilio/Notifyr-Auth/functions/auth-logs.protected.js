const assets = Runtime.getAssets();
const {  NotifyrAuthService } = require(assets["/service.js"].path);

const CALL_TYPE = 'call'
const SMS_TYPE = 'sms'

function setCallLog(params) {
  
}

function setSmsLog(params){

}

exports.handler = async function (context, event, callback) {
  const service = new NotifyrAuthService(context,event);
  
  const type = service.type 
  let url; 
  if (type === CALL_TYPE)
    {
    url = '/call-incoming/status';
    body = setCallLog(event);
  }
  else if (type === SMS_TYPE){
    url = 'sms-incoming/status'
    body = setSmsLog(event);

  }
  else {
    
  }

  // TODO  parse in a understable object
  // TODO send to the server
  
  console.log(event);
  console.log(context);
  console.log(callback);
  // return callback(null,{})
};
