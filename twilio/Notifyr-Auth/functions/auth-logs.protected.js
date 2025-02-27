const assets = Runtime.getAssets();
const {  NotifyrAuthService } = require(assets["/service.js"].path);


exports.handler = async function (context, event, callback) {
  const service = new NotifyrAuthService(context,event);
  
    // TODO first get the type message or voice call
    // TODO set the url
    // TODO  parse in a understable object
    // send to the services
  
  console.log(event);
  console.log(context);
  console.log(callback);
  // return callback(null,{})
};
