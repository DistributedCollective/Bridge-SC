# RECOMMENDED OPERATIONS FOR NEW ASSETS

## Overview

Instructions for federators to safely add a new asset to the Sovryn Token Bridge.  

**NOTE**: Procedures in this manual are based on packages existing by the time the projects were developed, like Truffle and Web3.js. More efficient packages can be used to improve the process, like hardhat or foundry, but it requires independet and local installations of them and the proper configuration of the environment.

**Repositories:** Primarily [bridge-private](https://github.com/DistributedCollective/bridge-private) for federator operations. Bridge Smart Contracts at [Bridge-SC](https://github.com/DistributedCollective/Bridge-SC).

**Contract Addresses:** [Sovryn Contracts Spreadsheet](https://docs.google.com/spreadsheets/d/1SSqQJ4HNrIo8jRghKBa4ao_aAt4TJxP7jafRV-l0YcM/edit?gid=205430603#gid=205430603)

**⚠️ CRITICAL:** Coordinate via secure channel (Keybase). DO NOT share transaction IDs publicly.

---

## Prerequisites

1. SSH access to your federator node
2. Federator private key (AWS Secrets Manager)
3. Keybase access for coordination
4. Contract addresses (see spreadsheet above)

---

## Process: 5 Steps

1. **Pause federator nodes** - Stop automatic operations
2. **Deploy mirror token** - Via MultiSig (Bridge Contracts repo)
3. **First cross-bridge transaction** - Trusted user initiates
4. **Manual voting** - Federators vote on first transaction
5. **Resume operations** - Restart automatic processing

---

## STEP 1: Pause Federator Nodes from [bridge-private](https://github.com/DistributedCollective/bridge-private)  

### Who Initiates?

Designated coordinator announces via Keybase. All federators execute on their nodes.

### How to Pause

SSH to your node and run:

```bash
./stop.sh
```

**Verify:**  

```bash
docker ps  # Should show no running federator containers
```

**Confirm in Keybase:**  

```
✅ [Your Name] - Node paused. Ready for new asset deployment.
```

**Wait for all federators to confirm before proceeding.**  

---  

## STEP 2: Deploy Mirror Token via MultiSig

**Repository:** [Bridge-SC](https://github.com/DistributedCollective/Bridge-SC)

### Overview

Mirror tokens are created automatically during the first cross-bridge transaction. After creation, MultiSig owners must allow the token and set fee parameters.

### Process

#### 2.1 First Transaction Creates Mirror Token

When a new token crosses the bridge for the first time, the Bridge contract automatically calls [`_createSideToken()`](https://github.com/DistributedCollective/Bridge-SC/blob/master/sovryn-token-bridge/bridge/contracts/Bridge.sol#L336-L352):

- Creates new side token via SideTokenFactory
- Applies prefix/suffix to token symbol (e.g., "e" for Ethereum tokens, "bs" for BSC tokens)
- Registers mapping between original and side token
- Emits `NewSideToken` event

**You don't deploy the token manually.** It happens during Step 3 (first cross).

#### 2.2 Allow Token on Bridge

**After** mirror token is created, MultiSig owners must allow it on the destination chain.

**Script:** [`scripts/allowToken.js`](https://github.com/DistributedCollective/Bridge-SC/blob/master/sovryn-token-bridge/bridge/scripts/allowToken.js)

**Usage:**
```bash
cd sovryn-token-bridge/bridge
npx truffle exec ./scripts/allowToken.js --network <NETWORK> <TOKEN_ADDRESS>
```

**Networks:**
- `mainnet` - Ethereum mainnet
- `bmainnet` - BSC mainnet  
- `rskmainnet` - RSK mainnet
- `sepolia` - Ethereum testnet
- `btestnet` - BSC testnet
- `rsktestnet` - RSK testnet

**Example:**
```bash
npx truffle exec ./scripts/allowToken.js --network rskmainnet 0x1234...abcd
```

**What it does:**
1. Connects to AllowTokens contract
2. Encodes `addAllowedToken(tokenAddress)`
3. Submits MultiSig transaction
4. Returns transaction ID for signing

**Keybase coordination:**
```
🔹 Action: Allow token on RSK
🔹 Script: allowToken.js
🔹 Network: rskmainnet
🔹 Token: 0x[SIDE_TOKEN_ADDRESS]
🔹 MultiSig TX ID: [ID]
```

Each MultiSig owner must sign the transaction until required threshold is met.

#### 2.3 Set Fee and Min Amount

**Script:** [`scripts/setFeeAndMinPerToken.js`](https://github.com/DistributedCollective/Bridge-SC/blob/master/sovryn-token-bridge/bridge/scripts/setFeeAndMinPerToken.js)

**Usage:**
```bash
npx truffle exec ./scripts/setFeeAndMinPerToken.js --network <NETWORK> <TOKEN_ADDRESS> <FEE> <MIN_AMOUNT>
```

**Parameters:**
- `TOKEN_ADDRESS` - Side token address (from Step 2.2)
- `FEE` - Fee in token's smallest unit (e.g., 1000000 for 1 USDC with 6 decimals)
- `MIN_AMOUNT` - Minimum transfer amount in smallest unit

**Example:**
```bash
# For a token with 18 decimals, 0.01 token min, 0.001 token fee
npx truffle exec ./scripts/setFeeAndMinPerToken.js --network rskmainnet \
  0x1234...abcd \
  1000000000000000 \
  10000000000000000
```

**Keybase coordination:**
```
🔹 Action: Set fee & min for new token
🔹 Network: rskmainnet
🔹 Token: 0x[SIDE_TOKEN_ADDRESS]
🔹 Fee: [FEE]
🔹 Min: [MIN_AMOUNT]
🔹 MultiSig TX ID: [ID]
```

#### 2.4 Verify Configuration

**Option A: Truffle Console**
```bash
cd sovryn-token-bridge/bridge
npx truffle console --network rskmainnet
```

```javascript
const AllowTokens = artifacts.require("AllowTokens");
const Bridge = artifacts.require("Bridge");

const bridge = await Bridge.deployed();
const allowTokensAddr = await bridge.allowTokens();
const allowTokens = await AllowTokens.at(allowTokensAddr);

// Check if token is allowed
await allowTokens.isTokenAllowed("0x[TOKEN_ADDRESS]");
// Should return: true

// Check fee
await allowTokens.getFeePerToken("0x[TOKEN_ADDRESS]");
// Should return: [FEE]

// Check min amount
await allowTokens.getMinPerToken("0x[TOKEN_ADDRESS]");
// Should return: [MIN_AMOUNT]
```

**Option B: Block Explorer**

Navigate to AllowTokens contract on RSK Explorer, call read functions:
- `isTokenAllowed(tokenAddress)` → should be `true`
- `getFeePerToken(tokenAddress)` → should match configured fee
- `getMinPerToken(tokenAddress)` → should match configured min

### MultiSig Contract Addresses

**Mainnet (ETH-RSK):**
- Ethereum: `0x062c74f9d27b1178bb76186c1756128ccb3ccd2e`
- RSK: `0xb64322e10b5ae1be121b8bb0dead560c53d9dbc3`

**Mainnet (BSC-RSK):**
- BSC: `0xec3fabc3517e64e07669dd1d2d673f466f93a328`
- RSK: `0xee9ea57555d9533d71f6f77e0e480961f068a6c5`

See [contract spreadsheet](https://docs.google.com/spreadsheets/d/1SSqQJ4HNrIo8jRghKBa4ao_aAt4TJxP7jafRV-l0YcM/edit?gid=205430603#gid=205430603) for complete list.

### Step 2 Completion

**Confirm in Keybase:**
```
✅ [Your Name] - Mirror token deployed and configured
📝 Side token: 0x[ADDRESS]
📝 Token allowed: ✅
📝 Fee set: ✅
📝 Min amount set: ✅
```

---

## STEP 3: First Cross-Bridge Transaction

**Repository:** [Bridge-SC](https://github.com/DistributedCollective/Bridge-SC)

### Overview

Trusted user initiates first cross-bridge transaction. This creates the mirror token on destination chain and generates a Cross event that federators will manually vote on.

### Prerequisites

**Origin Chain:**
- Token deployed and verified
- User has tokens in wallet
- User has gas for transaction

**Destination Chain:**
- Bridge and Federation contracts deployed
- Federators paused (from Step 1)
- MultiSig ready for Step 2 actions

### Process

#### 3.1 Prepare Transaction

**Trusted User Actions:**

1. Navigate to Bridge contract on origin chain
2. Get Bridge address from [contract spreadsheet](https://docs.google.com/spreadsheets/d/1SSqQJ4HNrIo8jRghKBa4ao_aAt4TJxP7jafRV-l0YcM/edit?gid=205430603#gid=205430603)

3. Approve tokens for Bridge:
```solidity
// ERC20.approve()
approve(bridgeAddress, amount)
```

#### 3.2 Execute Cross Transaction

**Method A: Using Truffle Console**

```bash
cd sovryn-token-bridge/bridge
npx truffle console --network <ORIGIN_NETWORK>
```

```javascript
const Bridge = artifacts.require("Bridge");
const ERC20 = artifacts.require("IERC20");

const bridge = await Bridge.deployed();
const token = await ERC20.at("0x[TOKEN_ADDRESS]");

// Approve
await token.approve(bridge.address, "1000000000000000000", {from: "[USER_ADDRESS]"});

// Cross tokens
const tx = await bridge.receiveTokens(
    "0x[TOKEN_ADDRESS]",
    "1000000000000000000",  // amount
    {from: "[USER_ADDRESS]"}
);

console.log("Transaction hash:", tx.tx);
console.log("Block number:", tx.receipt.blockNumber);

// Get Cross event details
const crossEvent = tx.logs.find(log => log.event === "Cross");
console.log("Cross Event:");
console.log("  Token:", crossEvent.args._tokenAddress);
console.log("  To:", crossEvent.args._to);
console.log("  Amount:", crossEvent.args._amount.toString());
console.log("  Symbol:", crossEvent.args._symbol);
console.log("  Decimals:", crossEvent.args._decimals);
console.log("  Granularity:", crossEvent.args._granularity.toString());
console.log("  Log Index:", crossEvent.logIndex);
```

**Method B: Block Explorer**

1. Go to Bridge contract on origin chain explorer
2. Call `Write Contract` → `receiveTokens`
   - `tokenAddress`: token to bridge
   - `amount`: amount in smallest unit
3. Submit transaction
4. Wait for confirmation
5. Open transaction details
6. Find `Cross` event in logs
7. Record all event parameters

#### 3.3 Share Transaction Details via Keybase

**After transaction confirms**, trusted user shares details:

```
🔹 Token: [SYMBOL]
🔹 Origin Chain: [ETH/RSK/BSC]
🔹 Destination Chain: [RSK/ETH/BSC]
🔹 TX Hash: 0x[HASH]
🔹 Block Number: [NUMBER]
🔹 Block Hash: 0x[BLOCK_HASH]
🔹 Log Index: [INDEX]
🔹 Token Address (origin): 0x[ORIGINAL_TOKEN_ADDRESS]
🔹 Receiver: 0x[RECEIVER_ADDRESS]
🔹 Amount: [AMOUNT]
🔹 Symbol: [SYMBOL]
🔹 Decimals: [DECIMALS]
🔹 Granularity: [GRANULARITY]
🔹 User Data: [USER_DATA or empty]
```

**How to get Block Hash:**

Using web3 in truffle console:
```javascript
const block = await web3.eth.getBlock([BLOCK_NUMBER]);
console.log("Block hash:", block.hash);
```

Or via API:
```bash
curl https://mainnet.infura.io/v3/YOUR_KEY \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["0x[BLOCK_HEX]",false],"id":1}'
```

#### 3.4 Verify Mirror Token Created

On **destination chain**, check for `NewSideToken` event after federators vote (Step 4).

**Truffle Console:**
```javascript
const Bridge = artifacts.require("Bridge");
const bridge = await Bridge.deployed();

// Get past events
const events = await bridge.getPastEvents("NewSideToken", {
    fromBlock: [RECENT_BLOCK],
    toBlock: "latest"
});

console.log("New side token:", events[0].returnValues._sideToken);
console.log("Original token:", events[0].returnValues._originalToken);
console.log("Symbol:", events[0].returnValues._newSymbol);
```

**Block Explorer:**
- Search Bridge contract
- Go to Events tab
- Filter for `NewSideToken`
- Record side token address

#### 3.5 Important Notes

**DO NOT:**
- Restart federator nodes yet (wait for Step 4 voting)
- Use large amounts for first cross (recommend minimal test amount)
- Share transaction details publicly (use Keybase only)

**Verify:**
- Transaction confirmed on origin chain
- `Cross` event emitted successfully
- All parameters captured correctly
- Block hash obtained
- All federators have details before proceeding to Step 4

### Troubleshooting

**"Token not allowed"**  
→ Origin chain: Token must be allowed in AllowTokens contract first

**"Amount below minimum"**  
→ Check `getMinPerToken()` for the token, increase amount

**"Insufficient allowance"**  
→ Call `token.approve(bridgeAddress, amount)` first

**"Daily limit exceeded"**  
→ Check `AllowTokens.dailyLimit()` and current `spentToday`

**Transaction reverts without reason**  
→ Check if Bridge is paused: `Bridge.paused()` should be `false`

---

## STEP 4: Manual Voting Using [bridge-private](https://github.com/DistributedCollective/bridge-private)  

### Federation Contract

**Reference:** [`/sovryn-token-bridge/bridge/contracts/Federation.sol`](https://github.com/DistributedCollective/Bridge-SC/blob/master/sovryn-token-bridge/bridge/contracts/Federation.sol) in bridge-private

**Key function:** `voteTransaction()` (Lines 91-115) or `voteTransactionAt()` (Lines 117-142) for transactions with user data

### Voting Options

#### Option A: Python Script (Recommended)

**⚠️ TODO:** Python voting script exists but needs to be located (likely in Bridge Contracts repo).

Expected: Takes transaction params from Keybase, calls `voteTransaction()` with your key, returns confirmation.

**This section will be updated once script is located.**

#### Option B: Truffle Console

Navigate to bridge directory:
```bash
cd sovryn-token-bridge/bridge
```

Open console:
```bash
# Mainnet
npx truffle console --network rskmainnet

# Testnet  
npx truffle console --network rsktestnet
```

Execute vote:
```javascript
const Federation = artifacts.require("Federation");
const federation = await Federation.at('[FEDERATION_ADDRESS]');

// Without user data
await federation.voteTransaction(
    '[TOKEN_ADDRESS]',
    '[RECEIVER]',
    '[AMOUNT]',
    '[SYMBOL]',
    '[BLOCK_HASH]',
    '[TX_HASH]',
    [LOG_INDEX],      // number, no quotes
    [DECIMALS],       // number, no quotes
    [GRANULARITY],    // number, no quotes
    { from: '[YOUR_FEDERATOR_ADDRESS]', gas: 500000 }
);

// With user data
await federation.voteTransactionAt(
    '[TOKEN_ADDRESS]', '[RECEIVER]', '[AMOUNT]', '[SYMBOL]',
    '[BLOCK_HASH]', '[TX_HASH]', [LOG_INDEX], [DECIMALS], [GRANULARITY],
    '[USER_DATA]',
    { from: '[YOUR_FEDERATOR_ADDRESS]', gas: 500000 }
);
```

**Important:** Replace `[PLACEHOLDERS]` with actual values. Numbers should NOT be quoted.

### Confirm in Keybase

```
✅ [Your Name] - Vote submitted for TX: 0x[HASH]
📝 My vote TX: 0x[VOTE_TX_HASH]
```

### Verification

**Option 1: Blockchain Explorer**
1. Go to https://explorer.rsk.co/ (or testnet)
2. Find Federation contract
3. Check Events tab for `Executed` event

**Option 2: Truffle Console**
```javascript
const wasProcessed = await federation.transactionWasProcessed('[TX_ID]');
console.log('Processed:', wasProcessed);  // Should be true
```

### Troubleshooting

**"Caller not a Federator"** → Your address not registered in Federation contract

**"initStageDone == false"** → Federation not initialized; MultiSig must call `setInitStageDone(true)`

**Transaction ID mismatch** → Double-check all parameters match Cross event data exactly

---

## STEP 5: Resume Operations from [bridge-private](https://github.com/DistributedCollective/bridge-private)  

### Who Initiates?

Same coordinator who initiated pause, after confirming Step 4 completed successfully.

### How to Resume

SSH to your node:
```bash
./start.sh [FED_ENV] [FED_ID]
```

**Example:**
```bash
./start.sh mainnet-ETH-RSK fed-01
```

**FED_ENV options:** `mainnet-ETH-RSK`, `mainnet-BSC-RSK`, `testnet-ETH-RSK`

### Verify

**1. Docker status:**
```bash
docker ps | grep fed-tokenbridge  # Should show running
```

**2. Check logs:**
```bash
tail -f federator.log
```

Look for:
- `RSK Host [URL]`
- `ETH Host [URL]`
- `This node is a leader` or `Not leader, just chilling`
- `Starting federator run`

**3. Monitor new asset:**
```bash
tail -f federator.log | grep "[TOKEN_SYMBOL]"
```

### Confirm in Keybase

```
✅ [Your Name] - Node online. Processing events normally.
```

### If Issues Arise

1. Immediately stop: `./stop.sh`
2. Report in Keybase with error details
3. Do NOT resume until issue resolved

---

## Quick Checklist

### Pre-Operations
- [ ] Keybase channel active
- [ ] All federators notified
- [ ] Asset details documented

### Step 1: Pause
- [ ] Coordinator announces
- [ ] Run `./stop.sh`
- [ ] Verify Docker stopped
- [ ] Confirm in Keybase

### Step 2: Deploy Token
- [ ] First cross transaction executed (creates mirror token)
- [ ] Mirror token address obtained
- [ ] `allowToken.js` MultiSig transaction submitted
- [ ] Required signatures collected
- [ ] Token allowed
- [ ] `setFeeAndMinPerToken.js` MultiSig transaction submitted
- [ ] Required signatures collected  
- [ ] Fee and min configured
- [ ] Configuration verified
- [ ] All confirm in Keybase

### Step 3: First Transaction
- [ ] Trusted user initiates
- [ ] Token approved for Bridge
- [ ] `receiveTokens()` executed
- [ ] Transaction confirmed
- [ ] `Cross` event captured
- [ ] Block hash obtained
- [ ] Details shared via Keybase
- [ ] All federators verified info

### Step 4: Vote
- [ ] Vote via Python script or Truffle
- [ ] Required quorum achieved
- [ ] `Executed` event emitted
- [ ] Bridge marks as `processed`
- [ ] Receiver confirms tokens
- [ ] All confirm in Keybase

### Step 5: Resume
- [ ] Coordinator announces
- [ ] Run `./start.sh [ENV] [ID]`
- [ ] Verify Docker running
- [ ] Check logs
- [ ] Test transaction processed
- [ ] All confirm in Keybase

---

## Key File References

### From bridge-private:

**Scripts:**
- `/start.sh` - Start node
- `/stop.sh` - Stop node
- `/sovryn-token-bridge/query_cross_events.sh` - Query events

**Config:**
- `/federator-env/[ENV]/config.js` - Main config
- `/federator-env/[ENV]/mainnet.json` - ETH addresses
- `/federator-env/[ENV]/rskmainnet.json` - RSK addresses

**Source:**
- `/sovryn-token-bridge/federator/src/main.js` - Main entry
- `/sovryn-token-bridge/federator/src/lib/Federator.js` - Core logic

### From Bridge-SC:

**Contracts:**
- [`/sovryn-token-bridge/bridge/contracts/Federation.sol`](https://github.com/DistributedCollective/Bridge-SC/blob/master/sovryn-token-bridge/bridge/contracts/Federation.sol) - Voting contract
- [`/sovryn-token-bridge/bridge/contracts/Bridge.sol`](https://github.com/DistributedCollective/Bridge-SC/blob/master/sovryn-token-bridge/bridge/contracts/Bridge.sol) - Main bridge logic
- [`/sovryn-token-bridge/bridge/contracts/AllowTokens.sol`](https://github.com/DistributedCollective/Bridge-SC/blob/master/sovryn-token-bridge/bridge/contracts/AllowTokens.sol) - Token allowlist
- [`/sovryn-token-bridge/bridge/contracts/MultiSigWallet.sol`](https://github.com/DistributedCollective/Bridge-SC/blob/master/sovryn-token-bridge/bridge/contracts/MultiSigWallet.sol) - MultiSig wallet

**Scripts:**
- [`/sovryn-token-bridge/bridge/scripts/allowToken.js`](https://github.com/DistributedCollective/Bridge-SC/blob/master/sovryn-token-bridge/bridge/scripts/allowToken.js) - Allow token
- [`/sovryn-token-bridge/bridge/scripts/setFeeAndMinPerToken.js`](https://github.com/DistributedCollective/Bridge-SC/blob/master/sovryn-token-bridge/bridge/scripts/setFeeAndMinPerToken.js) - Set fees
- [`/sovryn-token-bridge/bridge/scripts/crossToken.js`](https://github.com/DistributedCollective/Bridge-SC/blob/master/sovryn-token-bridge/bridge/scripts/crossToken.js) - Test cross

**Config:**
- [`/sovryn-token-bridge/bridge/truffle-config.js`](https://github.com/DistributedCollective/Bridge-SC/blob/master/sovryn-token-bridge/bridge/truffle-config.js) - Network config

---

**Last Updated:** October 20, 2025

**END OF MANUAL**
