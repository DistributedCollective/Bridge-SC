// SPDX-License-Identifier: MIT
pragma solidity >=0.6.0 <0.8.0;

import "openzeppelin-solidity/contracts/access/Ownable.sol";
import "openzeppelin-solidity/contracts/utils/Pausable.sol";

contract Converter is Ownable, Pausable {
    uint256 public conversionFee;
    uint256 public testPauseVar = 1; // Borrar esto sirve solo para testear el pause ahora;

    event ConversionFeeChanged(uint256 _previousValue, uint256 _currentValue);

    constructor(uint256 _conversionFee) public {
        require(_conversionFee > 0, "Deploying error. Conversion fee is zero");
        conversionFee = _conversionFee;
    }

    function setConversionFee(uint256 _newConversionFee) public onlyOwner {
        require(_newConversionFee > 0, "New conversion fee is zero");

        uint256 previousValue = conversionFee;
        conversionFee = _newConversionFee;

        emit ConversionFeeChanged(previousValue, conversionFee);
    }

    function pauseContract() public onlyOwner whenNotPaused {
        _pause();
    }

    function unpauseContract() public onlyOwner whenPaused {
        _unpause();
    }

    function testPause(uint256 _newValueTest) public whenNotPaused {
        testPauseVar = _newValueTest;
    }
}
