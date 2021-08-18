
// SPDX-License-Identifier: MIT
pragma solidity ^0.5.0;

import "./IBridge.sol";
import "./ISideToken.sol";
import "./IErc777Receiver.sol";
import "./zeppelin/ownership/Ownable.sol";

contract Erc777Converter is IErc777Receiver, Ownable {

    IBridge public bridgeContract; // Bridge Address
    address constant private NULL_ADDRESS = address(0);

    event BridgeContractChanged(
        address _previousAddress,
        address _currentAddress
    );

    event TokensReceived(
        address _recipientAddress,
        uint256 _orderAmount,
        address _tokenAddress
    );

    modifier onlyBridge() {
        require(
            msg.sender == address(bridgeContract),
            "Only BRIDGE Contract can call this function"
        );
        _;
    }
  
    modifier notNull(address _address) {
        require(_address != NULL_ADDRESS, "Address cannot be empty");
        _;
    }
    
    constructor() public IErc777Receiver() {
    }

    function onTokensMinted(
            uint256 _amount,
            address _tokenAddress,
            bytes calldata _userData
        )
            external
            onlyBridge
            notNull(_tokenAddress)
        {
            require(_amount > 0, "Invalid Amount sent");
            ISideToken sideToken = ISideToken(_tokenAddress);
            address recipient = decodeAddress(_userData);

            emit TokensReceived(recipient, _amount, _tokenAddress);

            require(sideToken.transfer(recipient,_amount), "transfer to receiver failed");
        }

        function decodeAddress(bytes memory data) private pure returns (address) {
            address addr = abi.decode(data, (address));
            require(addr != NULL_ADDRESS, "Converter: Error decoding extraData");
            return addr;
        }

        function setBridgeContract(address _bridgeContract)
        public
        onlyOwner
        notNull(_bridgeContract)
        returns (bool)
    {
        address previousAddress = address(bridgeContract);
        bridgeContract = IBridge(_bridgeContract);

        emit BridgeContractChanged(previousAddress, _bridgeContract);
        return true;
    }
    
}