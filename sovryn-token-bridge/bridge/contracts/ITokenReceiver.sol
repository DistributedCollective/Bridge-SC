pragma solidity ^0.5.0;

/// @title interface for contracts called from the bridge
interface ITokenReceiver {

    /// @notice this function is used in the Converter to be called from the bridge contract
    function onTokensMinted(
        uint256 _orderAmount,
        address _tokenAddress,
        bytes calldata userData
    ) external;
}
