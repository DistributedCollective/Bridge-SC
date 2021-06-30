pragma solidity ^0.5.0;

import "./IBridge.sol";
import "./zeppelin/ownership/Ownable.sol";

contract Federation is Ownable {
    uint constant public MAX_MEMBER_COUNT = 50;
    address constant private NULL_ADDRESS = address(0);

    IBridge public bridge;
    address[] public members;
    uint public required;

    bytes32 constant private NULL_HASH = bytes32(0);
    bool public initStageDone;

    mapping (address => bool) public isMember;
    mapping (bytes32 => mapping (address => bool)) public votes;
    mapping(bytes32 => bool) public processed;
    // solium-disable-next-line max-len
    event Voted(address indexed sender, bytes32 indexed transactionId, address originalTokenAddress, address receiver, uint256 amount, string symbol, bytes32 blockHash, bytes32 indexed transactionHash, uint32 logIndex, uint8 decimals, uint256 granularity);
    event Executed(bytes32 indexed transactionId);
    event MemberAddition(address indexed member);
    event MemberRemoval(address indexed member);
    event RequirementChange(uint required);
    event BridgeChanged(address bridge);
    event RevokeTxAndVote(bytes32 tx_revoked);
    event StoreFormerFederationExecutedTx(bytes32 tx_stored);

    modifier onlyMember() {
        require(isMember[_msgSender()], "Federation: Caller not a Federator");
        _;
    }

    modifier validRequirement(uint membersCount, uint _required) {
        // solium-disable-next-line max-len
        require(_required <= membersCount && _required != 0 && membersCount != 0, "Federation: Invalid requirements");
        _;
    }

    constructor(address[] memory _members, uint _required) public validRequirement(_members.length, _required) {
        require(_members.length <= MAX_MEMBER_COUNT, "Federation: Members larger than max allowed");
        members = _members;
        for (uint i = 0; i < _members.length; i++) {
            require(!isMember[_members[i]] && _members[i] != NULL_ADDRESS, "Federation: Invalid members");
            isMember[_members[i]] = true;
            emit MemberAddition(_members[i]);
        }
        required = _required;
        emit RequirementChange(required);
    }

    function setBridge(address _bridge) external onlyOwner {
        require(_bridge != NULL_ADDRESS, "Federation: Empty bridge");
        bridge = IBridge(_bridge);
        emit BridgeChanged(_bridge);
    }

    function voteTransaction(
        address originalTokenAddress,
        address receiver,
        uint256 amount,
        string calldata symbol,
        bytes32 blockHash,
        bytes32 transactionHash,
        uint32 logIndex,
        uint8 decimals,
        uint256 granularity)
    external returns(bool)
    {
        return _voteTransaction(originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, "");
    }

    function voteTransactionAt(
        address originalTokenAddress,
        address receiver,
        uint256 amount,
        string calldata symbol,
        bytes32 blockHash,
        bytes32 transactionHash,
        uint32 logIndex,
        uint8 decimals,
        uint256 granularity,
        bytes calldata userData)
    external returns(bool)
    {
        return _voteTransaction(originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, userData);
    }

    function _voteTransaction(
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
    ) internal onlyMember returns(bool) {
        // solium-disable-next-line max-len
        require(initStageDone == true, "Federation: Cannot process TX while initStageDone == false");
        bytes32 transactionId = getTransactionId(originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity);
        if (processed[transactionId])
            return true;

        if (votes[transactionId][_msgSender()])
            return true;

        votes[transactionId][_msgSender()] = true;
        // solium-disable-next-line max-len
        emit Voted(_msgSender(), transactionId, originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity);

        uint transactionCount = getTransactionCount(transactionId);
        if (transactionCount >= required && transactionCount >= members.length / 2 + 1) {
            processed[transactionId] = true;
            bool acceptTransfer = bridge.acceptTransferAt(
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
            require(acceptTransfer, "Federation: Bridge acceptTransfer error");
            emit Executed(transactionId);
            return true;
        }

        return true;
    }

    function getTransactionCount(bytes32 transactionId) public view returns(uint) {
        uint count = 0;
        for (uint i = 0; i < members.length; i++) {
            if (votes[transactionId][members[i]])
                count += 1;
        }
        return count;
    }

    function hasVoted(bytes32 transactionId) external view returns(bool)
    {
        return votes[transactionId][_msgSender()];
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
        // solium-disable-next-line max-len
        return keccak256(abi.encodePacked(originalTokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity));
    }

    function addMember(address _newMember) external onlyOwner
    {
        require(_newMember != NULL_ADDRESS, "Federation: Empty member");
        require(!isMember[_newMember], "Federation: Member already exists");
        require(members.length < MAX_MEMBER_COUNT, "Federation: Max members reached");

        isMember[_newMember] = true;
        members.push(_newMember);
        emit MemberAddition(_newMember);
    }

    function removeMember(address _oldMember) external onlyOwner
    {
        require(_oldMember != NULL_ADDRESS, "Federation: Empty member");
        require(isMember[_oldMember], "Federation: Member doesn't exists");
        require(members.length > 1, "Federation: Can't remove all the members");
        require(members.length - 1 >= required, "Federation: Can't have less than required members");

        isMember[_oldMember] = false;
        for (uint i = 0; i < members.length - 1; i++) {
            if (members[i] == _oldMember) {
                members[i] = members[members.length - 1];
                break;
            }
        }
        members.length -= 1;
        emit MemberRemoval(_oldMember);
    }

    function getMembers() external view returns (address[] memory)
    {
        return members;
    }

    function changeRequirement(uint _required) external onlyOwner validRequirement(members.length, _required)
    {
        require(_required >= 2, "Federation: Requires at least 2");
        required = _required;
        emit RequirementChange(_required);
    }

// Revoke state of txID (from true to false), to enable nultiSig release of stucked txID on the bridge
// setRevokeTransaction() should be called on the bridge as well to enable revoke of txID
    function setRevokeTransactionAndVote(bytes32 _revokeTransactionID) external onlyOwner {
        require(_revokeTransactionID != NULL_HASH, "Federation: _revokeTransactionID cannot be NULL");
        require(processed[_revokeTransactionID] == true, "Federation: cannot revoke unprocessed TX");   
        processed[_revokeTransactionID] = false;
        for (uint i = 0; i < members.length; i++) {
            votes[_revokeTransactionID][members[i]] = false;
        }
        emit RevokeTxAndVote(_revokeTransactionID);

    }

// Store former Federation contract version processed[] state
// Can be used only at deployment stage. Cannot _voteTransaction txID while this stage is active (initStageDone is false)
    // function initStoreOldFederation(bytes32 _TransactionID) external onlyOwner {
    //     require(initStageDone == false, "Federation: initStoreOldFederation enabled only during deployment setup Stage");
    //     require(_TransactionID != NULL_HASH, "Federation: _revokeTransactionID cannot be NULL");
    //     processed[_TransactionID] = true;
        
    //     emit StoreFormerFederationExecutedTx(_TransactionID);
    // }
    function initStoreOldFederation(bytes32[] calldata _TransactionIDs) external onlyOwner {
        require(initStageDone == false, "Federation: initStoreOldFederation enabled only during deployment setup Stage");
        //require(_TransactionID != NULL_HASH, "Federation: _revokeTransactionID cannot be NULL");
        for (uint i = 0; i < _TransactionIDs.length; i++) {
            require(_TransactionIDs[i] != NULL_HASH, "Federation: _storeTransactionID cannot be NULL");
            processed[_TransactionIDs[i]] = true;
            emit StoreFormerFederationExecutedTx(_TransactionIDs[i]);
        }
    }

// Finish stage of store of former Federation contract version
// Must be set to true before _voteTransaction is called 
    function endDeploymentSetup() external onlyOwner {
        initStageDone = true;
    }
}