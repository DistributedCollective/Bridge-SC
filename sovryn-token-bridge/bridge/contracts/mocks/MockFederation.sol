pragma solidity ^0.5.0;
pragma experimental ABIEncoderV2;

import "../zeppelin/cryptography/ECDSA.sol";

contract MockFederation {
    struct SignatureInfo {
        bytes signature;
        uint256 deadline;
    }

    uint256 public memberAmount;
    uint256 public validationAmountRequired;
    address[] public members;

    mapping(address => bool) public isMember;
    mapping(bytes32 => bool) public processed;
    mapping(bytes32 => mapping(address => bool)) public votes;

    event Signed(bytes32 indexed transactionId, address validator);
    event Executed(bytes32 indexed transactionId);

    constructor(address[] memory _members, uint256 _validationAmountRequired) public {
        for (uint256 i; i < _members.length; i++) {
            require(
                !isMember[_members[i]] && _members[i] != address(0),
                "Federation: Invalid member"
            );
            isMember[_members[i]] = true;
            members.push(_members[i]);
        }
        validationAmountRequired = _validationAmountRequired;
    }

    function getMembers() external view returns (address[] memory) {
        return members;
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
        SignatureInfo[] memory signaturesInfos
    ) public returns (bool) {
        return
            _executeTransaction(
                originalTokenAddress,
                receiver,
                amount,
                symbol,
                blockHash,
                transactionHash,
                logIndex,
                decimals,
                granularity,
                "",
                signaturesInfos
            );
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
        SignatureInfo[] memory signaturesInfos
    ) public returns (bool) {
        return
            _executeTransaction(
                originalTokenAddress,
                receiver,
                amount,
                symbol,
                blockHash,
                transactionHash,
                logIndex,
                decimals,
                granularity,
                userData,
                signaturesInfos
            );
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
        SignatureInfo[] memory signaturesInfos
    ) private returns (bool) {
        bytes32 transactionId = getTransactionId(
            originalTokenAddress,
            receiver,
            amount,
            symbol,
            blockHash,
            transactionHash,
            logIndex,
            decimals,
            granularity
        );
        if (processed[transactionId]) return true;

        processSignedTransaction(
            originalTokenAddress,
            receiver,
            amount,
            symbol,
            blockHash,
            transactionHash,
            logIndex,
            decimals,
            granularity,
            userData,
            signaturesInfos
        );

        return true;
    }

    function processSignedTransaction(
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
        SignatureInfo[] memory signaturesInfos
    ) private returns (bool) {
        require(isMember[msg.sender], "Only federators can execute transactions");

        bytes32 transactionIdU = getTransactionIdU(
            originalTokenAddress,
            receiver,
            amount,
            symbol,
            blockHash,
            transactionHash,
            logIndex,
            decimals,
            granularity,
            userData
        );
        if (processed[transactionIdU]) return true;

        votes[transactionIdU][msg.sender] = true;
        uint256 memberValidations = 1; // Sender implicitly accepts
        emit Signed(transactionIdU, msg.sender);

        for (uint256 i; i < signaturesInfos.length; i += 1) {
            require(
                signaturesInfos[i].deadline > block.timestamp,
                "Some signature is not valid anymore"
            );

            uint256 chainId;
            assembly {
                chainId := chainid()
            }
            bytes32 hash = keccak256(
                abi.encodePacked(
                    "\x19Ethereum Signed Message:\n116",
                    abi.encodePacked(
                        transactionIdU,
                        chainId,
                        address(this),
                        signaturesInfos[i].deadline
                    )
                )
            );
            address signer = ECDSA.recover(hash, signaturesInfos[i].signature);

            require(isMember[signer], "Signature doesn't match any member");
            if (!votes[transactionIdU][signer]) {
                votes[transactionIdU][signer] = true;
                memberValidations += 1;
                emit Signed(transactionIdU, signer);
            }
        }

        require(
            memberValidations >= validationAmountRequired &&
                memberValidations >= memberAmount / 2 + 1,
            "Not enough validations"
        );
        processed[transactionIdU] = true;
        emit Executed(transactionIdU);

        return true;
    }

    function transactionWasProcessed(bytes32 transactionId) external view returns (bool) {
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
        uint256 granularity
    ) public pure returns (bytes32) {
        return
            keccak256(
                abi.encodePacked(
                    originalTokenAddress,
                    receiver,
                    amount,
                    symbol,
                    blockHash,
                    transactionHash,
                    logIndex,
                    decimals,
                    granularity
                )
            );
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
        bytes memory userData
    ) public pure returns (bytes32) {
        return
            keccak256(
                abi.encodePacked(
                    originalTokenAddress,
                    receiver,
                    amount,
                    symbol,
                    blockHash,
                    transactionHash,
                    logIndex,
                    decimals,
                    granularity,
                    userData
                )
            );
    }
}
