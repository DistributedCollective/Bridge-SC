const { Network, AnonymousAuth } = require('ataraxia');
const { TCPTransport } = require('ataraxia-tcp');

class P2p {
    transport;
    net;
    logger;

    constructor(name, port = 30303, peers, logger) {
        this.logger = logger;
        this.createTransport(port);
        this.addPeers(peers);
        this.createNetwork(name);

        this.net.onNodeAvailable((node) => {
            this.logger.info(
                `A new node is available: ${node.id} | ${
                    this.net.nodes.length
                } total peer(s) | Leader: ${this.getLeaderId()}`
            );
        });

        this.net.onNodeUnavailable((node) => {
            this.logger.info(
                `A node is left: ${node.id} | ${
                    this.net.nodes.length
                } total peer(s) | Leader: ${this.getLeaderId()}`
            );
        });
    }

    createTransport(port) {
        this.transport = new TCPTransport({
            port,
            authentication: [new AnonymousAuth()],
        });
    }

    addPeers(peers) {
        peers.forEach((peer) => {
            if (peer.address === '127.0.0.1' && peer.port === this.transport._port) return;
            this.transport.addManualPeer({
                host: peer.address,
                port: peer.port,
            });
        });
    }

    createNetwork(name) {
        this.net = new Network({
            name,
            transports: [this.transport],
        });
    }

    async launch() {
        try {
            await this.net.join();
        } catch (err) {
            throw new Error(err);
        }

        this.logger.info(
            `Joined federators network | Node id: ${this.net.networkId} | Port: ${this.transport.port}`
        );
    }

    getPeerAmount() {
        return this.net.nodes.length;
    }

    isLeader() {
        return this.net.networkId === this.getLeaderId();
    }

    getLeaderId() {
        const nodeIds = this.getSortedNodeIds();
        if (nodeIds.length === 0) {
            return null;
        }
        return nodeIds[0];
    }

    getSortedNodeIds() {
        const nodeIds = this.getNodeIds();
        nodeIds.sort();
        return nodeIds;
    }

    getNodeIds() {
        const nodeIds = this.net.nodes.map((node) => node.id);
        // Ataraxia > 0.11 doesn't include current node in this.network.nodes
        if (nodeIds.indexOf(this.net.networkId) === -1) {
            nodeIds.push(this.net.networkId);
        }
        return nodeIds;
    }
}

module.exports = P2p;
