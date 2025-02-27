const assets = Runtime.getAssets();
const {NotifyrAuthService} = require(assets["/service.private.js"].path);

exports.handler = function(context, event, callback) {

  const twiml = new Twilio.twiml.MessagingResponse();
  twiml.message("Hello World!");
  console.log(event);

  return callback(null, twiml);
};
