# Secrets

Most of the projects have configurations that are not meant to be shared nor pushed to any repository but are required in order to let our apps work. API Keys, database passwords or encryption keys could be considered good examples.

There are two ways to be able to, without exposing sensitive information, to let our apps to use them. **Keep in mind that both alternatives can be used at the same time. See [the comparison chart](#comparison)**.

_Note: It's in or roadmap to provide better tools to tackle this issue like Hashicorp's Vault. We actually been running an instance of Vault just to share team secrets for months._

## Gitlab Variables

This alternative is a little bit more cumbersome and error prone as it requires more steps and files but it should be considered the default way to use secrets in our apps.

![secrets](secrets.png)

Steps to make it work:

1. Access to Gitlab Variables config section `Settings > CI / CD > Variables`
2. Add as many as variables as you need to:
   - Naming standard is `$VARIABLENAME_$ENV`, for example, `MY_API_KEY_PROD`, `MY_API_KEY_STAGING`, `MY_API_KEY_UAT`.
   - Check the `Masked` option as true but leave `Protected` unchecked (protected will prevent using them from a non protected branch like `release/x.x.x`).
3. Configure each `$environment/docker/.env` file to re-export the variables you have defined, for example, `production/docker/.env` should have the following line:
   - `export MY_API_KEY = $MY_API_KEY_PROD`
   - We need to re-export variables as our app will probably use the same variable name for different environments but we will potentially have `_PROD`, `_STAGING` and `_UAT` ones.
4. Edit your `docker-compose-base.yml` file in order to make this environment variables visible to the container. To do so:
   - Add an `environment` section under the service that requires this variables
   - Configure the variables, `- MY_API_KEY=${MY_API_KEY}`
5. The app will have access to the keys as environment variables.

For a NodeJs app you will be able to access them using `process.env`, for example:

```
const myApiKey = process.env.MY_API_KEY
```

In spring you can use them in the `application.properties` file using `${}` notation:

```
# application.properties or application-$environment.properties

service.apiKey = ${MY_API_KEY}
```

Examples of this use can be found when configuring backend database credentials in the [examples](../examples) folder.

## Server Config Files

This is the most straight forward alternative. Steps:

1. Create as many files with secret configurations as you want to and put them in `ops/$environment/configs` directory.
2. Execute `./ops --config-server $environment` to automatically upload them to the server (you can run this step as many times as you want to).
3. Let your app containers to read those files by mounting `/configs` host folder as a volume. To do so, just add a volumes section in your `docker-compose-base.yml` file.
4. Then you can use the mapped files either by reading them or just loading them as environment variables (for example using `source $FILE` where the file contains `export` sentences).

**Keep in mind this config files should never be pushed to the repository so if you need someone else to get access to them, you will need to provide a way to security share them with the rest of the team**

## Comparison

| Use case                                                         | Gitlab Variables                                   | Server Config Files                                         |
| ---------------------------------------------------------------- | -------------------------------------------------- | ----------------------------------------------------------- |
| DB credentials                                                   | **Preferred**                                      | More cumbersome                                             |
| API keys                                                         | **Preferred**. Easier to share within team members | More complex as a secure way to share them needs to be used |
| Config files with static configured keys (i.e. `prometheus.yml`) | May not be possible to use it                      | **Preferred**                                               |
