const axios = require("axios");
const set_auth_token = (token) => "Bearer " + token;

const { Contact } = require(assets["/contacts.private.js"].path);

class NotifyrAuthService {
  constructor(context,event) {
    this.context = context;
    this.event = event;
    this.client = this.context.getTwilioClient();
    this.mode = this.context.MODE;
    this.url =
      this.mode === "prod" ? this.context.URL_PROD : this.context.URL_TEST;
    this.headers = {
      "API-KEY": this.context.API_KEY,
      Authorization: set_auth_token(this.context.AUTH_KEY),
    };

    this.relayPath = this.event.path
  }

  async authenticate(phoneNumber, codeEntered) {
    const url = `${this.url}/contacts`;
    const response = await axios.get(url, {
      headers: this.headers,
    });

    response.data;
  }

  async query_server() {}

  async log_status() {}
}

module.exports = {
  NotifyrAuthService,
};
