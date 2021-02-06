pragma solidity ^0.5.0;

import "./ITokenReceiver.sol";
import "../zeppelin/introspection/IERC1820Registry.sol";

/// @title method for test feature of calling onTokenMinter
contract TokenReceiverImpl is ITokenReceiver {

    event onTokenMintedCall(
        uint256 _orderAmount,
        address _tokenAddress,
        bytes _userData
    );

    constructor() public ITokenReceiver() {
    }

    function onTokensMinted(
        uint256 _orderAmount,
        address _tokenAddress,
        bytes calldata _userData
    ) external {
        emit onTokenMintedCall(
            _orderAmount, _tokenAddress, _userData
        );
    }
}
