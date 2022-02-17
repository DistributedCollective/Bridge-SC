const { Network, AnonymousAuth } = require('ataraxia');
const { TCPTransport } = require('ataraxia-tcp');

async function launchP2pNetwork(port = 30303, peers, logger) {
    const tcpTransport = new TCPTransport({
        port,
        authentication: [new AnonymousAuth()],
    });

    peers.forEach((peer) => {
        if (peer.address === '127.0.0.1' && peer.port === port) return;
        tcpTransport.addManualPeer({
            host: peer.address,
            port: peer.port,
        });
    });

    const net = new Network({
        name: 'bridge-federators',
        transports: [tcpTransport],
    });

    net.onNodeAvailable((node) => {
        logger.info(`A new node is available: ${node.id} | ${net.nodes.length} total peer(s)`);
    });

    try {
        await net.join();
    } catch (err) {
        throw new Error(err);
    }

    logger.info(
        `Joined federators network | Peer id: ${net.networkId} | Port: ${tcpTransport.port}`
    );
}

module.exports = { launchP2pNetwork };
