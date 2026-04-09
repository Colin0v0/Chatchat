import unittest

import httpx

from app.core.http import SharedHttpClientRegistry


class SharedHttpClientRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_reuses_client_for_same_configuration(self):
        registry = SharedHttpClientRegistry()
        timeout = httpx.Timeout(10.0, connect=3.0)
        limits = httpx.Limits(max_connections=5, max_keepalive_connections=2)

        first = await registry.get_client(
            base_url="http://127.0.0.1:8000/v1",
            headers={"Authorization": "Bearer test"},
            timeout=timeout,
            limits=limits,
        )
        second = await registry.get_client(
            base_url="http://127.0.0.1:8000/v1",
            headers={"Authorization": "Bearer test"},
            timeout=timeout,
            limits=limits,
        )

        self.assertIs(first, second)
        await registry.aclose()

    async def test_returns_distinct_clients_for_distinct_headers(self):
        registry = SharedHttpClientRegistry()

        first = await registry.get_client(
            base_url="http://127.0.0.1:8000/v1",
            headers={"Authorization": "Bearer a"},
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
        )
        second = await registry.get_client(
            base_url="http://127.0.0.1:8000/v1",
            headers={"Authorization": "Bearer b"},
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
        )

        self.assertIsNot(first, second)
        await registry.aclose()


if __name__ == "__main__":
    unittest.main()
