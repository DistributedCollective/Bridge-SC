pragma solidity ^0.5.0;
pragma experimental ABIEncoderV2;

import "../zeppelin/cryptography/ECDSA.sol";

contract MockFederation {
    uint256 public memberAmount;
    uint256 public validationAmountRequired;

    mapping(address => bool) public isMember;
    mapping(bytes32 => bool) public processed;

    event Executed(bytes32 indexed transactionId);

    constructor(address[] memory _members, uint256 _validationAmountRequired) public {
        for (uint256 i; i < _members.length; i++) {
            require(!isMember[_members[i]] && _members[i] != address(0), "Federation: Invalid member");
            isMember[_members[i]] = true;
        }
        validationAmountRequired = _validationAmountRequired;
    }     

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
    private returns(bool) {
        require(isMember[msg.sender], "Only federators can execute transactions");

        bytes32 transactionIdU = getTransactionIdU(originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, userData);
        if (processed[transactionIdU])
            return true;
        
        uint256 memberValidations = 1; // Sender implicitly accepts
        for (uint256 i; i < sigs.length; i +=1) {
            bytes32 hash = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", transactionIdU));
            address signer = ECDSA.recover(hash, sigs[i]);

            if (isMember[signer] && signer != msg.sender) {
                memberValidations += 1;
            }
        }

        require(memberValidations >= validationAmountRequired && memberValidations >= memberAmount / 2 + 1, "Not enough validations");
        processed[transactionIdU] = true;                    
        return true;
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