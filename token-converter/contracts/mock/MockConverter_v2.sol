// SPDX-License-Identifier: MIT
pragma solidity >=0.6.0 <0.8.0;

import "@openzeppelin/contracts-upgradeable/access/OwnableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/utils/PausableUpgradeable.sol";
import "@openzeppelin/contracts-upgradeable/proxy/Initializable.sol";
import "@openzeppelin/contracts-upgradeable/math/SafeMathUpgradeable.sol";

contract MockConverter_v2 is Initializable, OwnableUpgradeable, PausableUpgradeable  {
    using SafeMathUpgradeable for uint256;
    uint256 public conversionFee;
    uint256 public testPauseVar; // Borrar esto sirve solo para testear el pause ahora;


    event ConversionFeeChanged(uint256 _previousValue, uint256 _currentValue);

    function initialize(uint256 _conversionFee) public initializer {
        require(_conversionFee > 0, "Deploying error. Conversion fee is zero");
        conversionFee = _conversionFee;
        testPauseVar = 1;       // Borrar esto sirve solo para testear el pause ahora;
        __Ownable_init();
        __Pausable_init();        
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

    // Borrar esto sirve solo para testear el pause ahora;
    function incrementValueByTen(uint256 _newValueTest) public whenNotPaused {
        testPauseVar = _newValueTest.add(10);   // modified to test upgradability
    }
}
