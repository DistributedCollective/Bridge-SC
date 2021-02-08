// SPDX-License-Identifier: MIT
pragma solidity >=0.6.0 <0.8.0;

import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/math/SafeMathUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/ReentrancyGuardUpgradeable.sol";
import "./IBridge.sol";
import "./ISideToken.sol";
import "./ITokenReceiver.sol";

contract Converter is
    Initializable,
    OwnableUpgradeable,
    PausableUpgradeable,
    ReentrancyGuardUpgradeable,
    ITokenReceiver
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

    event SentToReceiver(
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
        ITokenReceiver.initialize();
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

    function onTokensMinted(
        uint256 _orderAmount,
        address _tokenAddress,
        bytes calldata _userData
    )
        external
        override
        onlyBridge
        whenNotPaused
        notNull(_tokenAddress)
        isTokenWhitelisted(_tokenAddress)
    {
        require(_orderAmount > 0, "Invalid Amount sent");

        // contrato del bridge ERC777 o receivetoken
        address recipient = decodeAddress(_userData);

        emit TokensReceived(recipient, _orderAmount, _tokenAddress);

        // call to make the sell orders of the received tokens
        makeSellOrder(_orderAmount, _tokenAddress, recipient);
    }

    function decodeAddress(bytes memory data) private pure returns (address) {
        address addr = abi.decode(data, (address));
        require(addr != NULL_ADDRESS, "Converter: Error decoding extraData");
        return addr;
    }

    function makeSellOrder(
        uint256 _orderAmount,
        address _tokenAddress,
        address _recipient
    ) private whenNotPaused {
        uint256 previousOrder = lastOrderIndex;
        numOrder = numOrder.add(1);
        lastOrderIndex = numOrder;

        if (previousOrder != 0) {
            orders[previousOrder].nextOrder = numOrder;
        } else {
            firstOrderIndex = numOrder;
        }

        orders[numOrder] = Order(
            _tokenAddress,
            _orderAmount,
            _orderAmount,
            _recipient,
            previousOrder,
            0
        );

        emit MakeSellOrder(
            numOrder,
            orders[numOrder].orderAmount,
            orders[numOrder].tokenAddress,
            orders[numOrder].recipient
        );
    }

    /// @dev This function is exclusively for offchain query
    /// It will return 2 arrays, one for the orderIds and the other with the remaining amounts of each order

    function getSellOrders(uint256 fromOrder, uint256 qtyToReturn)
        public
        view
        whenNotPaused
        returns (uint256[] memory, uint256[] memory)
    {
        require(qtyToReturn > 0, "qtyToReturn must be greater than ZERO");
        require(lastOrderIndex != 0, "No orders to retrieve");
        require(
            orders[fromOrder].recipient != NULL_ADDRESS,
            "Invalid FROM Order parameter"
        );

        uint256[] memory ordersAmounts = new uint256[](qtyToReturn);
        uint256[] memory ordersIds = new uint256[](qtyToReturn);

        Order memory sellOrder = orders[fromOrder];
        uint256 nextOrder;
        uint256 currentOrderNumber;
        uint256 index = 0;

        while (sellOrder.nextOrder != 0 && index < qtyToReturn) {
            nextOrder = sellOrder.nextOrder;
            currentOrderNumber = orders[nextOrder].previousOrder;
            ordersIds[index] = currentOrderNumber;
            ordersAmounts[index] = sellOrder.remainingAmount;
            sellOrder = orders[nextOrder];
            index = index.add(1);
        }

        if (sellOrder.nextOrder == 0 && index < qtyToReturn) {
            ordersIds[index] = lastOrderIndex;
            ordersAmounts[index] = orders[lastOrderIndex].remainingAmount;
        }

        return (ordersIds, ordersAmounts);
    }

    function updateOrdersMap(Order memory order, uint256 orderId)
        internal
        returns (bool)
    {
        uint256 previousOrder = order.previousOrder;
        uint256 nextOrder = order.nextOrder;

        // TODO: this can be improved by using firstIndex and lastIndex
        // Order filled completely, must be removed
        if (previousOrder == 0) {
            // It's the FIRST one in the map
            if (nextOrder == 0) {
                // It's the only one in the map, no next
                lastOrderIndex = 0;
                firstOrderIndex = 0;
            } else {
                // It has SUBSEQUENTS orders
                firstOrderIndex = orders[orderId].nextOrder;
                orders[nextOrder].previousOrder = 0;
            }
        } else {
            // It's NOT THE FIRST
            if (nextOrder == 0) {
                // It's the LAST in the map
                lastOrderIndex = previousOrder;
                orders[previousOrder].nextOrder = 0;
            } else {
                // It's NOT THE LAST
                orders[previousOrder].nextOrder = order.nextOrder;
                orders[nextOrder].previousOrder = order.previousOrder;
            }
        }
        delete orders[orderId];
        return true;
    }

    function takeSellOrder(
        uint256 orderId,
        uint256 amountToBuy, // qty tokens to buy
        address destinationAddress,
        bytes calldata signature,
        bytes calldata extraData // public
    )
        external
        payable
        whenNotPaused
        nonReentrant
        notNull(destinationAddress)
        notNull(orders[orderId].tokenAddress)
    {
        require(amountToBuy > 0, "Amount to buy must be greater than 0");

        Order memory order = orders[orderId];
        require(
            amountToBuy <= order.remainingAmount,
            "Amount to buy must be equal or less than remaining tokens"
        );

        uint256 priceWithDiscount =
            amountToBuy.sub(
                ((amountToBuy).mul(conversionFee)).div(feePercentageDivider)
            );
        require(
            msg.value >= priceWithDiscount,
            "Transferred Amount is less than expected"
        );

        order.remainingAmount = order.remainingAmount.sub(amountToBuy);
        orders[orderId].remainingAmount = order.remainingAmount;

        bool calledOK;
        if (order.remainingAmount == 0) {
            calledOK = updateOrdersMap(order, orderId);
            require(calledOK, "Error when updating orders map");
        }

        // require(
        //     ISideToken(order.tokenAddress).approve(
        //         address(bridgeContract),
        //         amountToBuy
        //     ),
        //     "Converter: Fail Approval"
        // );
        // calledOK = bridgeContract.receiveTokensAt(
        //     order.tokenAddress,
        //     amountToBuy,
        //     ethDestinationAddress,
        //     signature,
        //     extraData
        // );
        // require(calledOK, "Error when sending to the bridge");
        require(
            ISideToken(order.tokenAddress).transfer(
                destinationAddress,
                amountToBuy
            ),
            "Converter: Fail transfer"
        );

        emit SentToReceiver(
            orderId,
            amountToBuy,
            order.tokenAddress,
            destinationAddress
        );

        uint256 sendBackAmount; // amount to send back to the LP because it was bigger than the order
        if (msg.value > priceWithDiscount) {
            sendBackAmount = msg.value.sub(priceWithDiscount);
            (calledOK, ) = msg.sender.call{value: sendBackAmount}("");
            require(calledOK, "Error sending back to the Liquidity provider");
        }

        (calledOK, ) = order.recipient.call{value: priceWithDiscount}("");
        require(calledOK, "Error sending to seller rsk address");
        emit TakeSellOrder(
            orderId,
            amountToBuy,
            order.tokenAddress,
            msg.sender,
            destinationAddress
        );
    }
}
