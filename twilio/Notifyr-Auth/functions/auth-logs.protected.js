const assets = Runtime.getAssets();
const {NotifyrAuthService} = require(assets["/service.private.js"].path);

exports.handler = async function(context, event, callback) {
  const service = new NotifyrAuthService(context);
  console.log(event);
  // return callback(null,{})
}