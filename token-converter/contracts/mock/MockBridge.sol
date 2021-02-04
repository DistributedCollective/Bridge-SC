// SPDX-License-Identifier: MIT
pragma solidity >=0.6.0 <0.8.0;

import "../IBridge.sol";

contract Bridge is IBridge {

    function version() external pure override returns (string memory) {
        return "";
    }

    function getFeePercentage() external view override returns (uint256) {
        return 1;
    }

    function calcMaxWithdraw() external view override returns (uint256) {
        return 1;
    }

    function receiveTokens(address tokenToUse, uint256 amount)
        external override
        returns (bool)
    {
        return true;
    }

    function receiveTokensAt(
        address tokenToUse,
        uint256 amount,
        address receiver,
        bytes calldata signature,
        bytes calldata extraData
    ) external override returns (bool) {
        return true;
    }

    function tokensReceived(
        address operator,
        address from,
        address to,
        uint256 amount,
        bytes calldata userData,
        bytes calldata operatorData
    ) external override {}

    function acceptTransfer(
        address originalTokenAddress,
        address receiver,
        uint256 amount,
        string calldata symbol,
        bytes32 blockHash,
        bytes32 transactionHash,
        uint32 logIndex,
        uint8 decimals,
        uint256 granularity
    ) external override returns (bool) {
        return true;
    }
}
