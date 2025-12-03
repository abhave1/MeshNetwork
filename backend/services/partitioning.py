import hashlib
import bisect
import logging
from typing import List, Optional, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConsistentHash:
    def __init__(self, nodes: Optional[List[str]] = None, virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self.ring = {}
        self.sorted_keys = []

        if nodes:
            for node in nodes:
                self.add_node(node)

    def _hash(self, key: str) -> int:
        md5 = hashlib.md5()
        md5.update(key.encode('utf-8'))
        return int(md5.hexdigest(), 16)

    def add_node(self, node: str):
        for i in range(self.virtual_nodes):
            virtual_key = f"{node}:{i}"
            hash_value = self._hash(virtual_key)
            self.ring[hash_value] = node
            bisect.insort(self.sorted_keys, hash_value)

        logger.info(f"Added node {node} to consistent hash ring with {self.virtual_nodes} virtual nodes")

    def remove_node(self, node: str):
        for i in range(self.virtual_nodes):
            virtual_key = f"{node}:{i}"
            hash_value = self._hash(virtual_key)

            if hash_value in self.ring:
                del self.ring[hash_value]
                self.sorted_keys.remove(hash_value)

        logger.info(f"Removed node {node} from consistent hash ring")

    def get_node(self, key: str) -> Optional[str]:
        if not self.ring:
            return None

        hash_value = self._hash(key)
        idx = bisect.bisect_right(self.sorted_keys, hash_value)

        if idx == len(self.sorted_keys):
            idx = 0

        node_hash = self.sorted_keys[idx]
        return self.ring[node_hash]

    def get_nodes_for_key(self, key: str, n: int = 1) -> List[str]:
        if not self.ring or n <= 0:
            return []

        hash_value = self._hash(key)
        idx = bisect.bisect_right(self.sorted_keys, hash_value)

        nodes = []
        seen_nodes = set()

        for i in range(len(self.sorted_keys)):
            actual_idx = (idx + i) % len(self.sorted_keys)
            node_hash = self.sorted_keys[actual_idx]
            node = self.ring[node_hash]

            if node not in seen_nodes:
                nodes.append(node)
                seen_nodes.add(node)

                if len(nodes) == n:
                    break

        return nodes

    def get_distribution_stats(self) -> Dict[str, Any]:
        node_counts = {}

        for node in self.ring.values():
            node_counts[node] = node_counts.get(node, 0) + 1

        return {
            'total_virtual_nodes': len(self.ring),
            'physical_nodes': len(set(self.ring.values())),
            'virtual_nodes_per_physical': node_counts
        }

class PartitioningService:
    def __init__(self, replica_set_members: Optional[List[str]] = None):
        self.nodes = replica_set_members or ['primary', 'secondary1', 'secondary2']
        self.hash_ring = ConsistentHash(self.nodes)

        logger.info(f"Initialized partitioning service with nodes: {self.nodes}")

    def get_node_for_user(self, user_id: str) -> str:
        node = self.hash_ring.get_node(user_id)
        logger.debug(f"User {user_id} mapped to node {node}")
        return node

    def get_replica_nodes_for_user(self, user_id: str, num_replicas: int = 3) -> List[str]:
        nodes = self.hash_ring.get_nodes_for_key(user_id, num_replicas)
        logger.debug(f"User {user_id} should be replicated to nodes: {nodes}")
        return nodes

    def get_partition_key(self, document: Dict[str, Any]) -> Optional[str]:
        if 'user_id' in document:
            return document['user_id']

        if '_id' in document:
            return str(document['_id'])

        logger.warning(f"No partition key found in document: {document}")
        return None

    def should_route_to_node(self, document: Dict[str, Any], target_node: str) -> bool:
        partition_key = self.get_partition_key(document)

        if not partition_key:
            return True

        responsible_node = self.get_node_for_user(partition_key)
        return responsible_node == target_node

    def get_distribution_report(self) -> Dict[str, Any]:
        stats = self.hash_ring.get_distribution_stats()

        return {
            'partitioning_strategy': 'consistent_hashing',
            'partition_key': 'user_id',
            'nodes': self.nodes,
            'distribution': stats
        }

    def rebalance(self, new_nodes: List[str]):
        current_nodes = set(self.nodes)
        new_nodes_set = set(new_nodes)

        nodes_to_add = new_nodes_set - current_nodes
        nodes_to_remove = current_nodes - new_nodes_set

        for node in nodes_to_remove:
            self.hash_ring.remove_node(node)
            logger.info(f"Removed node from hash ring: {node}")

        for node in nodes_to_add:
            self.hash_ring.add_node(node)
            logger.info(f"Added node to hash ring: {node}")

        self.nodes = new_nodes
        logger.info(f"Rebalanced hash ring. Current nodes: {self.nodes}")

partitioning_service = PartitioningService()
