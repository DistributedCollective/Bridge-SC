pragma solidity ^0.5.0;

interface ISideTokenFactory {

    function createSideToken(string calldata name, string calldata symbol, uint256 granularity) external returns(address);

    event SideTokenCreated(address indexed sideToken, string symbol, uint256 granularity);
}