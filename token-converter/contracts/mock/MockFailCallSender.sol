// SPDX-License-Identifier: MIT
pragma solidity >=0.6.0 <0.8.0;

import "../Converter.sol";

contract MockFailOnReceiveCaller {
    function call(
        Converter converter,
        uint256 orderId,
        uint256 amountToBuy, // qty tokens to buy
        address destinationAddress,
        bytes calldata signature,
        bytes calldata extraData // public
    ) public {
        converter.takeSellOrder(
            orderId,
            amountToBuy,
            destinationAddress,
            signature,
            extraData
        );
    }
}
