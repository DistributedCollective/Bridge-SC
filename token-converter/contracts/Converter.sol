// SPDX-License-Identifier: MIT
pragma solidity >=0.6.0 <0.8.0;

import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/math/SafeMathUpgradeable.sol";

contract Converter is Initializable, OwnableUpgradeable, PausableUpgradeable {
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
        address finalRecipientAddress; // Final destination of the rBTC payed by the buyer
        uint256 previousOrder; // Address of the previous Order
        uint256 nextOrder; // Address of the next Order
    }

    mapping(uint256 => Order) private orders; // map of made sell orders

    uint256 constant public feePercentageDivider = 10000; // Percentage with up to 2 decimals

    event ConversionFeeChanged(uint256 previousValue, uint256 currentValue);

    event BridgeContractAddressChanged(
        address _previousAddress,
        address _currentAddress
    );

    event TokensReceived(
        address _sellerAddress,
        uint256 _orderAmount,
        address _tokenAddress
    );

    event MakeSellOrder(
        uint256 orderId,
        uint256 amount,
        address tokenAddress,
        address seller
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
            msg.sender == bridgeContractAddress,
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

    function setBridgeContractAddress(address _bridgeContractAddress)
        public
        onlyOwner
        notNull(_bridgeContractAddress)
        returns (bool)
    {
        address previousAddress = bridgeContractAddress;
        bridgeContractAddress = _bridgeContractAddress;

        emit BridgeContractAddressChanged(
            previousAddress,
            bridgeContractAddress
        );
        return true;
    }

    function onTokensReceived(
        address _sellerAddress,
        uint256 _orderAmount,
        address _tokenAddress,
        bytes32 userData
    )
        public
        onlyBridge
        whenNotPaused
        notNull(_sellerAddress)
        notNull(_tokenAddress)
        isTokenWhitelisted(_tokenAddress)
    {
        require(_orderAmount > 0, "Invalid Amount sent");

        // contrato del bridge ERC777 o receivetoken

        // TODO parse user data to obtain finalReceipientAddress
        address finalReceipientAddress = _sellerAddress;

        emit TokensReceived(_sellerAddress, _orderAmount, _tokenAddress);

        // call to make the sell orders of the received tokens
        makeSellOrder(
            _sellerAddress,
            _orderAmount,
            _tokenAddress,
            finalReceipientAddress
        );
    }

    function makeSellOrder(
        address _sellerAddress,
        uint256 _orderAmount,
        address _tokenAddress,
        address _finalRecipientAddress
    ) internal whenNotPaused {
        // returns (uint256 orderId) { ==> Return anything ??
        uint256 previousOrder = numOrder;
        numOrder.add(1);

        if (previousOrder != 0) {
            orders[previousOrder].nextOrder = numOrder;
        }

        orders[numOrder] = Order(
            _sellerAddress,
            _tokenAddress,
            _orderAmount,
            _finalRecipientAddress,
            previousOrder,
            0
        );
        emit MakeSellOrder(
            numOrder,
            orders[numOrder].orderAmount,
            orders[numOrder].tokenAddress,
            orders[numOrder].sellerAddress
        );
    }
}
