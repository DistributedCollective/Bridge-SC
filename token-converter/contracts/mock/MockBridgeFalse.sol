// SPDX-License-Identifier: MIT
pragma solidity >=0.6.0 <0.8.0;

contract MockBridgeFalse {
    address private constant NULL_ADDRESS = address(0);

    function version() external pure returns (string memory) {
        return "";
    }

    function getFeePercentage() external pure returns (uint256) {
        return 1;
    }

    function calcMaxWithdraw() external pure returns (uint256) {
        return 1;
    }

    function receiveTokens(address, uint256) external pure returns (bool) {
        return true;
    }

    function receiveTokensAt(
        address,
        uint256,
        address,
        bytes calldata
    ) external pure returns (bool) {
        return false;
    }

    function tokensReceived(
        address,
        address,
        address,
        uint256,
        bytes calldata,
        bytes calldata
    ) external {}

    function acceptTransfer(
        address,
        address,
        uint256,
        string calldata,
        bytes32,
        bytes32,
        uint32,
        uint8,
        uint256
    ) external pure returns (bool) {
        return true;
    }
}
