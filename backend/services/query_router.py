import requests
import logging
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QueryRouter:
    def __init__(self):
        self.local_region = config.REGION
        self.remote_regions = config.REMOTE_REGIONS
        self.timeout = config.REQUEST_TIMEOUT

    def check_network_health(self) -> Dict[str, bool]:
        health_status = {}

        for region_url in self.remote_regions:
            try:
                response = requests.get(
                    f"{region_url}/health",
                    timeout=self.timeout
                )
                health_status[region_url] = response.status_code == 200
                logger.info(f"Region {region_url} is {'reachable' if health_status[region_url] else 'unreachable'}")
            except Exception as e:
                health_status[region_url] = False
                logger.warning(f"Region {region_url} is unreachable: {e}")

        return health_status

    def route_query(
        self,
        endpoint: str,
        method: str = 'GET',
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        user_region: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.info(f"Routing {method} query to {endpoint} (local region: {self.local_region})")

        return {
            'local_region': self.local_region,
            'query_type': 'local'
        }

    def scatter_gather(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_per_region: Optional[int] = None,
        min_responses: int = 1
    ) -> Dict[str, Any]:
        import time
        start_time = time.time()

        all_results = []
        successful_regions = []
        failed_regions = []

        timeout = timeout_per_region or self.timeout

        with ThreadPoolExecutor(max_workers=len(self.remote_regions)) as executor:
            futures = {}

            for region_url in self.remote_regions:
                future = executor.submit(
                    self._query_region,
                    region_url,
                    endpoint,
                    params,
                    timeout
                )
                futures[future] = region_url

            for future in as_completed(futures, timeout=timeout * 2):
                region_url = futures[future]
                try:
                    result = future.result(timeout=timeout)
                    if result:
                        successful_regions.append(region_url)
                        if isinstance(result, dict):
                            all_results.append(result)
                            logger.info(f"Retrieved 1 response from {region_url}")
                        elif isinstance(result, list):
                            all_results.extend(result)
                            logger.info(f"Retrieved {len(result)} results from {region_url}")
                        else:
                            logger.warning(f"Unexpected result type from {region_url}: {type(result)}")
                    else:
                        failed_regions.append(region_url)
                        logger.warning(f"No results from {region_url}")
                except Exception as e:
                    failed_regions.append(region_url)
                    logger.error(f"Error querying {region_url}: {e}")

        end_time = time.time()
        elapsed_time = end_time - start_time

        if len(successful_regions) < min_responses:
            logger.warning(
                f"Only {len(successful_regions)} regions responded "
                f"(minimum required: {min_responses})"
            )

        metadata = {
            'total_regions_queried': len(self.remote_regions),
            'successful_regions': successful_regions,
            'failed_regions': failed_regions,
            'success_rate': len(successful_regions) / len(self.remote_regions) if self.remote_regions else 0,
            'query_time_seconds': round(elapsed_time, 3),
            'timeout_per_region': timeout
        }

        logger.info(
            f"Scatter-gather completed: {len(successful_regions)}/{len(self.remote_regions)} "
            f"regions responded in {elapsed_time:.3f}s"
        )

        return {
            'results': all_results,
            'metadata': metadata
        }

    def _query_region(
        self,
        region_url: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        try:
            url = f"{region_url}{endpoint}"
            timeout_val = timeout or self.timeout
            response = requests.get(url, params=params, timeout=timeout_val)

            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Region {region_url} returned status {response.status_code}")
                return None

        except requests.Timeout:
            logger.error(f"Timeout querying region {region_url} (timeout: {timeout_val}s)")
            return None
        except Exception as e:
            logger.error(f"Error querying region {region_url}: {e}")
            return None

    def merge_results(
        self,
        results: List[Dict[str, Any]],
        sort_by: str = 'timestamp',
        reverse: bool = True
    ) -> List[Dict[str, Any]]:
        try:
            sorted_results = sorted(
                results,
                key=lambda x: x.get(sort_by, ''),
                reverse=reverse
            )
            return sorted_results
        except Exception as e:
            logger.error(f"Error merging results: {e}")
            return results

query_router = QueryRouter()
