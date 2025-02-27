const axios = require("axios");
const set_auth_token = (token) => "Bearer " + token;

const assets = Runtime.getAssets();
const { Contact } = require(assets["/contacts.js"].path);

class NotifyrAuthService {

  constructor(context,event) {
    this.context = context;
    this.event = event;
    this.client = this.context.getTwilioClient();
    this.mode = this.context.MODE;
    this.type = this.event.type??null
    this.setUrl();
    this.headers = {
      "x-api-key": this.context.API_KEY,
      "Authorization": set_auth_token(this.context.AUTH_KEY),
    };

    //this.relayPath = this.event.path
  }

  async authenticate(phoneNumber, codeEntered) {
    const url = `${this.url}/contacts`;
    const response = await axios.get(url, {
      headers: this.headers,
    });

    response.data;
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

  async pingNotifyr(){

  }

  async queryUserData(){

  }

  async sendDtmf(){

  }

  async sendLogStatus(body) {
    const result = axios
  }

}

module.exports = {
  NotifyrAuthService,
};
