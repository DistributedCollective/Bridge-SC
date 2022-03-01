pragma solidity ^0.5.0;

contract MockBridge {
    event Cross(
        address indexed _tokenAddress,
        address indexed _to,
        uint256 _amount,
        string _symbol,
        bytes _userData,
        uint8 _decimals,
        uint256 _granularity
    );

    function crossTokens(
        address tokenToUse,
        address receiver,
        uint256 amountMinusFees,
        string calldata symbol,
        bytes calldata userData,
        uint8 decimals,
        uint256 granularity
    ) external {
        emit Cross(tokenToUse, receiver, amountMinusFees, symbol, userData, decimals, granularity);
    }

    function getTransactionId(
        bytes32 _blockHash,
        bytes32 _transactionHash,
        address _receiver,
        uint256 _amount,
        uint32 _logIndex
    )
        public pure returns(bytes32)
    {
        return keccak256(abi.encodePacked(_blockHash, _transactionHash, _receiver, _amount, _logIndex));
    }
}
