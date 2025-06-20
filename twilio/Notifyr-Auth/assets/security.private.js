const crypto = require('crypto');

// Generate salt
function generateSalt(length = 64) {
    return crypto.randomBytes(length);
}

function hashValueWithSalt(value, key, salt) {
    const hmac = crypto.createHmac('sha256', Buffer.from(key, 'utf-8'));
    hmac.update(Buffer.from(value, 'utf-8'));
    hmac.update(salt);
    return hmac.digest('hex');
}

/**
 * The function `storePassword` generates a salt, hashes a password with a key and the salt, and
 * returns the hashed password and the salt in base64 format.
 * 
 * @param {string} password - The `password` parameter is the user's password that needs to be securely stored.
 * @param {string} key - The `key` parameter in the `storePassword` function is used as a secret key to hash the
 * password along with a generated salt. 
 * @returns The `storePassword` function is returning an object with two properties:
 * 1. `hashedPassword`: The hashed password encoded in base64 format.
 * 2. `salt`: The salt used for hashing the password, also encoded in base64 format.
 */
function storePassword(password, key) {
    const salt = generateSalt();
    const hashedPassword = hashValueWithSalt(password, key, salt);
    const hashedPasswordBase64 = Buffer.from(hashedPassword).toString('base64');
    return {
        hashedPassword: hashedPasswordBase64,
        salt: salt.toString('base64')
    };
}

/**
* Creates a Twilio-style signature for a given request
* @param {string} authToken - Your Twilio Auth Token
* @param {string} url - The full request URL (no query string)
* @param {object} params - POST parameters as key-value pairs
* @returns {string} - The base64-encoded signature
*/
function generateTwilioSignature(authToken, url, params = {}) {
    const sortedKeys = Object.keys(params).sort();
    let data = url;

    for (let key of sortedKeys) {
        data += key + params[key];
    }

    const signature = crypto
        .createHmac('sha1', authToken)
        .update(data)
        .digest('base64');

    return signature;
}

module.exports={
    storePassword,
    generateTwilioSignature
}