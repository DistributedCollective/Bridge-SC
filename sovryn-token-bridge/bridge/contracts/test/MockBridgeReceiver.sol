pragma solidity ^0.5.0;

import "../IBridgeReceiver.sol";

contract MockBridgeReceiver is IBridgeReceiver {
    event Fallback(
        address sender,
        uint256 value
    );

    event ReceivedEthFromBridge(
        address sender,
        uint256 value,
        bytes userData
    );

    // Allow fallback for easier testing
    function () external payable {
        emit Fallback(
            msg.sender,
            msg.value
        );
    }

    function receiveEthFromBridge(
        bytes calldata userData
    ) external payable {
        emit ReceivedEthFromBridge(
            msg.sender,
            msg.value,
            userData
        );
    }
}