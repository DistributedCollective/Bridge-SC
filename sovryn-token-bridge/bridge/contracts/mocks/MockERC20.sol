pragma solidity ^0.5.0;

import "../zeppelin/token/ERC20/ERC20.sol";
import "../zeppelin/token/ERC20/ERC20Detailed.sol";

contract MockERC20 is ERC20, ERC20Detailed {
	constructor() public
		ERC20Detailed("TST", "TST", 18) {}

	function mint(address account, uint256 amount) external {
		_mint(account, amount);
	}
}
