pragma solidity ^0.5.0;

import "../Bridge.sol";

contract mockBridge is Bridge {

    function mockCrossTokens(address tokenToUse, address receiver, uint256 amount, bytes memory userData) public {
        return super.crossTokens(tokenToUse, receiver, amount, userData);
    }

    function mockAcceptCrossBackToToken(address receiver, address tokenAddress, uint8 decimals, uint256 granularity, uint256 amount) public {
        super._acceptCrossBackToToken(receiver, tokenAddress, decimals, granularity, amount);
    }

    function mockReceiveTokens(
        address tokenToUse,
        uint256 amount,
        address receiver,
        bytes memory extraData
    ) public whenNotUpgrading whenNotPaused nonReentrant returns(bool) {
        return super._receiveTokens(tokenToUse, amount, receiver, extraData);
    }

    function mockCreateSideToken(address token, string memory symbol, uint256 granularity) public returns (ISideToken sideToken){
        return super._createSideToken(token, symbol, granularity);
    }

}