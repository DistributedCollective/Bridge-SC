

function fixSignature(signature) {
    let v = parseInt(signature.slice(130, 132), 16);

    if (v < 27) {
        v += 27;
    }

    const vHex = v.toString(16);

    return signature.slice(0, 130) + vHex;
}

module.exports = {
    fixSignature
}
