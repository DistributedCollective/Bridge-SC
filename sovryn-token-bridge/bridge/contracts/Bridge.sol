pragma solidity ^0.5.0;

// Import base Initializable contract
import "./zeppelin/upgradable/Initializable.sol";
// Import interface and library from OpenZeppelin contracts
import "./zeppelin/upgradable/utils/ReentrancyGuard.sol";
import "./zeppelin/upgradable/lifecycle/UpgradablePausable.sol";
import "./zeppelin/upgradable/ownership/UpgradableOwnable.sol";

import "./zeppelin/introspection/IERC1820Registry.sol";
import "./zeppelin/token/ERC777/IERC777Recipient.sol";
import "./zeppelin/token/ERC20/IERC20.sol";
import "./zeppelin/token/ERC20/SafeERC20.sol";
import "./zeppelin/utils/Address.sol";
import "./zeppelin/math/SafeMath.sol";

import "./IBridge.sol";
import "./ISideToken.sol";
import "./ISideTokenFactory.sol";
import "./IAllowTokens.sol";
import "./Utils.sol";

contract Bridge is Initializable, IBridge, IERC777Recipient, UpgradablePausable, UpgradableOwnable, ReentrancyGuard {
    using SafeMath for uint256;
    using SafeERC20 for IERC20;
    using Address for address;

    address constant private NULL_ADDRESS = address(0);
    bytes32 constant private NULL_HASH = bytes32(0);
    IERC1820Registry constant private erc1820 = IERC1820Registry(0x1820a4B7618BdE71Dce8cdc73aAB6C95905faD24);

    address private federation;
    uint256 private feePercentage;
    string public symbolPrefix;
    uint256 public lastDay;
    uint256 public spentToday;

    mapping (address => ISideToken) public mappedTokens; // OirignalToken => SideToken
    mapping (address => address) public originalTokens; // SideToken => OriginalToken
    mapping (address => bool) public knownTokens; // OriginalToken => true
    mapping(bytes32 => bool) public processed; // ProcessedHash => true
    IAllowTokens public allowTokens;
    ISideTokenFactory public sideTokenFactory;
    //Bridge_v1 variables
    bool public isUpgrading;
    uint256 constant public feePercentageDivider = 10000; // Porcentage with up to 2 decimals
    bool private alreadyRun;
    //Bridge_v3 variables
    bool public initialPrefixSetup;
    bool public isSuffix;
    bool private ethFirstTransfer;
    uint256 public ethFeeCollected;
    address private WETHAddr;
    string private nativeTokenSymbol;
    //address public aggregatorAddr;

    event FederationChanged(address _newFederation);
    event SideTokenFactoryChanged(address _newSideTokenFactory);
    event Upgrading(bool isUpgrading);
    //event AllowTokenChanged(address _newAllowToken);
    //event PrefixUpdated(bool _isSuffix, string _prefix);

// We are not using this initializer anymore because we are upgrading.
//    function initialize(
//        address _manager,
//        address _federation,
//        address _allowTokens,
//        address _sideTokenFactory,
//        string memory _symbolPrefix
//    ) public initializer {
//        UpgradableOwnable.initialize(_manager);
//        UpgradablePausable.initialize(_manager);
//        symbolPrefix = _symbolPrefix;
//        allowTokens = AllowTokens(_allowTokens);
//        _changeSideTokenFactory(_sideTokenFactory);
//        _changeFederation(_federation);
//        //keccak256("ERC777TokensRecipient")
//        erc1820.setInterfaceImplementer(address(this), 0xb281fc8c12954d22544db45de3159a39272895b169a852b314f9cc762e44c53b, address(this));
//    }

    function version() external pure returns (string memory) {
        return "v3";
    }

    modifier onlyFederation() {
       require(msg.sender == federation, "Bridge: Sender not Federation");
       _;
    }

    modifier whenNotUpgrading() {
        require(!isUpgrading, "Bridge: Upgrading");
        _;
    }

    function acceptTransfer(
        address tokenAddress,
        address receiver,
        uint256 amount,
        string calldata symbol,
        bytes32 blockHash,
        bytes32 transactionHash,
        uint32 logIndex,
        uint8 decimals,
        uint256 granularity
    ) external returns(bool) {
        return _acceptTransfer(tokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, "");
    }

    function acceptTransferAt(
        address tokenAddress,
        address receiver,
        uint256 amount,
        string calldata symbol,
        bytes32 blockHash,
        bytes32 transactionHash,
        uint32 logIndex,
        uint8 decimals,
        uint256 granularity,
        bytes calldata userData
    ) external returns(bool) {
        return _acceptTransfer(tokenAddress, receiver, amount, symbol, blockHash, transactionHash, logIndex, decimals, granularity, userData);
    }

    function _acceptTransfer(
        address tokenAddress,
        address receiver,
        uint256 amount,
        string memory symbol,
        bytes32 blockHash,
        bytes32 transactionHash,
        uint32 logIndex,
        uint8 decimals,
        uint256 granularity,
        bytes memory userData
    ) internal onlyFederation whenNotPaused nonReentrant returns(bool) {
        require(tokenAddress != NULL_ADDRESS, "Bridge: Token is null");
        require(receiver != NULL_ADDRESS, "Bridge: Receiver is null");
        require(amount > 0, "Bridge: Amount 0");
        require(bytes(symbol).length > 0, "Bridge: Empty symbol");
        require(blockHash != NULL_HASH, "Bridge: BlockHash is null");
        require(transactionHash != NULL_HASH, "Bridge: Transaction is null");
        require(decimals <= 18, "Bridge: Decimals bigger 18");
        require(Utils.granularityToDecimals(granularity) <= 18, "Bridge: invalid granularity");

        _processTransaction(blockHash, transactionHash, receiver, amount, logIndex);

        if (knownTokens[tokenAddress]) {
            _acceptCrossBackToToken(receiver, tokenAddress, decimals, granularity, amount);
        } else {
            _acceptCrossToSideToken(receiver, tokenAddress, decimals, granularity, amount, symbol, userData);
        }
        return true;
    }

    function _acceptCrossToSideToken(
        address receiver,
        address tokenAddress,
        uint8 decimals,
        uint256 granularity,
        uint256 amount,
        string memory symbol,
        bytes memory userData
    ) private {
        (uint256 calculatedGranularity,uint256 formattedAmount) = Utils.calculateGranularityAndAmount(decimals, granularity, amount);
        ISideToken sideToken = mappedTokens[tokenAddress];
        if (address(sideToken) == NULL_ADDRESS) {
            sideToken = _createSideToken(tokenAddress, symbol, calculatedGranularity);
        } else {
            require(calculatedGranularity == sideToken.granularity(), "Bridge: Granularity differ from side token");
        }
        sideToken.mint(receiver, formattedAmount, userData, "");

        if (receiver.isContract()) {
            (bool success, bytes memory errorData) = receiver.call(
                abi.encodeWithSignature("onTokensMinted(uint256,address,bytes)", formattedAmount, sideToken, userData)
            );
            if (!success) {
                emit ErrorTokenReceiver(errorData);
            }
        }

        emit AcceptedCrossTransfer(tokenAddress, receiver, amount, decimals, granularity, formattedAmount, 18, calculatedGranularity, userData);
    }

    function _acceptCrossBackToToken(address receiver, address tokenAddress, uint8 decimals, uint256 granularity, uint256 amount) private {
        require(decimals == 18, "Bridge: Invalid decimals cross back");
        //As side tokens are ERC777 we need to convert granularity to decimals
        (uint8 calculatedDecimals, uint256 formattedAmount) = Utils.calculateDecimalsAndAmount(tokenAddress, granularity, amount);
        //// Bridge v3 upgrade functions
        if (tokenAddress == WETHAddr) {
            address payable payableReceiver = address(uint160(receiver));
            payableReceiver.transfer(amount);
        }
        else {
            IERC20(tokenAddress).safeTransfer(receiver, formattedAmount);
        }
        emit AcceptedCrossTransfer(tokenAddress, receiver, amount, decimals, granularity, formattedAmount, calculatedDecimals, 1, "");
    }

    /**
    * ERC-20 tokens approve and transferFrom pattern
    * See https://eips.ethereum.org/EIPS/eip-20#transferfrom
    */
    function receiveTokensAt(
        address tokenToUse,
        uint256 amount,
        address receiver,
        bytes calldata extraData
    ) external returns(bool) {
        return _receiveTokens(tokenToUse, amount, receiver, extraData);
    }

    /**
    * ERC-20 tokens approve and transferFrom pattern
    * See https://eips.ethereum.org/EIPS/eip-20#transferfrom
    */
    function receiveTokens(address tokenToUse, uint256 amount) external returns(bool) {
        return _receiveTokens(tokenToUse, amount, _msgSender(), "");
    }

    /**
     * ERC-20 tokens approve and transferFrom pattern
     * See https://eips.ethereum.org/EIPS/eip-20#transferfrom
     */
    function _receiveTokens(
        address tokenToUse,
        uint256 amount,
        address receiver,
        bytes memory extraData
    ) private whenNotUpgrading whenNotPaused nonReentrant returns(bool) {
        require(tokenToUse != WETHAddr, "Bridge: Cannot transfer WETH");
        //Transfer the tokens on IERC20, they should be already Approved for the bridge Address to use them
        IERC20(tokenToUse).safeTransferFrom(_msgSender(), address(this), amount);
        crossTokens(tokenToUse, receiver, amount, extraData);
        return true;
    }

    /**
     * ERC-777 tokensReceived hook allows to send tokens to a contract and notify it in a single transaction
     * See https://eips.ethereum.org/EIPS/eip-777#motivation for details
     */
    function tokensReceived (
        address operator,
        address from,
        address to,
        uint amount,
        bytes calldata userData,
        bytes calldata
    ) external whenNotPaused whenNotUpgrading {
        //Hook from ERC777address
       if(operator == address(this)) return; // Avoid loop from bridge calling to ERC77transferFrom
        require(to == address(this), "Bridge: Not to address");
       address tokenToUse = _msgSender();
       require(tokenToUse != WETHAddr, "Bridge: Cannot transfer WETH");
       //This can only be used with trusted contracts
       crossTokens(tokenToUse, from, amount, userData);
    }

    function crossTokens(address tokenToUse, address receiver, uint256 amount, bytes memory userData) private {
        bool isASideToken = originalTokens[tokenToUse] != NULL_ADDRESS;
    //V3 upgrade change global token fee to per token fee
        uint256 fee = allowTokens.getFeePerToken(tokenToUse);
        if(fee>0 ){
            if (tokenToUse== WETHAddr ) {
                ethFeeCollected = ethFeeCollected.add(fee);
            }
            else {
            //Send the payment to the MultiSig of the Federation
                IERC20(tokenToUse).safeTransfer(owner(), fee);
            }
        }
        uint256 amountMinusFees = amount.sub(fee);
        if (isASideToken) {
            verifyWithAllowTokens(tokenToUse, amount, isASideToken);
            //Side Token Crossing
            ISideToken(tokenToUse).burn(amountMinusFees, userData);
            // solium-disable-next-line max-len
            emit Cross(originalTokens[tokenToUse], receiver, amountMinusFees, ISideToken(tokenToUse).symbol(), userData, ISideToken(tokenToUse).decimals(), ISideToken(tokenToUse).granularity());
        }
        else {
            //Main Token Crossing
            uint8 decimals;
            uint256 granularity;
            string memory symbol;

            knownTokens[tokenToUse] = true;
            if (tokenToUse== WETHAddr ) {
                decimals = 18;
                granularity = 1;
                symbol = nativeTokenSymbol;
            }
            else {
                ( decimals, granularity,  symbol) = Utils.getTokenInfo(tokenToUse);
            }
            uint formattedAmount = amount;
            if(decimals != 18) {
                formattedAmount = amount.mul(uint256(10)**(18-decimals));
            }
            //We consider the amount before fees converted to 18 decimals to check the limits
            verifyWithAllowTokens(tokenToUse, formattedAmount, isASideToken);
            emit Cross(tokenToUse, receiver, amountMinusFees, symbol, userData, decimals, granularity);
        }     
    }

    function _createSideToken(address token, string memory symbol, uint256 granularity) private returns (ISideToken sideToken){
        initialPrefixSetup = true;
        string memory newSymbol;
        if(!isSuffix) {
             newSymbol = string(abi.encodePacked(symbolPrefix, symbol));
        }
        else {
             newSymbol = string(abi.encodePacked(symbol, symbolPrefix));    
        }
        
        address sideTokenAddress = sideTokenFactory.createSideToken(newSymbol, newSymbol, granularity);
        sideToken = ISideToken(sideTokenAddress);
        mappedTokens[token] = sideToken;
        originalTokens[sideTokenAddress] = token;
        emit NewSideToken(sideTokenAddress, token, newSymbol, granularity);
        return sideToken;
    }

    function verifyWithAllowTokens(address tokenToUse, uint256 amount, bool isASideToken) private  {
        // solium-disable-next-line security/no-block-members
        if (now > lastDay + 24 hours) {
            // solium-disable-next-line security/no-block-members
            lastDay = now;
            spentToday = 0;
        }
        require(allowTokens.isValidTokenTransfer(tokenToUse, amount, spentToday, isASideToken), "Bridge: Bigger than limit");
        spentToday = spentToday.add(amount);
    }

    function getTransactionId(
        bytes32 _blockHash,
        bytes32 _transactionHash,
        address _receiver,
        uint256 _amount,
        uint32 _logIndex
    )
        public pure returns(bytes32)
    {
        return keccak256(abi.encodePacked(_blockHash, _transactionHash, _receiver, _amount, _logIndex));
    }

    function _processTransaction(
        bytes32 _blockHash,
        bytes32 _transactionHash,
        address _receiver,
        uint256 _amount,
        uint32 _logIndex
    )
        private
    {
        bytes32 compiledId = getTransactionId(_blockHash, _transactionHash, _receiver, _amount, _logIndex);
        require(!processed[compiledId], "Bridge: Already processed");
        processed[compiledId] = true;
    }

    // function setFeePercentage(uint amount) external onlyOwner whenNotPaused {
    //     require(amount < (feePercentageDivider/10), "Bridge: bigger than 10%");
    //     feePercentage = amount;
    //     emit FeePercentageChanged(feePercentage);
    // }

    // function getFeePercentage() external view returns(uint) {
    //     return feePercentage;
    // }

    function calcMaxWithdraw() external view returns (uint) {
        uint spent = spentToday;
        // solium-disable-next-line security/no-block-members
        if (now > lastDay + 24 hours)
            spent = 0;
        return allowTokens.calcMaxWithdraw(spent);
    }

  function changeFederation(address newFederation) external onlyOwner returns(bool) {
        _changeFederation(newFederation);
        return true;
    }

    function _changeFederation(address newFederation) internal {
        require(newFederation != NULL_ADDRESS, "Bridge: Federation is empty");
        federation = newFederation;
        emit FederationChanged(federation);
    }

    function getFederation() external view returns(address) {
        return federation;
    }

    function changeSideTokenFactory(address newSideTokenFactory) external onlyOwner returns(bool) {
        _changeSideTokenFactory(newSideTokenFactory);
        return true;
    }

    function _changeSideTokenFactory(address newSideTokenFactory) internal {
        require(newSideTokenFactory != NULL_ADDRESS, "Bridge: SideTokenFactory is empty");
        sideTokenFactory = ISideTokenFactory(newSideTokenFactory);
        emit SideTokenFactoryChanged(newSideTokenFactory);
    }

    function startUpgrade() external onlyOwner {
        isUpgrading = true;
        emit Upgrading(isUpgrading);
    }

    function endUpgrade() external onlyOwner {
        isUpgrading = false;
        emit Upgrading(isUpgrading);
    }

//// Bridge v3 upgrade functions
    function recieveEthAt(address _receiver, bytes calldata _extraData) external payable {
        require(msg.value > 0  && !(Address.isContract(msg.sender)) && (WETHAddr != address(0)), "Set WETHAddr. Send not from SC");
        if (!ethFirstTransfer) {
            ethFirstTransfer = true;
        }
        crossTokens(WETHAddr, _receiver, msg.value, _extraData);
    }
    //     if(aggregatorAddr != address(0)){
    //         crossTokens(WETHAddr, aggregatorAddr, msg.value, abi.encodePacked(msg.sender));
    //     }
    //     else {
    //         bytes memory _userData = "";        
    //         crossTokens(WETHAddr, msg.sender, msg.value, _userData);
    //     }
    // }
    // function setAggregatorAddr(address _aggregatorAddr) external onlyOwner {
    //     aggregatorAddr = _aggregatorAddr;
    // }

    function setWETHAddress(address _WETHAddr) external onlyOwner {
        require(_WETHAddr != address(0) && !ethFirstTransfer , "No set WETHAddr AF 1st transfer");
        //require(!ethFirstTransfer, "cannot change WETHAddr after first transfer");
        WETHAddr = _WETHAddr;
    }

    function changeAllowTokens(address newAllowTokens) external onlyOwner returns(bool) {
        _changeAllowTokens(newAllowTokens);
        return true;
    }

    function _changeAllowTokens(address newAllowTokens) internal {
        require(newAllowTokens != NULL_ADDRESS, "Bridge: newAllowTokens is empty");
        allowTokens = IAllowTokens(newAllowTokens);
        //emit AllowTokenChanged(newAllowTokens);
    }
    function initialSymbolPrefixSetup(bool _isSuffix, string calldata _prefix) external onlyOwner{
        require(!initialPrefixSetup, "Bridge: initialPrefixSetup Done");
        isSuffix = _isSuffix;
        symbolPrefix = _prefix;
        //emit PrefixUpdated(isSuffix, _prefix);
    }

    function withdrawAllEthFees(address payable _to) public payable onlyOwner {
        require(address(this).balance >= ethFeeCollected);
        ethFeeCollected = 0;
        _to.transfer(ethFeeCollected);
    }

    function setNativeTokenSymbol(string calldata _nativeTokenSymbol) external onlyOwner {
        nativeTokenSymbol = _nativeTokenSymbol;
    }

    function getNativeTokenSymbol() external view returns(string memory) {
        return nativeTokenSymbol;
    }

    // Commented because it is unused for us and need decrease contract size
    //This method is only to recreate the USDT and USDC tokens on rsk without granularity restrictions.
//    function clearSideToken() external onlyOwner returns(bool) {
//        require(!alreadyRun, "already done");
//        alreadyRun = true;
//        address payable[4] memory sideTokens = [
//            0xe506F698b31a66049BD4653ed934E7a07Cbc5549,
//            0x5a42221D7AaE8e185BC0054Bb036D9757eC18857,
//            0xcdc8ccBbFB6407c53118fE47259e8d00C81F42CD,
//            0x6117C9529F15c52e2d3188d5285C745B757b5825
//        ];
//        for (uint i = 0; i < sideTokens.length; i++) {
//            address originalToken = address(originalTokens[sideTokens[i]]);
//            originalTokens[sideTokens[i]] = NULL_ADDRESS;
//            mappedTokens[originalToken] = ISideToken(NULL_ADDRESS);
//        }
//        return true;
//    }

}
