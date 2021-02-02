// SPDX-License-Identifier: MIT
pragma solidity >=0.6.0 <0.8.0;

import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/math/SafeMathUpgradeable.sol";

contract MockConverter_v2 is Initializable, OwnableUpgradeable, PausableUpgradeable  {

    using SafeMathUpgradeable for uint256;

    address private constant NULL_ADDRESS = address(0);
    mapping(address => bool) private allowedTokens;

    uint256 public conversionFee; // fee to give the buyers a better price
    address public bridgeContractAddress; // Bridge Address
    uint256 private numOrder; // to store the incremental sell orders

    struct Order {
        address sellerAddress; // Sell Order maker address
        address tokenAddress; // Address of the Token
        uint256 orderAmount; // Amount of the order        
        address finalReceipientAddress; // Final destination of the rBTC payed by the buyer
        uint256 previousOrder; // Address of the previous Order
        uint256 nextOrder; // Address of the next Order
    }

    mapping(uint256 => Order) public orders; // map of made sell orders

    event ConversionFeeChanged(uint256 previousValue, uint256 currentValue);

    event BridgeContractAddressChanged(
        address _previousAddress,
        address _currentAddress
    );
    
    modifier onlyBridge() {
        require(
            msg.sender == bridgeContractAddress,
            "Only BRIDGE Contract can call this function"
        );
        _;
    }

    function initialize(uint256 _conversionFee) public initializer {
        require(
            _conversionFee > 0,
            "Deploying error. Conversion fee cannot be zero"
        );
        require(_conversionFee < 61, "Conversion fee cannot be more than 60%");

        conversionFee = _conversionFee;
        numOrder = 0;
        __Ownable_init();
        __Pausable_init();
    }

    function pauseContract() public onlyOwner whenNotPaused {
        _pause();
    }

    function unpauseContract() public onlyOwner whenPaused {
        _unpause();
    }

    function setConversionFee(uint256 _newConversionFee)
        public
        onlyOwner
        returns (bool)
    {
        require(_newConversionFee > 0, "New conversion fee cannot be zero");
        require(_newConversionFee < 61, "New conversion fee cannot be more than 60%");

        uint256 previousValue = conversionFee;
        conversionFee = _newConversionFee;

        emit ConversionFeeChanged(previousValue, conversionFee);
        return true;
    }

    function setBridgeContractAddress(address _bridgeContractAddress)
        public
        onlyOwner
        returns (bool)
    {
        require(
            _bridgeContractAddress != address(0),
            "Invalid bridgeContractAddress"
        );

        address previousAddress = bridgeContractAddress;
        bridgeContractAddress = _bridgeContractAddress;

        emit BridgeContractAddressChanged(
            previousAddress,
            bridgeContractAddress
        );
        return true;
    }

}
