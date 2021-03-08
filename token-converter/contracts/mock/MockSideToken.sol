// SPDX-License-Identifier: MIT
pragma solidity >=0.6.0 <0.8.0;

import "../ISideToken.sol";
import "../zeppelin/math/SafeMath.sol";


contract MockSideToken is ISideToken {
    using SafeMath for uint256;

    mapping(address => uint256) private _balances;

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

    function mint(address account, uint256 amount, bytes calldata, bytes calldata) external override {
        _balances[account] = _balances[account].add(amount);
    }

    function totalSupply() external view override returns (uint256) {
        return 0;
    }

    function balanceOf(address tokenHolder) public view override returns (uint256) {
        return _balances[tokenHolder];
    }

    function send(address, uint256, bytes calldata) external override {}

    function transfer(address recipient, uint256 amount) external override returns (bool) {
        address from = msg.sender;
        _move(from, from, recipient, amount, "", "");

        return true;
    }

    function allowance(address, address) external view override returns (uint256) {
        return 0;
    }

    function approve(address, uint256) external override returns (bool) {
        return true;
    }

    function transferFrom(address holder, address recipient, uint256 amount) external override returns (bool) {
        address spender = msg.sender;
        _move(spender, holder, recipient, amount, "", "");

        return true;
    }

    function _move(
        address ,
        address from,
        address to,
        uint256 amount,
        bytes memory,
        bytes memory
    )
    internal
    {
        _balances[from] = _balances[from].sub(amount, "Transfer amount exceeds balance");
        _balances[to] = _balances[to].add(amount);
    }
}
