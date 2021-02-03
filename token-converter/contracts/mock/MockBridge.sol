// SPDX-License-Identifier: MIT
pragma solidity >=0.6.0 <0.8.0;

contract Bridge {
    function version() external pure returns (string memory) {
        return "";
    }

    function getFeePercentage() external view returns (uint256) {
        return 1;
    }

    function calcMaxWithdraw() external view returns (uint256) {
        return 1;
    }

    function receiveTokens(address tokenToUse, uint256 amount)
        external
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
    ) external returns (bool) {
        return true;
    }

    function tokensReceived(
        address operator,
        address from,
        address to,
        uint256 amount,
        bytes calldata userData,
        bytes calldata operatorData
    ) external {}

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
    ) external returns (bool) {
        return true;
    }

    event Cross(
        address indexed _tokenAddress,
        address indexed _to,
        uint256 _amount,
        string _symbol,
        bytes _userData,
        uint8 _decimals,
        uint256 _granularity
    );
    event NewSideToken(
        address indexed _newSideTokenAddress,
        address indexed _originalTokenAddress,
        string _newSymbol,
        uint256 _granularity
    );
    event AcceptedCrossTransfer(
        address indexed _tokenAddress,
        address indexed _to,
        uint256 _amount,
        uint8 _decimals,
        uint256 _granularity,
        uint256 _formattedAmount,
        uint8 _calculatedDecimals,
        uint256 _calculatedGranularity
    );
    event FeePercentageChanged(uint256 _amount);
}
