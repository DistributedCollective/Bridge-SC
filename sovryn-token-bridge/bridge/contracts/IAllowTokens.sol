pragma solidity ^0.5.0;

interface IAllowTokens {

    function getFeePerToken(address token) external view returns(uint256); 
    function isValidTokenTransfer(address tokenToUse, uint amount, uint spentToday, bool isSideToken) external view returns (bool);
    function calcMaxWithdraw(uint spentToday) external view returns (uint);
}