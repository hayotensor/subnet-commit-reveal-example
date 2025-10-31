# Commit-Reveal Example Subnet

This repository is built on top of the Hypertensor Subnetwork Template.

This is unaudited and lightly tested. For production use, more test cases are required.

This is an example subnet that utilizes a commit-reveal schema to ensure we know peers performed the necessary work in the previous epochs to obtain scores of each peer.

---

## Commit-Reveal Flow

![alt text](https://raw.githubusercontent.com/hayotensor/subnet-commit-reveal-example/refs/heads/main/consensus-commit-reveal.png "Subnet commit-reveal flow")

---

## Full Documentation

https://docs.hypertensor.org

## Installation From source

### From source

To install this container from source, simply run the following:

```
git clone https://github.com/hayotensor/subnet-commit-reveal-example.git
cd mesh
python -m venv .venv
source .venv/bin/activate
pip install .
```
---
This documentation focuses on running a subnet with a commit-reveal schema locally.

## Running Nodes Locally

- Replace port 31330 with your port of choice.
- Replace `{your_ip}` with your IP.

### Nodes
The following examples uses `--no_blockchain_rpc` which doesn't require a blockchain RPC connection to run locally.

#### Start DHT / Start Node

This will start a new subnet (fresh swarm as initial node/bootnode and server in one)
```bash
mesh-server-mock \
--host_maddrs /ip4/0.0.0.0/tcp/31330 /ip4/0.0.0.0/udp/31330/quic \
--announce_maddrs /ip4/{your_ip}/tcp/31330 /ip4/{your_ip}/udp/31330/quic \
--identity_path bootnode.id \
--new_swarm  \
--subnet_id 1 --subnet_node_id 6 \
--no_blockchain_rpc
```

#### Join DHT / Start Node
```bash
mesh-server-mock \
--host_maddrs /ip4/0.0.0.0/tcp/31331 /ip4/0.0.0.0/udp/31331/quic \
--announce_maddrs /ip4/{your_ip}/tcp/31331 /ip4/{your_ip}/udp/31331/quic \
--identity_path alith.id \
--subnet_id 1 --subnet_node_id 1 \
--no_blockchain_rpc
```
---

##### Add more nodes by using the following test `identity_path`'s:
See `substrate/mock/chain_functions.py` to view the hardcoded `peer_id` → `subnet_node_id` values.

- `charleth.id`
- `dorothy.id`
- `ethan.id`
- `faith.id`

Note: When adding new nodes, see `substrate/mock/chain_functions.py` to ensure you include those nodes in the hardcoded data.

See the <b>Todo</b> list below.

---
## Running Nodes Locally With Local Blockchain

The following example will use Alith as the subnet owner and as the node example (registering and running the node). To add more nodes for testing with a running local blockchain, see `mesh/mesh_cli/hypertensor/README.md` to view each test identity path, it's hotkeys, coldkeys, and their peer IDs.

See `mesh/mesh_cli/hypertensor/node/register.py` to register more test accounts.

##### For testing with a running local blockchain
1. Register subnet
2. Register at least 3 nodes
3. Run the nodes
4. Activate the subnet

Once the subnet is activated, consensus will begin on the following epoch between all of the nodes in the subnet.

#### Register a subnet:
With Alith's coldkey as the owner and with Alith, Baltathar, Charleth, and Dorothy as the initial coldkeys:
```bash
register-subnet \
  --max_cost 100.00 \
  --name subnet-1 \
  --repo github.com/subnet-1 \
  --description "artificial intelligence" \
  --misc "cool subnet" \
  --churn_limit 64 \
  --min_stake 100.00 \
  --max_stake  1000.00 \
  --delegate_stake_percentage 0.1 \
  --subnet_node_queue_epochs 10 \
  --idle_classification_epochs 10 \
  --included_classification_epochs 10 \
  --max_node_penalties 10 \
  --initial_coldkeys "0xf24FF3a9CF04c71Dbc94D0b566f7A27B94566cac" "0x3Cd0A705a2DC65e5b1E1205896BaA2be8A07c6e0" "0x798d4Ba9baf0064Ec19eB4F0a1a45785ae9D6DFc" "0x773539d4Ac0e786233D90A233654ccEE26a613D9" \
  --max_registered_nodes 10 \
  --key_types "Rsa" \
  --bootnodes "test_bootnode" \
  --private_key "0x5fb92d6e98884f76de468fa3f6278f8807c48bebc13595d45af5bdc4da702133" \
  --local_rpc
```
#### Register a node:
<b>Note:</b> The client peer ID, bootnode peer ID, and bootnode are only for testing purposes. In production, the client peer ID and bootnode peer ID should be generated beforehand and each have its own identity paths (the bootnode will be derived from the bootnode peer ID if utilized). The client and bootnode peer ID are required on-chain but not required to be used off-chain in the subnet. The bootnode is optional.

Using Alith's coldkey private key:
```bash
register-node \
  --subnet_id 1 \
  --hotkey 0x317D7a5a2ba5787A99BE4693Eb340a10C71d680b \
  --peer_id QmShJYgxNoKn7xqdRQj5PBcNfPSsbWkgFBPA4mK5PH73JB \
  --bootnode_peer_id QmShJYgxNoKn7xqdRQj5PBcNfPSsbWkgFBPA4mK5PH73JC \
  --bootnode /ip4/127.00.1/tcp/31330/p2p/QmShJYgxNoKn7xqdRQj5PBcNfPSsbWkgFBPA4mK5PH73JC \
  --client_peer_id QmShJYgxNoKn7xqdRQj5PBcNfPSsbWkgFBPA4mK5PH73JD \
  --delegate_reward_rate 0.125 \
  --stake_to_be_added 100.00 \
  --max_burn_amount 100.00 \
  --private_key "0x5fb92d6e98884f76de468fa3f6278f8807c48bebc13595d45af5bdc4da702133" \
  --local_rpc
```
Get the subnet node ID after registration

#### Run a node
Using Alith's hotkey private key:
```bash
mesh-server-mock \
    --host_maddrs /ip4/0.0.0.0/tcp/31331 /ip4/0.0.0.0/udp/31331/quic \
    --announce_maddrs /ip4/{your_ip}/tcp/31331 /ip4/{your_ip}/udp/31331/quic \
    --identity_path alith.id \
    --subnet_id 1 --subnet_node_id 2 \
    --local_rpc \
    --private_key "0x51b7c50c1cd27de89a361210431e8f03a7ddda1a0c8c5ff4e4658ca81ac02720"
```
---

#### Todo

- Implement a database or JSON to persist scores locally without the use of a blockchain for live local testing.
  - ✅ <s>Register node to local db</s>
  - ✅ <s>Get live node dat from local db</s>
  - ✅ <s>Store validator/attestor data to local db</s>
  - ✅ <s>Get validator/attestor data from local db</s>
  - Local node classification updating
---

## Contributing

This is currently at the active development stage, and we welcome all contributions. Everything, from bug fixes and documentation improvements to entirely new features, is appreciated.

If you want to contribute to this mesh template but don't know where to start, take a look at the unresolved [issues](https://github.com/hypertensor-blockchain/mesh/issues). 

Open a new issue or join [our chat room](https://discord.gg/bY7NUEweQp) in case you want to discuss new functionality or report a possible bug. Bug fixes are always welcome, but new features should be preferably discussed with maintainers beforehand.
