pragma solidity ^0.5.0;

import "./zeppelin/cryptography/ECDSA.sol";

/// @title A authentication contract
/// @notice We are using ECDSA for signature validation
contract Auth {
    using ECDSA for bytes32;

    /// @notice Verify that msgHash is signed by signerAddr
    /// @dev It reverts if the signature is invalid
    /// @param signerAddr The address of the signer
    /// @param msgHash The message to validate
    /// @param signature The given signature to validate within the hash
    function verifySignature(address signerAddr, bytes calldata msgHash, bytes calldata signature) external pure {
        address retAddr = keccak256(msgHash).toEthSignedMessageHash().recover(signature);
        require(retAddr == signerAddr, "Auth: The signature is not valid!");
    }
}
