// SPDX-License-Identifier: MIT
pragma solidity >=0.6.0 <0.8.0;

import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/math/SafeMathUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import "../IBridge.sol";

contract MockConverter_v2 is
    Initializable,
    OwnableUpgradeable,
    PausableUpgradeable,
    ReentrancyGuardUpgradeable
{
    using SafeMathUpgradeable for uint256;

    address private constant NULL_ADDRESS = address(0);
    mapping(address => bool) private allowedTokens;

    uint256 public conversionFee; // fee to give the buyers a better price

    IBridge public bridgeContract; // Bridge Address

    uint256 public numOrder; // to store the incremental sell orders, always increment when creating new order
    uint256 public lastOrderIndex; // to store the number of the last order (differs from numOrder when buiying the last order)
    uint256 public firstOrderIndex; // to store the number of the first order (to do the getSellOrder pagination)

    struct Order {
        address tokenAddress; // Address of the Token
        uint256 orderAmount; // Amount of the order
        uint256 remainingAmount; // Amount left to fill the order
        address recipient; // Destination address of the rBTC payed by the buyer
        uint256 previousOrder; // Address of the previous Order
        uint256 nextOrder; // Address of the next Order
    }

    mapping(uint256 => Order) public orders; // map of made sell orders

    uint256 public constant feePercentageDivider = 10000; // Percentage with up to 2 decimals

    event ConversionFeeChanged(uint256 previousValue, uint256 currentValue);

    event BridgeContractChanged(
        address _previousAddress,
        address _currentAddress
    );

    event TokensReceived(
        address _recipientAddress,
        uint256 _orderAmount,
        address _tokenAddress
    );

    event MakeSellOrder(
        uint256 _orderId,
        uint256 _amount,
        address _tokenAddress,
        address _recipientAddress
    );

    event TakeSellOrder(
        uint256 _orderId,
        uint256 _amount,
        address _tokenAddress,
        address _buyer,
        address _ethDestinationAddress
    );

    event SentToBridge(
        uint256 _orderId,
        uint256 _amount,
        address _tokenAddress,
        address _ethDestinationAddress
    );

    event WhitelistTokenAdded(address tokenAddress);
    event WhitelistTokenRemoved(address tokenAddress);

    modifier notNull(address _address) {
        require(_address != NULL_ADDRESS, "Address cannot be empty");
        _;
    }

    modifier isTokenWhitelisted(address _tokenAddress) {
        require(
            allowedTokens[_tokenAddress] == true,
            "Token is not Whitelisted"
        );
        _;
    }

    modifier isTokenNotWhitelisted(address _tokenAddress) {
        require(
            allowedTokens[_tokenAddress] != true,
            "Token is already Whitelisted"
        );
        _;
    }

    modifier onlyBridge() {
        require(
            msg.sender == address(bridgeContract),
            "Only BRIDGE Contract can call this function"
        );
        _;
    }

    modifier acceptableConversionFee(uint256 _newConversionFee) {
        require(_newConversionFee > 0, "New conversion fee cannot be zero");
        require(
            _newConversionFee < feePercentageDivider,
            "New conversion fee cannot be more than 100.00%"
        );
        _;
    }

    function initialize(uint256 _conversionFee)
        public
        initializer
        acceptableConversionFee(_conversionFee)
    {
        conversionFee = _conversionFee;
        numOrder = 0;
        lastOrderIndex = 0;
        firstOrderIndex = 0;
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
        acceptableConversionFee(_newConversionFee)
        returns (bool)
    {
        uint256 previousValue = conversionFee;
        conversionFee = _newConversionFee;

        emit ConversionFeeChanged(previousValue, conversionFee);
        return true;
    }

    function addTokenToWhitelist(address _tokenAddress)
        public
        onlyOwner
        notNull(_tokenAddress)
        isTokenNotWhitelisted(_tokenAddress)
    {
        allowedTokens[_tokenAddress] = true;
        emit WhitelistTokenAdded(_tokenAddress);
    }

    function removeTokenFromWhitelist(address _tokenAddress)
        public
        onlyOwner
        notNull(_tokenAddress)
        isTokenWhitelisted(_tokenAddress)
    {
        delete allowedTokens[_tokenAddress];
        emit WhitelistTokenRemoved(_tokenAddress);
    }

    function isTokenValid(address _tokenAddress)
        public
        view
        notNull(_tokenAddress)
        returns (bool)
    {
        bool tokenisValid = allowedTokens[_tokenAddress];
        return tokenisValid;
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
