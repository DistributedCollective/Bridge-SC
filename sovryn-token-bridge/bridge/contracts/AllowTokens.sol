pragma solidity >=0.4.21 <0.6.0;

import "./zeppelin/math/SafeMath.sol";
import "./zeppelin/ownership/Ownable.sol";
import "./IAllowTokens.sol";

contract AllowTokens is IAllowTokens, Ownable {
    using SafeMath for uint256;

    address constant private NULL_ADDRESS = address(0);

    mapping (address => bool) public allowedTokens;
    bool private validateAllowedTokens;
    uint256 private maxTokensAllowed;
    uint256 private minTokensAllowed;
    uint256 public dailyLimit;

// Bridge v3 upgrade variables
// minimum amount allowed per token
    mapping (address => uint) public minAllowedToken;
// constant fee per token
    mapping (address => uint) public feeConstToken;
// maximum amount allowed per token
    mapping (address => uint) public maxAllowedToken;


    event AllowedTokenAdded(address indexed _tokenAddress);
    event AllowedTokenRemoved(address indexed _tokenAddress);
    event AllowedTokenValidation(bool _enabled);
    event MaxTokensAllowedChanged(uint256 _maxTokens);
    event MinTokensAllowedChanged(uint256 _minTokens);
    event DailyLimitChanged(uint256 dailyLimit);

// Bridge v3 upgrade events
    event FeeAndMinPerTokenChanged(address _token, uint256 _feeConst, uint256 _minAmount);
    event MaxPerTokenChanged(address _token, uint256 _maxAmount);

    modifier notNull(address _address) {
        require(_address != NULL_ADDRESS, "AllowTokens: Address cannot be empty");
        _;
    }

    constructor(address _manager) public  {
        transferOwnership(_manager);
        validateAllowedTokens = true;
        maxTokensAllowed = 100000 ether;
        minTokensAllowed = 1 ether;
        dailyLimit = 1000000 ether;
    }

    function isValidatingAllowedTokens() external view returns(bool) {
        return validateAllowedTokens;
    }

    function getMaxTokensAllowed() external view returns(uint256) {
        return maxTokensAllowed;
    }

    function getMinTokensAllowed() external view returns(uint256) {
        return minTokensAllowed;
    }

    function allowedTokenExist(address token) private view notNull(token) returns (bool) {
        return allowedTokens[token];
    }

    function isTokenAllowed(address token) public view notNull(token) returns (bool) {
        if (validateAllowedTokens) {
            return allowedTokenExist(token);
        }
        return true;
    }

    function addAllowedToken(address token) external onlyOwner {
        require(!allowedTokenExist(token), "AllowTokens: Token already exists in allowedTokens");
        allowedTokens[token] = true;
        emit AllowedTokenAdded(token);
    }

    function removeAllowedToken(address token) external onlyOwner {
        require(allowedTokenExist(token), "AllowTokens: Token does not exis  in allowedTokenst");
        allowedTokens[token] = false;
        emit AllowedTokenRemoved(token);
    }

    function enableAllowedTokensValidation() external onlyOwner {
        validateAllowedTokens = true;
        emit AllowedTokenValidation(validateAllowedTokens);
    }

    function disableAllowedTokensValidation() external onlyOwner {
        // Before disabling Allowed Tokens Validations some kind of contract validation system
        // should be implemented on the Bridge for the methods receiveTokens, tokenFallback and tokensReceived
        validateAllowedTokens = false;
        emit AllowedTokenValidation(validateAllowedTokens);
    }

    function setMaxTokensAllowed(uint256 maxTokens) external onlyOwner {
        require(maxTokens >= minTokensAllowed, "AllowTokens: Max Tokens should be equal or bigger than Min Tokens");
        maxTokensAllowed = maxTokens;
        emit MaxTokensAllowedChanged(maxTokensAllowed);
    }

    function setMinTokensAllowed(uint256 minTokens) external onlyOwner {
        require(maxTokensAllowed >= minTokens, "AllowTokens: Min Tokens should be equal or smaller than Max Tokens");
        minTokensAllowed = minTokens;
        emit MinTokensAllowedChanged(minTokensAllowed);
    }

    function changeDailyLimit(uint256 _dailyLimit) external onlyOwner {
        require(_dailyLimit >= maxTokensAllowed, "AllowTokens: Daily Limit should be equal or bigger than Max Tokens");
        dailyLimit = _dailyLimit;
        emit DailyLimitChanged(_dailyLimit);
    }

    // solium-disable-next-line max-len
    function isValidTokenTransfer(address tokenToUse, uint amount, uint spentToday, bool isSideToken) external view returns (bool) {
        if(amount > maxTokensAllowed)
            return false;
        if(amount < minAllowedToken[tokenToUse])
            return false;
        if (spentToday + amount > dailyLimit || spentToday + amount < spentToday)
           return false;
        if(!isSideToken && !isTokenAllowed(tokenToUse))
            return false;
        if(feeConstToken[tokenToUse] == 0 )
            return false;
        if(maxAllowedToken[tokenToUse] > 0) {
            if(amount > maxAllowedToken[tokenToUse]) {
                return false;
            }   
        }
        return true;
    }

    function calcMaxWithdraw(uint spentToday) external view returns (uint) {
        uint maxWithrow = dailyLimit - spentToday;
        if (dailyLimit < spentToday)
            return 0;
        if(maxWithrow > maxTokensAllowed)
            maxWithrow = maxTokensAllowed;
        return maxWithrow;
    }

// Bridge v3 upgrade functions
    function getMinPerToken(address token) external view returns(uint256) {
        return minAllowedToken[token];
    }

    function getFeePerToken(address token) public view returns(uint256) {
        return feeConstToken[token];
    }

    function setFeeAndMinPerToken(address token, uint256 _feeConst, uint256 _minAmount) external onlyOwner {
        require(_minAmount <= maxTokensAllowed, "AllowTokens: Min Tokens should be equal or smaller than Max Tokens");
        require(_minAmount >= _feeConst, "AllowTokens: Min Tokens should be equal bigger than fee");
        require(_feeConst > 0, "AllowTokens: Fee Should be> 0");
        if (maxAllowedToken[token] != 0 ) {
            require(_minAmount <= maxAllowedToken[token], "AllowTokens: Min Tokens should be equal or smaller than maxAllowedToken");
        }
        feeConstToken[token] = _feeConst;
        minAllowedToken[token] = _minAmount;
        emit FeeAndMinPerTokenChanged(token, _feeConst, _minAmount);
    }
    function setMaxPerToken(address token, uint256 _maxAmount) external onlyOwner {
        require(_maxAmount <= maxTokensAllowed, "AllowTokens: Max Tokens should be equal or smaller than Max Tokens");
        require(minAllowedToken[token] <= _maxAmount, "AllowTokens: maxAllowedToken[] should be equal or bigger than minAllowedToken[]");
        maxAllowedToken[token] = _maxAmount;
        emit MaxPerTokenChanged(token, _maxAmount);
    }
    
    function getMaxPerToken(address token) external view returns(uint256) {
        return maxAllowedToken[token];
    }


}
