// Pass the number of digits i need to wait before sending
const assets = Runtime.getAssets();
const { NotifyrAuthService } = require(assets["/service.js"].path);

exports.handler = async function (context, event, callback) {

    const service = new NotifyrAuthService(context, event);
    

};
  
