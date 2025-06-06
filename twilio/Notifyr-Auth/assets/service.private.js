const axios = require("axios");

const set_auth_token = (token) => "Bearer " + token;
const set_http_basic_auth = (username, password) => { };


const assets = Runtime.getAssets();
const { Contact } = require(assets["/contacts.js"].path);
const { generateTwilioSignature } = require(assets["/security.js"].path)

class NotifyrAuthService {

  constructor(context, event) {
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

    this.notifyr_authToken = this.context.AUTH_KEY
    this.notifyr_refreshToken = this.context.REFRESH_KEY;

    this.twilio_auth_token=this.context.AUTH_TOKEN;

    this.headers = {
      "Authorization": set_auth_token(this.notifyr_authToken ?? 'Test'),
    };
  }

  setUrl() {
    switch (this.mode) {
      case 'prod':
        this.url = this.context.URL_PROD;
        break;

      case 'test':
        this.url = this.context.URL_TEST;
        break;

      case 'dev':
        this.url = this.context.URL_DEV;
        break;
      default:
        this.url = this.context.URL_TEST;
        break;
    };

  }

  async sendLogStatus(body, url,params={}) {
    const status_url = this.url + url
    const signature = generateTwilioSignature(this.twilio_auth_token, status_url)
    const headers = {
      //'X-Twilio-Signature': signature
    }
    try {
      const result = await axios.post(status_url, { ...body }, {
        headers,
        params,

      });
    } catch (error) {
      console.error(error.response)
    }
    
  }

  async login() {
    const url = null
    const result = await axios.post(url)
    const tokens = result['data']['tokens']

  }

  async sendGatherResult(body,params={}) {
    try {

      const url = `${this.url}/twilio/call/incoming/gather-result/`;
      const signature = generateTwilioSignature(this.twilio_auth_token, url)
      const headers = {
        //'X-Twilio-Signature': signature
      }
      const response = await axios.post(url, body,{
        headers,
        params,
      });
      const { message } = response.data;
      console.log(response)

      return {
        message,
        status_code: response.status,
      };
    } catch (error) {

      return {
        message: error.response?.data?.message || 'An unexpected error occurred',
        status_code: error.response?.status || 500,
      };
    }
  }

  async refresh() {

  }

}

module.exports = {
  NotifyrAuthService,
};
