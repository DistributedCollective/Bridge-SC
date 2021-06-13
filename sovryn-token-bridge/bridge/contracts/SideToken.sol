pragma solidity ^0.5.0;

import "./zeppelin/token/ERC777/ERC777.sol";
import "./IERC677Receiver.sol";
import "./ISideToken.sol";

contract SideToken is ISideToken, ERC777 {
    using Address for address;
    using SafeMath for uint256;

    address public minter;
    uint256 private _granularity;
    bytes32 constant private NULL_HASH = bytes32(0);

    event Transfer(address,address,uint256,bytes);

    constructor(string memory _tokenName, string memory _tokenSymbol, address _minterAddr, uint256 _newGranularity)
    ERC777(_tokenName, _tokenSymbol, new address[](0)) public {
        require(_minterAddr != address(0), "SideToken: Minter address is null");
        require(_newGranularity >= 1, "SideToken: Granularity must be equal or bigger than 1");
        minter = _minterAddr;
        _granularity = _newGranularity;
    }

    modifier onlyMinter() {
        require(_msgSender() == minter, "SideToken: Caller is not the minter");
        _;
    }

    function mint(
        address account,
        uint256 amount,
        bytes calldata userData,
        bytes calldata operatorData
    )
    external onlyMinter
    {
        if(userData == NULL_HASH) {
            _mint(_msgSender(), account, amount, userData, operatorData);
        }
        else super._mint(_msgSender(), account, amount, userData, operatorData);
        }
    }

    /**
    * @dev ERC677 transfer token with additional data if the recipient is a contact.
    * @param recipient The address to transfer to.
    * @param amount The amount to be transferred.
    * @param data The extra data to be passed to the receiving contract.
    */
    function transferAndCall(address recipient, uint amount, bytes calldata data)
        external returns (bool success)
    {
        address from = _msgSender();

        _send(from, from, recipient, amount, data, "", false);
        emit Transfer(from, recipient, amount, data);
        IERC677Receiver(recipient).onTokenTransfer(from, amount, data);
        return true;
    }

    function granularity() public view returns (uint256) {
        return _granularity;
    }

    /**
    * @dev enable mint to non ERC777 interface contract if userData is empty.
    */    
    function _mint(
    address operator,
    address account,
    uint256 amount,
    bytes memory userData,
    bytes memory operatorData
    )
    internal
    {
        require(account != address(0), "ERC777: mint to zero address");

        // Update state variables
        _totalSupply = _totalSupply.add(amount);
        _balances[account] = _balances[account].add(amount);

        _callTokensReceived(operator, address(0), account, amount, userData, operatorData, false);

        emit Minted(operator, account, amount, userData, operatorData);
        emit Transfer(address(0), account, amount);
    }

}