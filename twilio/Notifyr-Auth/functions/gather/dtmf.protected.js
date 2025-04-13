// Pass the number of digits i need to wait before sending
const assets = Runtime.getAssets();

const { NotifyrAuthService } = require(assets["/service.js"].path);
const { Contact } = require(assets["/contacts.js"].path);

class DTMFConfig {

    constructor(event) {
        this.event = event;
    }

    deconstructQuery() {
        this.otp = this.event.otp ?? null;

        if (this.event.otp === null) {
            throw new Error("Missing OTP in the event object.");
        }
        this.otp.trim()

        this.type = this.event.type ?? null;

        this.return_url = this.event.return_url ?? null;
        if (this.return_url === null) {
            throw new Error("Missing return_url in the event object.");
        }

        this.max_digits = this.event.max_digits ?? null;

        this.subject_id = this.event.subject_id ?? null;
        this.request_id = this.event.request_id ?? null;
        this.contact_id = this.event.contact ?? null;

        this.digits = this.event.Digits;
        this.CallSid = this.event.CallSid;
        this.To = this.event.To;
        this.Direction = this.event.Direction;

        this.hangup = this.event.hangup;
    }

    verify_digits() {
        if (this.digits === null) {
            throw new Error("Missing digits in the event object.");
        }
        if (this.digits.length !== this.max_digits) {
            throw new Error("Digits length does not match max_digits.");
        }
        if (this.digits !== this.otp) {
            throw new Error("Digits do not match OTP.");
        }

        return true;
    }

    async verify_contact_dtmf_code(contact) {

    }

}

exports.handler = async function (context, event, callback) {

    console.log(event);

    const service = new NotifyrAuthService(context, event);
    const twiml = new Twilio.twiml.VoiceResponse();
    const dtmf = new DTMFConfig(event);

    const contact = new Contact(service.url);

    let _deconstruct_error = true;
    let _error_message;

    try {
        dtmf.deconstructQuery();
        _deconstruct_error = false;
    } catch (error) {
        _error_message = error.message;
        console.error("Error deconstructing query:", error.message);
        twiml.say("There was an error processing your request. Please try again later.");
    }

    if (_deconstruct_error) {

        try {
            if (dtmf.contact_id === null) {
                dtmf.verify_digits();
            }
            else {
                dtmf.verify_contact_dtmf_code(contact)
            }
        } catch (error) {
            _error_message = error.message;
            console.error("Error verifying digits:", error.message);
            twiml.say("The digits you entered are incorrect. Please try again.");
        }
    }


    if (dtmf.hangup) {
        twiml.say("Goodbye!");
        twiml.hangup();
    }

    return callback(null, twiml);
};

