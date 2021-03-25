// Use this code snippet in your app.
// If you need more information about configurations or implementing the sample code, visit the AWS docs:
// https://aws.amazon.com/developers/getting-started/nodejs/

const AWS = require("aws-sdk");

// // Load the AWS SDK

const region = "us-east-2";
const secretName = "federator";

const secretsManager = new AWS.SecretsManager({
  region,
});

readSecret = async (event, context) => {
  try {
    const data = await secretsManager
      .getSecretValue({
        SecretId: secretName,
      })
      .promise();

    if (data) {
      if (data.SecretString) {
        const secret = data.SecretString;
        console.log(secret);
        return secret;
      }

      const binarySecretData = data.SecretBinary;
      return r;
    }
  } catch (error) {
    console.log("Error retrieving secrets");
    console.log(error);
  }
};
readSecret();
