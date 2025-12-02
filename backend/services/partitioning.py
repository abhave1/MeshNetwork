"""
Hash-based partitioning service for intra-region data distribution.
Implements consistent hashing for load balancing across nodes within a region.
"""

import hashlib
import bisect
import logging
from typing import List, Optional, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ConsistentHash:
    """
    Consistent hashing ring implementation for distributing data across nodes.

    This allows for minimal data movement when nodes are added or removed.
    Used for hash-based sub-partitioning within a geographic region.
    """

    def __init__(self, nodes: Optional[List[str]] = None, virtual_nodes: int = 150):
        """
        Initialize consistent hash ring.

        Args:
            nodes: List of node identifiers
            virtual_nodes: Number of virtual nodes per physical node (for better distribution)
        """
        self.virtual_nodes = virtual_nodes
        self.ring = {}  # Maps hash values to node names
        self.sorted_keys = []  # Sorted list of hash values for binary search

        if nodes:
            for node in nodes:
                self.add_node(node)

    def _hash(self, key: str) -> int:
        """
        Generate hash value for a key using MD5.

        Args:
            key: String to hash

        Returns:
            Integer hash value
        """
        # Use MD5 for consistent hashing (not for security)
        md5 = hashlib.md5()
        md5.update(key.encode('utf-8'))
        # Convert to integer
        return int(md5.hexdigest(), 16)

    def add_node(self, node: str):
        """
        Add a node to the hash ring.

        Args:
            node: Node identifier
        """
        for i in range(self.virtual_nodes):
            # Create virtual node identifiers
            virtual_key = f"{node}:{i}"
            hash_value = self._hash(virtual_key)
            self.ring[hash_value] = node
            bisect.insort(self.sorted_keys, hash_value)

        logger.info(f"Added node {node} to consistent hash ring with {self.virtual_nodes} virtual nodes")

    def remove_node(self, node: str):
        """
        Remove a node from the hash ring.

        Args:
            node: Node identifier to remove
        """
        for i in range(self.virtual_nodes):
            virtual_key = f"{node}:{i}"
            hash_value = self._hash(virtual_key)

            if hash_value in self.ring:
                del self.ring[hash_value]
                self.sorted_keys.remove(hash_value)

        logger.info(f"Removed node {node} from consistent hash ring")

    def get_node(self, key: str) -> Optional[str]:
        """
        Get the node responsible for a given key.

        Args:
            key: Key to look up (e.g., user_id)

        Returns:
            Node identifier that should handle this key
        """
        if not self.ring:
            return None

        hash_value = self._hash(key)

        # Find the first node with hash >= key's hash (clockwise on ring)
        idx = bisect.bisect_right(self.sorted_keys, hash_value)

        # Wrap around if we're past the last node
        if idx == len(self.sorted_keys):
            idx = 0

        node_hash = self.sorted_keys[idx]
        return self.ring[node_hash]

    def get_nodes_for_key(self, key: str, n: int = 1) -> List[str]:
        """
        Get multiple nodes for a key (for replication).

        Args:
            key: Key to look up
            n: Number of nodes to return

        Returns:
            List of node identifiers
        """
        if not self.ring or n <= 0:
            return []

        hash_value = self._hash(key)
        idx = bisect.bisect_right(self.sorted_keys, hash_value)

        nodes = []
        seen_nodes = set()

        # Collect n unique nodes
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
        """
        Get statistics about key distribution across nodes.

        Returns:
            Dictionary with distribution statistics
        """
        node_counts = {}

        for node in self.ring.values():
            node_counts[node] = node_counts.get(node, 0) + 1

        return {
            'total_virtual_nodes': len(self.ring),
            'physical_nodes': len(set(self.ring.values())),
            'virtual_nodes_per_physical': node_counts
        }


class PartitioningService:
    """
    Service for managing data partitioning within a region.
    Combines geographic partitioning with hash-based sub-partitioning.
    """

    def __init__(self, replica_set_members: Optional[List[str]] = None):
        """
        Initialize partitioning service.

        Args:
            replica_set_members: List of MongoDB replica set member hosts
        """
        # For MVP, we'll use the replica set members as our partitioning nodes
        # In production, you might have separate partitioning logic
        self.nodes = replica_set_members or ['primary', 'secondary1', 'secondary2']
        self.hash_ring = ConsistentHash(self.nodes)

        logger.info(f"Initialized partitioning service with nodes: {self.nodes}")

    def get_node_for_user(self, user_id: str) -> str:
        """
        Determine which node should handle operations for a given user.

        Args:
            user_id: User identifier

        Returns:
            Node identifier
        """
        node = self.hash_ring.get_node(user_id)
        logger.debug(f"User {user_id} mapped to node {node}")
        return node

    def get_replica_nodes_for_user(self, user_id: str, num_replicas: int = 3) -> List[str]:
        """
        Get replica nodes for a user (for replication within region).

        Args:
            user_id: User identifier
            num_replicas: Number of replica nodes

        Returns:
            List of node identifiers
        """
        nodes = self.hash_ring.get_nodes_for_key(user_id, num_replicas)
        logger.debug(f"User {user_id} should be replicated to nodes: {nodes}")
        return nodes

    def get_partition_key(self, document: Dict[str, Any]) -> Optional[str]:
        """
        Extract the partition key from a document.

        Args:
            document: Document to partition

        Returns:
            Partition key (typically user_id)
        """
        # Primary partition key is user_id
        if 'user_id' in document:
            return document['user_id']

        # Fallback to _id if no user_id
        if '_id' in document:
            return str(document['_id'])

        logger.warning(f"No partition key found in document: {document}")
        return None

    def should_route_to_node(self, document: Dict[str, Any], target_node: str) -> bool:
        """
        Check if a document should be routed to a specific node.

        Args:
            document: Document to check
            target_node: Target node identifier

        Returns:
            True if document should be routed to this node
        """
        partition_key = self.get_partition_key(document)

        if not partition_key:
            # If no partition key, allow access from any node
            return True

        responsible_node = self.get_node_for_user(partition_key)
        return responsible_node == target_node

    def get_distribution_report(self) -> Dict[str, Any]:
        """
        Generate a report on data distribution across nodes.

        Returns:
            Distribution statistics
        """
        stats = self.hash_ring.get_distribution_stats()

        return {
            'partitioning_strategy': 'consistent_hashing',
            'partition_key': 'user_id',
            'nodes': self.nodes,
            'distribution': stats
        }

    def rebalance(self, new_nodes: List[str]):
        """
        Rebalance the hash ring when nodes are added or removed.

        Args:
            new_nodes: Updated list of nodes
        """
        # Determine which nodes were added and removed
        current_nodes = set(self.nodes)
        new_nodes_set = set(new_nodes)

        nodes_to_add = new_nodes_set - current_nodes
        nodes_to_remove = current_nodes - new_nodes_set

        # Remove old nodes
        for node in nodes_to_remove:
            self.hash_ring.remove_node(node)
            logger.info(f"Removed node from hash ring: {node}")

        # Add new nodes
        for node in nodes_to_add:
            self.hash_ring.add_node(node)
            logger.info(f"Added node to hash ring: {node}")

        # Update nodes list
        self.nodes = new_nodes

        logger.info(f"Rebalanced hash ring. Current nodes: {self.nodes}")


# Create singleton instance
# In a real deployment, you would initialize this with actual replica set members
partitioning_service = PartitioningService()
