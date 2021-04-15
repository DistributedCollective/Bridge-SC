# federators: 
- how to connect
- where are the logs
- how to stop/start a federator

## how to connect
Federators are located on private network which can be accessed only via jump server (VPN does not yet exists)


1. first connect to the jump server with ssh

        ```ssh -i <privatekey> ubuntu@3.16.33.190```

2. connect to one of the federators, current federators:
- federator/mainnet/eth-rsk/1 - 10.154.40.227
- federator/testnet/eth-rsk/1 - 10.154.40.169
- federator/testnet/eth-rsk/2 - 10.154.40.243

        ```ssh -i <privatekey> ubuntu@<federator_private_ip>```



## where are the logs
federator log is located here /home/ubuntu/Bridge-SC/federator.log

## how to stop/start a federator

- start and stop script are located here: 
  ```/home/ubuntu/Bridge-SC/start.sh```
  ```/home/ubuntu/Bridge-SC/stop.sh```

- start.sh retrieve an argument for the block chain you would like the federator to connect to for example starting a federtor command:
  ```./start.sh mainnet-ETH-RSK &```

  where blockchain type is actually one of the folder names locate here ```/Users/dev/sovryn/Bridge-SC/federator-env/mainnet-ETH-RSK``` which describes the federator config

- stop.sh gets no argument

# federator keys:
please note that a federator server would start if a key on aws secrets manager is not defined, the secret name on aws should have the same name of the federator server.



