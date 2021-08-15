pragma solidity ^0.5.0;

contract mockERC20Receiver {
    
    uint256 public sum = 0 ;
    event ThisSum(uint256 _sum);
    function()
        external
        payable
    {
        for(uint256 i = 0 ; i < 100 ; i++) {
            sum = sum + i ;
        }
    emit ThisSum(sum);
    }
}

