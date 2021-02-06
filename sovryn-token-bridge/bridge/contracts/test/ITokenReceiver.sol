pragma solidity ^0.5.0;

import "../zeppelin/token/ERC777/IERC777Recipient.sol";
import "../zeppelin/introspection/IERC1820Registry.sol";


/// @title interface for contracts called from the bridge
contract ITokenReceiver is IERC777Recipient {
    IERC1820Registry constant private _erc1820 = IERC1820Registry(0x1820a4B7618BdE71Dce8cdc73aAB6C95905faD24);

    event onTokenReceivedCall(
        address operator,
        address from,
        address to,
        uint amount,
        bytes userData,
        bytes operatorData
    );

    constructor() public {
        _erc1820.setInterfaceImplementer(address(this), keccak256("ERC777TokensRecipient"), address(this));
    }

    /// @notice this function is used in the Converter to be called from the bridge contract
    function onTokensMinted(
        uint256 _orderAmount,
        address _tokenAddress,
        bytes calldata _userData
    ) external;


    function tokensReceived(
        address operator,
        address from,
        address to,
        uint amount,
        bytes calldata userData,
        bytes calldata operatorData
    ) external {
        emit onTokenReceivedCall(
            operator,
            from,
            to,
            amount,
            userData,
            operatorData
        );
    }
}
