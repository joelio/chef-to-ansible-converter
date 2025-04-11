const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

exports.handler = async function(event, context) {
  // Check if this is a POST request
  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      body: JSON.stringify({ error: 'Method Not Allowed' })
    };
  }

  try {
    // Parse the request body
    const body = JSON.parse(event.body);
    const { repoUrl } = body;

    if (!repoUrl) {
      return {
        statusCode: 400,
        body: JSON.stringify({ error: 'Repository URL is required' })
      };
    }

    // Create a unique ID for this conversion
    const conversionId = Date.now().toString();
    
    // Set up environment variables
    const env = {
      ...process.env,
      ANTHROPIC_API_KEY: process.env.ANTHROPIC_API_KEY
    };

    // Return a response immediately to avoid timeout
    return {
      statusCode: 200,
      body: JSON.stringify({
        message: 'Conversion started',
        conversionId: conversionId,
        status: 'processing'
      })
    };
  } catch (error) {
    console.error('Error:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Internal Server Error' })
    };
  }
};
