pragma solidity ^0.5.0;

import "./zeppelin/cryptography/ECDSA.sol";

contract Auth {
    using ECDSA for bytes32;

    /**
     * Verify that msgHash is signed by signerAddr
     */
    function verifySignature(address signerAddr, bytes calldata msgHash, bytes calldata signature) external pure {
        address retAddr = keccak256(msgHash).toEthSignedMessageHash().recover(signature);
        require(retAddr == signerAddr, "Auth: The signature is not valid!");
    }
}
