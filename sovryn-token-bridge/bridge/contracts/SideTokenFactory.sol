pragma solidity ^0.5.0;

import "./zeppelin/ownership/Secondary.sol";
import "./ISideTokenFactory.sol";
import "./SideToken.sol";



contract SideTokenFactory is ISideTokenFactory, Secondary {
    event TokenAttributesSet(string indexed fromTokenSymbol, string indexed toTokenSymbol, string indexed toTokenName);
    event SideTokenCreated(address indexed sideToken, string indexed symbol, string indexed name, address minter, uint256 granularity);

    // Mapping from fromTokenSymbol => [toTokenSymbol, toTokenName]
    mapping(string => TokenAttributes) public tokenAttributesConversion;

    struct TokenAttributes {
        string toTokenSymbol;
        string toTokenName;
    }

    // Set the mapping for token symbol and name conversion
    function setTokenAttributesConversion(string calldata fromTokenSymbol, string calldata toTokenSymbol, string calldata toTokenName) external onlyPrimary {
        require(bytes(fromTokenSymbol).length != 0, "fromTokenSymbol must not be empty");
        require(bytes(toTokenSymbol).length != 0, "toTokenSymbol must not be empty");
        tokenAttributesConversion[fromTokenSymbol] = TokenAttributes({
            toTokenSymbol: toTokenSymbol,
            toTokenName: toTokenName
        });
        emit TokenAttributesSet(fromTokenSymbol, toTokenSymbol, toTokenName);
    }

    function createSideToken(string calldata name, string calldata symbol, uint256 granularity) external onlyPrimary returns(address) {
        require(bytes(symbol).length != 0, "Side token symbol must not be empty");
        require(bytes(name).length != 0, "Side token name must not be empty");
        TokenAttributes memory attrs = tokenAttributesConversion[symbol];       
        string memory finalSymbol = bytes(attrs.toTokenSymbol).length != 0 ? attrs.toTokenSymbol : symbol;
        string memory finalName = bytes(attrs.toTokenName).length != 0 ? attrs.toTokenName : name;
        address minter = primary();
        address sideToken = address(new SideToken(finalName, finalSymbol, minter, granularity));
        emit SideTokenCreated(sideToken, finalSymbol, finalName, minter,granularity);
        return sideToken;
    }
}