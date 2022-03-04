pragma solidity ^0.5.0;
pragma experimental ABIEncoderV2;

import "../zeppelin/cryptography/ECDSA.sol";

contract MockFederation {
    mapping(bytes32 => bool) public processed;

	// event Voted(address indexed sender, bytes32 indexed transactionId, address originalTokenAddress, address receiver, uint256 amount, string symbol, bytes32 blockHash, bytes32 indexed transactionHash, uint32 logIndex, uint8 decimals, uint256 granularity, bytes userData);
    event Executed(bytes32 indexed transactionId);

    function executeTransaction(
        address originalTokenAddress,
        address receiver,
        uint256 amount,
        string memory symbol,
        bytes32 blockHash,
        bytes32 transactionHash,
        uint32 logIndex,
        uint8 decimals,
        uint256 granularity,
        bytes[] memory sigs
    )
    public returns(bool)
    {
        return _executeTransaction(originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, "", sigs);
    }

    function executeTransactionAt(
        address originalTokenAddress,
        address receiver,
        uint256 amount,
        string memory symbol,
        bytes32 blockHash,
        bytes32 transactionHash,
        uint32 logIndex,
        uint8 decimals,
        uint256 granularity,
        bytes memory userData,
        bytes[] memory sigs
    )
    public returns(bool)
    {
       return _executeTransaction(originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, userData, sigs);
    }

    function _executeTransaction(
        address originalTokenAddress,
        address receiver,
        uint256 amount,
        string memory symbol,
        bytes32 blockHash,
        bytes32 transactionHash,
        uint32 logIndex,
        uint8 decimals,
        uint256 granularity,
        bytes memory userData,
        bytes[] memory sigs
    ) private returns(bool) {
			  bytes32 transactionId = getTransactionId(originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity);
        if (processed[transactionId])
            return true;

        processTransaction(originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, userData, sigs);

        return true;
    }

    function processTransaction(
        address originalTokenAddress,
        address receiver,
        uint256 amount,
        string memory symbol,
        bytes32 blockHash,
        bytes32 transactionHash,
        uint32 logIndex,
        uint8 decimals,
        uint256 granularity,
        bytes memory userData,
        bytes[] memory sigs
    )
    private returns(bool) 
    {
        bytes32 transactionIdU = getTransactionIdU(originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, userData);

        if (processed[transactionIdU])
            return true;

        // emit Voted(msg.sender, transactionIdU, originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, userData);
        

				/******** CHECK SIGNATURES HERE ***********/
        // uint transactionCount = getTransactionCount(transactionIdU);
        // if (transactionCount >= required && transactionCount >= members.length / 2 + 1) {
            processed[transactionIdU] = true;
            
            // bool acceptTransfer = bridge.acceptTransferAt(
            //     originalTokenAddress,
            //     receiver,
            //     amount,
            //     symbol,
            //     blockHash,
            //     transactionHash,
            //     logIndex,
            //     decimals,
            //     granularity,
            //     userData
            // );
            // require(acceptTransfer, "Federation: Bridge acceptTransfer error");
						
            emit Executed(transactionIdU);
            return true;

        // }
    }

    function getSigner(bytes32 transactionId, bytes memory signature) public pure returns (address signer) {
        // bytes memory bMessage = abi.encode(msg.sender);
        bytes32 hash = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", transactionId));
        signer = ECDSA.recover(hash, signature);
    }

    function transactionWasProcessed(bytes32 transactionId) external view returns(bool)
    {
        return processed[transactionId];
    }

    function getTransactionId(
        address originalTokenAddress,
        address receiver,
        uint256 amount,
        string memory symbol,
        bytes32 blockHash,
        bytes32 transactionHash,
        uint32 logIndex,
        uint8 decimals,
        uint256 granularity)
    public pure returns(bytes32)
    {
        return keccak256(abi.encodePacked(originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity));
    }

    function getTransactionIdU(
        address originalTokenAddress,
        address receiver,
        uint256 amount,
        string memory symbol,
        bytes32 blockHash,
        bytes32 transactionHash,
        uint32 logIndex,
        uint8 decimals,
        uint256 granularity,
        bytes memory userData)
    public pure returns(bytes32)
    {
        return keccak256(abi.encodePacked(originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, userData));
    }
}