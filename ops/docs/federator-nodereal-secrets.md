# Federator NodeReal Secrets

This runbook describes how to configure private NodeReal RPC keys for federator nodes without committing keys to git.

The federator configs use these environment variables:

- `NODEREAL_BSC_FEDERATOR_API`
- `NODEREAL_ETH_FEDERATOR_API`

The public JSON files contain placeholders such as:

```json
"host": "https://bsc-mainnet.nodereal.io/v1/${NODEREAL_BSC_FEDERATOR_API}"
```

At runtime, `config.js` expands the placeholder from the environment. If the required variable is missing, the federator fails fast instead of falling back to the public overloaded endpoint.

## Recommended Emergency Setup: Local `.env`

Docker Compose automatically reads a `.env` file from the same directory where `docker-compose-prod.yml` is executed.

On each federator node:

```sh
cd /home/ubuntu/Bridge-SC
```

Create or update `.env`:

```sh
cat > .env <<'EOF'
NODEREAL_BSC_FEDERATOR_API=<BSC_NODE_REAL_API_KEY>
NODEREAL_ETH_FEDERATOR_API=<ETH_NODE_REAL_API_KEY>
EOF
```

Lock down permissions:

```sh
chmod 600 .env
```

Make sure `.env` is not committed:

```sh
git status --short .env
```

If it appears in git status, add it to the local exclude file:

```sh
echo .env >> .git/info/exclude
```

## Restart BSC Federator

Restart only the federator container:

```sh
cd /home/ubuntu/Bridge-SC
export FED_ENV=mainnet-BSC-RSK
docker-compose -f docker-compose-prod.yml up -d --force-recreate federation
```

Do not use `start.sh` for a simple hot restart unless you intentionally want its full reset behavior. It calls `reset.sh`, which deletes federator DB progress and performs git hard resets.

## Restart ETH Federator

```sh
cd /home/ubuntu/Bridge-SC
export FED_ENV=mainnet-ETH-RSK
docker-compose -f docker-compose-prod.yml up -d --force-recreate federation
```

## Verify The Container Has The Variables

Do not print the actual values. Check only whether they are present:

```sh
docker-compose -f docker-compose-prod.yml exec federation sh -lc \
  'test -n "$NODEREAL_BSC_FEDERATOR_API" && echo BSC key present || true'
```

```sh
docker-compose -f docker-compose-prod.yml exec federation sh -lc \
  'test -n "$NODEREAL_ETH_FEDERATOR_API" && echo ETH key present || true'
```

For a BSC-only node, only the BSC variable needs to be present. For an ETH-only node, only the ETH variable needs to be present.

## Verify RPC Access From The Host

BSC:

```sh
. ./.env

curl -sS "https://bsc-mainnet.nodereal.io/v1/$NODEREAL_BSC_FEDERATOR_API" \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' | jq

unset NODEREAL_BSC_FEDERATOR_API NODEREAL_ETH_FEDERATOR_API
```

Expected BSC mainnet result:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": "0x38"
}
```

ETH:

```sh
. ./.env

curl -sS "https://eth-mainnet.nodereal.io/v1/$NODEREAL_ETH_FEDERATOR_API" \
  -H 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"eth_chainId","params":[]}' | jq

unset NODEREAL_BSC_FEDERATOR_API NODEREAL_ETH_FEDERATOR_API
```

Expected ETH mainnet result:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": "0x1"
}
```

## Check Federator Logs

```sh
docker-compose -f docker-compose-prod.yml logs --tail=100 -f federation
```

The app currently logs the sidechain host as `ETH Host` even when it is BSC. The URL should show the NodeReal domain, not `bsc.sovryn.app` or `eth.sovryn.app`.

## Optional Hardening: AWS Secrets Manager

AWS Secrets Manager is useful for long-term operations, auditability, and controlled rotation. It is not required for emergency recovery.

`start.sh` can load these secrets from AWS Secrets Manager if the environment variables are not already set:

- Secret name: `NODEREAL_BSC_FEDERATOR_API`
- Secret value: raw BSC NodeReal API key
- Secret name: `NODEREAL_ETH_FEDERATOR_API`
- Secret value: raw ETH NodeReal API key

Each AWS account that runs federator nodes must create its own secrets and IAM permissions.

Create secrets:

```sh
aws secretsmanager create-secret \
  --region us-east-2 \
  --name NODEREAL_BSC_FEDERATOR_API \
  --secret-string '<BSC_NODE_REAL_API_KEY>'
```

```sh
aws secretsmanager create-secret \
  --region us-east-2 \
  --name NODEREAL_ETH_FEDERATOR_API \
  --secret-string '<ETH_NODE_REAL_API_KEY>'
```

If the secret already exists, update it:

```sh
aws secretsmanager put-secret-value \
  --region us-east-2 \
  --secret-id NODEREAL_BSC_FEDERATOR_API \
  --secret-string '<BSC_NODE_REAL_API_KEY>'
```

```sh
aws secretsmanager put-secret-value \
  --region us-east-2 \
  --secret-id NODEREAL_ETH_FEDERATOR_API \
  --secret-string '<ETH_NODE_REAL_API_KEY>'
```

Attach this inline policy to the federator EC2 instance role. Replace `<ACCOUNT_ID>`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadFederatorNodeRealSecrets",
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": [
        "arn:aws:secretsmanager:us-east-2:<ACCOUNT_ID>:secret:NODEREAL_BSC_FEDERATOR_API-*",
        "arn:aws:secretsmanager:us-east-2:<ACCOUNT_ID>:secret:NODEREAL_ETH_FEDERATOR_API-*"
      ]
    }
  ]
}
```

The trailing `-*` is required because Secrets Manager appends a random suffix to secret ARNs.

Verify from the instance:

```sh
aws secretsmanager get-secret-value \
  --region us-east-2 \
  --secret-id NODEREAL_BSC_FEDERATOR_API \
  --query SecretString \
  --output text >/dev/null
```

```sh
aws secretsmanager get-secret-value \
  --region us-east-2 \
  --secret-id NODEREAL_ETH_FEDERATOR_API \
  --query SecretString \
  --output text >/dev/null
```

Both commands should exit with status `0`.

## Operational Notes

- Keep `.env` local to each federator node and never commit it.
- Use `chmod 600 .env`.
- Revoke the old leaked/public NodeReal key after federators are confirmed healthy on the new keys.
- Monitor NodeReal CU usage per key after rollout.
- Restrict NodeReal keys by source IP if NodeReal supports it for the account/plan.
- Longer term, protect `https://bsc.sovryn.app/mainnet` at the proxy layer with rate limits, auth, IP allowlists, or a capped public fallback.
