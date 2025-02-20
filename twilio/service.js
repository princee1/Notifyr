
const API_KEY_HEADER = 'X-API-KEY';
const AUTH_CONTEXT_KEY = 'auth-key';	
const API_CONTEXT_KEY = 'api-key';	

const axios = require('axios');
const jwt = require('jsonwebtoken');

const set_bearer_token = (val) => "Bearer " + val;

