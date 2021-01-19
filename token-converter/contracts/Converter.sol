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
    uint256 public numOrder; // to store the incremental sell orders
    uint256 public lastOrderIndex;

    struct Order {
        address sellerAddress; // Sell Order maker address
        address tokenAddress; // Address of the Token
        uint256 orderAmount; // Amount of the order
        address finalReceipientAddress; // Final destination of the rBTC payed by the buyer
        uint256 previousOrder; // Address of the previous Order
        uint256 nextOrder; // Address of the next Order
    }

    mapping(uint256 => Order) public orders; // map of made sell orders

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
    event BuySellOrder(
        uint256 orderId,
        uint256 amount,
        address tokenAddress,
        address buyerAdress,
        address ethDestinationAddress
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

    modifier aceptableConversionFee(uint256 _newConversionFee) {
        require(_newConversionFee > 0, "New conversion fee cannot be zero");
        require(
            _newConversionFee < 100,
            "New conversion fee cannot be more than 100%"
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

    function onTokensMinted(
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
    ) internal whenNotPaused {  // it is necesary ?
        // returns (uint256 orderId) { ==> Return anything ??
        uint256 previousOrder = numOrder;
        numOrder = numOrder.add(1);

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

    function makeSellOrder(
        address _sellerAddress,
        uint256 _orderAmount,
        address _tokenAddress,
        address _finalReceipientAddress
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
            _finalReceipientAddress,
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

    function buySellOrder(uint256 _orderId, address _ethDestinationAddress)
        public
        whenNotPaused
        notNull(_ethDestinationAddress)
        notNull(orders[_orderId].sellerAddress)
    {
        // require(, "Wrong Amount Sent");
        uint256 previousOrder = orders[_orderId].previousOrder;
        uint256 nextOrder = orders[_orderId].nextOrder;

        if (previousOrder != 0) {
            orders[previousOrder].nextOrder = nextOrder;
        }

        if (nextOrder != 0) {
            orders[nextOrder].previousOrder = previousOrder;
        }

        emit BuySellOrder(
            _orderId,
            orders[_orderId].orderAmount,
            orders[_orderId].tokenAddress,
            msg.sender,
            _ethDestinationAddress
        );

        // transfer to bridge the rsk tokens and pass as a parameter the ethAddress
        // transfer rBtc from the buyer to orders[orderId].finalReceipientAddress
        // emit events over the transfers ?
        delete orders[_orderId];
    }

    // function getOrders(uint256 startingOrderId, uint256 qtyOrdersToReturn)
    //     public
    //     view
    //     whenNotPaused
    //     returns (Order[] memory)
    // {
    //     require(orders[startingOrderId].activeOrder, "Invalid Starting Order ID");
    //     require(qtyOrdersToReturn > 0, "Invalid qtyOrdersToReturn Value");
    //     require(qtyOrdersToReturn < 21, "qtyOrdersToReturn too big");

    //     Order[] memory availableOrders = new Order[](qtyOrdersToReturn);

    //     uint256 i = 0;
    //     uint256 tempQtyOrdersToReturn = qtyOrdersToReturn;

    //     Order memory currentOrder = orders[startingOrderId];

    //     while (i < tempQtyOrdersToReturn) {
    //         if (currentOrder.activeOrder) availableOrders[i] = currentOrder;
    //         if (currentOrder.nextOrder != 0) {
    //             currentOrder = orders[currentOrder.nextOrder];
    //             i++;
    //         } else {
    //             tempQtyOrdersToReturn = 0;
    //         }
    //     }
    //     return availableOrders;
    // }
}
