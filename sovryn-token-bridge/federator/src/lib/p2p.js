const { ethers } = require('ethers');
const { Network } = require('ataraxia');
const { TCPTransport } = require('ataraxia-tcp');
const { RSKKeyedAuth } = require('../vendors/RSKKeyedAuth');

class P2p {
    transport;
    net;
    logger;

    constructor(name, config, federatorsAdresses, logger) {
        this.logger = logger;
    }

    initiateP2pNetwork(name, port, peers, federatorsAdresses, privateKey) {
        this.createTransport(port, federatorsAdresses, privateKey);
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
                `A node left: ${node.id} | ${
                    this.net.nodes.length
                } total peer(s) | Leader: ${this.getLeaderId()}`
            );
        });
    }

    createTransport(port, federatorsAdresses, privateKey) {
        this.transport = new TCPTransport({
            port,
            authentication: [
                new RSKKeyedAuth({
                    getPeerAddresses: async () => federatorsAdresses,
                    signer: new ethers.Wallet(privateKey),
                }),
            ],
        });
    }

    addPeers(peers) {
        if (!this.transport) throw new Error('No transport available');
        peers.forEach((peer) => {
            if (peer.ip === '127.0.0.1' && peer.port === this.transport._port) return;
            this.transport.addManualPeer({
                host: peer.ip,
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

    async start() {
        try {
            await this.net.join();
            this.logger.info(
                `Joined federators network | Node id: ${this.net.networkId} | Port: ${this.transport.port}`
            );
        } catch (err) {
            throw new Error(err);
        }
    }

    async stop() {
        try {
            await this.net.leave();
            this.logger.info('Left federators network');
        } catch (err) {
            throw new Error(err);
        }
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
