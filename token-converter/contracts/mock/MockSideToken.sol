// SPDX-License-Identifier: MIT
pragma solidity >=0.6.0 <0.8.0;

import "../ISideToken.sol";

contract MockSideToken is ISideToken {

    function name() external view override returns (string memory) {
        return "SideToken";
    }

    function symbol() external view override returns (string memory) {
        return "ST";
    }

    function decimals() external pure override returns (uint8) {
        return 18;
    }

    function granularity() external view override returns (uint256) {
        return 1;
    }

    function burn(uint256, bytes calldata) external override {}

    function mint(address, uint256, bytes calldata, bytes calldata) external override {}

    function totalSupply() external view override returns (uint256) {
        return 0;
    }

    function balanceOf(address) external view override returns (uint256) {
        return 0;
    }

    function send(address, uint256, bytes calldata) external override {}

    function transfer(address , uint256) external override returns (bool) {
        return true;
    }

    function allowance(address, address) external view override returns (uint256) {
        return 0;
    }

    function approve(address, uint256) external override returns (bool) {
        return true;
    }

    function transferFrom(address, address, uint256) external override returns (bool) {
        return true;
    }

}
