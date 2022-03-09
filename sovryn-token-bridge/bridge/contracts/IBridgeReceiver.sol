pragma solidity ^0.5.0;

/// @title interface for contracts that can react to bridge ETH transfers, and maybe token transfers in the future
interface IBridgeReceiver {
    function receiveEthFromBridge(
        bytes calldata userData
    ) external payable;
}