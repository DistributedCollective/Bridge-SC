# Federator

Presents the event and necesary information to validate it on the other network
The federator is an off-chain process which performs voting actions to validate transactions between a Mainchain (source) and a Sidechain (target) network. These transactions are obtained from the Bridge contract on the Mainchain using event logs and voted in the Sidechain through a Federation contract. Once all required signers (federators) vote for a transaction the Federation contract starts the process to release the funds on the Sidechain.
The federators will be the owners of the contracts willing to allow to cross their tokens, and by doing so staking they reputation.

## Config

Go to /federator/config copy `config.sample.js` file and rename it to `config.js` set mainchain and sidechain to point to the json files of the networks you are suing, for example rsktestnet-kovan.json and kovan.json, `make sure to set the host parameter of those files`. Create the file `federator.key` inside the config folder, and add the private key of the member of the Federation contract. The members of the federation are controled by the MultiSig contract, same that is owner of the Bridge and AllowedTokens contracts.
The minimumPeerAmount field affect the number of p2p node a federator needs to be connected to in order to start fetching the bridge's events. It also affects the number of signatures required before sending the token release transaction.
The port field needs to be updated if you run multiple federators on the same machine.
The signaturesTTL field sets the time during which the signatures produced by the federation is usable.
Fill the peers field with the ip, port and address of each federator who want to connect to and accept in your network.

## Usage

Run `npm install` to install the dependencies, make sure you followed the previous config step. Then to start the service run `npm start` which will start a single federator that listen to both networks. Check the logs to see that everything is working properly.

## Test

To run an integration test use `npm run integrationTest`. The integration test will use a preconfigured private key (from `config.js`) which is assumed to be the only member of the Federation contract.
In order to test with multiple federators, ensure they're added as members of the Federation contract and pass their private keys as a comma separated string for both chains as arguments of the integration test script. For instance:
`node integrationTest.js "privKeyM1, privKeyM2, privKeyMN" "privKeyS1, privKeyS2, privKeySN"`

## Run a Federator

### config

To run the federator using Docker first, go to the /federator/config folder and rename `config.sample.js` to `config.js`. In that file you will dedcide the networks the federate must be listening, for example for the bridge in testnet a federator config.js will look like

```json
module.exports = {
    mainchain: require('./rsktestnet-kovan.json'),
    sidechain: require('./kovan.json'),
    runEvery: 1, // In minutes,
    confirmations: 10,// Number of blocks before processing it,
    privateKey: require('federator.key'),
    storagePath: './db'
}
```

where the mainchain for example is rsktestnet and the sidechain is kovan, the .json files are in the /federator/config folder and includes the addresses of the contracts in that network and the block number when they where deployed.
The order of sidechain and mainchain is not important is just which one is going to be checked first, as federators are bi directionals.
Inside the .json files there is also the host to that network, for example this is the rsktestnet-kovan.json

```json
{
    "bridge": "0x684a8a976635fb7ad74a0134ace990a6a0fcce84",
    "federation": "0x36c893a955399cf15a4a2fbef04c0e06d4d9b379",
    "testToken": "0x5d248f520b023acb815edecd5000b98ef84cbf1b",
    "multisig": "0x88f6b2bc66f4c31a3669b9b1359524abf79cfc4a",
    "allowTokens": "0x952b706a9ab5fd2d3b36205648ed7852676afbe7",
    "host": "<YOUR HOST URL AND PORT>",
    "fromBlock": 434075
}
```

You need to change `"<YOUR NODE HOST AND RPC PORT>"` for the url of your node for that network and the json rpc port. `Remember to do it for both networks`.
Also you need to create a `federators.key` file with the federator private in it.

### Latest block

The federator will use the block number in `./federator/db/latestBlock.txt` for the main chain and `./federator/db/side-fed/latestBlock.txt` for the side chain as starting point. This is important as the federator will increase the number each time it successfully polls for blocks, and indicates the last block run.
If this files don't exist, the program will automatically create them using the `config.fromBlock` number. This is ok, but the default config number is the creation of the contract and may be too far from the current block number, having a negative impact in performance even preventing the program from running. This is way it should be as closest as the current block number minus the confirmations blocks as posible.

### Docker image

Once you have changed this configurations create the **docker image from the root folder** using.
`docker build . -t fed-tokenbridge`

Then run :

```sh
docker run --rm \
    --network host \
    -v $PWD/federator/config:/app/federator/config \
    -v $PWD/federator/db:/app/federator/db \
    --name=fed-tokenbridge \
    fed-tokenbridge:latest
```

to start the image.


## ETH gas quote and fee behavior

The gas oracle uses Etherscan V2 with Ethereum chain ID 1 and the configured
read API key. A key matching a 64-hex signing-scalar shape (optional `0x`) is
refused before a request; a signing key must never be used as a read API key.
Quotes must be finite positive decimal Gwei. Requests have an
absolute five-second deadline and a 128 KiB body limit; HTTP failures and
malformed responses expose no provider body, URL or credential in errors.

ETH transaction construction uses the latest RPC block's positive base fee,
with exact integer Wei arithmetic and the existing 2 Gwei priority fee and 30%
buffer. Fractional Gwei is preserved. Missing, invalid or stale block evidence
fails before a transaction can be constructed. Cached or zero oracle globals
are never a fee fallback. High-fee waits reread the latest block and are bounded
by the configured retry count.

The five-second block-read deadline bounds the builder's wait. It does not
cancel a pending request within the Web3 provider, so this is not a general
transport cancellation or timeout change for the application. An oracle read
failure is distinct from an authentication-stream process crash.

An isolated fee/oracle regression runner uses controlled transport and module
boundaries without network calls, signing or broadcasting:

```sh
node ../../tools/tests/gas_fee_regression.cjs
```


## Transport authentication bindings

Authentication requires both transport public keys to be 32-byte Buffers.
An unavailable or invalid binding rejects authentication and force-closes that
connection. The client initial-auth boundary catches only the typed binding
failure; the server uses its existing asynchronous error boundary. Other
provider errors keep their existing behavior. Signature validation, public
binding order and trusted-address checks remain required; empty keys and an
authentication bypass are never used.

The isolated binding regression runner exercises the published ataraxia peer
methods with controlled transport dependencies. It verifies both failure
boundaries, immediate connection destruction and valid client/server tags:

```sh
node ../../tools/tests/auth_binding_regression.cjs
```

This test requires the ataraxia packages to be installed. A separately provided
published-source fixture directory can instead be selected with
`ATARAXIA_REVIEW_SOURCE_DIR`. Native encrypted-stream and full application
integration still need the target runtime; passing the isolated test alone does
not establish successful peer admission on a deployed node.

## Source repair overlay image

`../Dockerfile.repair-overlay` inherits a reviewed, existing compatible
application image identified by **tag and immutable digest**. It replaces only
four gas files and the authentication-binding vendor file, with UID/GID 1000.
It does not install packages or change Node, native libraries, application
configuration, database mounts or the inherited startup command.

Before use, inspect the base with the dependency diagnostic's versions report
and validate its source hashes and dependency APIs against the intended repair.
An arbitrary or unknown application base is unsafe. The overlay build requires
`BASE_IMAGE`, a full `REPAIR_REVISION`, and two JSON source-hash maps:
`EXPECTED_BASE_SOURCE_SHA256` and `EXPECTED_REPAIR_SOURCE_SHA256`. Both maps must
contain all five fixed source paths listed in the Dockerfile. Missing/mismatched
hashes, unsupported transport APIs or native import failure abort the build.
The base digest and reviewed repair revision are recorded as image labels.

Prepare a sanitized build context from the full reviewed commit first:

```sh
python3 tools/prepare_federator_overlay.py --repo "$HOME/Bridge-SC" \
  --revision "$REVIEWED_REVISION" --output "$HOME/federator-repair-context"
```

The output directory must be new. This tool reads only the five fixed public
source blobs, the overlay Dockerfile and its ignore file from that immutable
Git commit. It emits the repair hash map and a private directory containing
exactly those seven files. Working configuration, key files, API environment
files, `.git` and database contents are never scanned or copied.

Use the returned directory as the Docker context and select its overlay
Dockerfile explicitly. Do not send an operator checkout as a build context.
A nested module `.dockerignore` does not govern the root context; the
Dockerfile-specific deny-default allowlist requires builder support. The
sanitized context is the portable default and remains safe when that support
is unavailable. See [Docker build-context documentation](https://docs.docker.com/build/concepts/context/#dockerignore-files).

Use an already available reviewed base and disable pulls and build-step network
access. Building, verifying the target Node/native runtime, publishing and
activating the repaired image are separate operator steps; this repository
change performs none of them.
