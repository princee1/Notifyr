const axios = require("axios");

const set_auth_token = (token) => "Bearer " + token;
const set_http_basic_auth = (username,password) => {};


const assets = Runtime.getAssets();
const { Contact } = require(assets["/contacts.js"].path);

class NotifyrAuthService {

  constructor(context,event) {
    this.context = context;
    this.event = event;
    this.mode = this.context.MODE;
    this.client = this.context.getTwilioClient();
    this.setService();

    //this.relayPath = this.event.path
  }

  setService() {
    this.type = this.event.type ?? null;
    this.setUrl();

    this.authToken = this.context.AUTH_KEY;
    this.refreshToken = this.context.REFRESH_KEY;
    
    this.headers = {
      "Authorization": set_auth_token(this.context.AUTH_KEY),
    };
  }

  setUrl(){
    switch (this.mode) {
      case 'prod':
        this.url = this.context.URL_PROD;
        break;
      
      case 'test':
        this.url =  this.context.URL_TEST;
        break;
      
      case 'dev':
        this.url = this.context.URL_DEV;
        break;
      default:
        this.url =  this.context.URL_TEST;
        break;
    };
    
  }

  async sendLogStatus(body,url) {
    const result = await axios.post(url,{headers:this.headers,body});
    console.log("Result",result.status);
    console.log("Result",result.data);
  }

  async login(){
    const url = null
    const result = await axios.post(url)
    const tokens = result['data']['tokens']

  }

  async refresh(){

  }

}

module.exports = {
  NotifyrAuthService,
};
