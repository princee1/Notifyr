exports.handler = function(context, event, callback) {
  const twiml = new Twilio.twiml.VoiceResponse();
  console.log(context);
  console.log(event)
  console.log(event.request.headers);
  twiml.say('Hello World!');
  return callback(null, twiml);

};
