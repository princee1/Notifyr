const crypto = require('crypto');

// Generate salt
function generateSalt(length = 64) {
    return crypto.randomBytes(length);
}

// Hash value with salt using HMAC-SHA256
function hashValueWithSalt(value, key, salt) {
    const hmac = crypto.createHmac('sha256', Buffer.from(key, 'utf-8'));
    hmac.update(Buffer.from(value, 'utf-8'));
    hmac.update(salt);
    return hmac.digest('hex');
}

// Store password: returns base64 hashed password and the salt
function storePassword(password, key) {
    const salt = generateSalt();
    const hashedPassword = hashValueWithSalt(password, key, salt);
    const hashedPasswordBase64 = Buffer.from(hashedPassword).toString('base64');
    return {
        hashedPassword: hashedPasswordBase64,
        salt: salt.toString('base64')
    };
}


module.exports={
    storePassword
}