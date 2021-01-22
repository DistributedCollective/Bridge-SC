# Token Converter

## Base Contract
In order to deploy this contract into RSK testnet network you should have a mnemonic phrase and some rBTC in such address.
The mnemonic must be saved in this file 
`token-converter/mnemonic.key`

With this format:
`cat ring own bus mere surf value blind space asfalt elder fun`


**Tests**:
<br>
To execute the tests, ganache-cli must be running.
Go to this folder:  
`token-converter/`
<br><br>
Install all the packages with:  
`npm i`
<br><br>
Afterwards execute this script to run ganache-cli:  
`npm run ganache`  
<br><br>
Open another terminal and execute this script to run the tests:  
`npm run test`
<br><br>
To show the coverage run this script:  
`npm run coverage`
