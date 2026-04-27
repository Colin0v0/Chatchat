import unittest
from types import SimpleNamespace

from app.retrieval.websearch.providers.dashscope import DashScopeWebSearchProvider
from app.retrieval.websearch.types import WebQuery


def make_settings(**overrides):
    values = {
        "dashscope_api_key": "dashscope-key",
        "web_search_api_key": "",
        "web_search_base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
        "web_search_timeout_seconds": 20.0,
        "web_search_model": "qwen-plus",
        "web_search_strategy": "turbo",
        "web_search_forced": True,
        "web_search_enable_source": True,
        "web_search_enable_citation": True,
        "web_search_citation_format": "[ref_<number>]",
        "web_search_max_results": 5,
        "web_search_http_max_concurrency": 4,
        "http_pool_max_connections": 20,
        "http_pool_max_keepalive_connections": 8,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class DashScopeWebSearchProviderTests(unittest.TestCase):
    def test_request_payload_uses_dashscope_native_search_options(self):
        provider = DashScopeWebSearchProvider(make_settings())

        payload = provider._build_request_payload(
            WebQuery(
                raw_query="今天杭州天气",
                cleaned_query="今天杭州天气",
                include_domains=("weather.com.cn",),
            )
        )

        self.assertEqual(payload["model"], "qwen-plus")
        parameters = payload["parameters"]
        self.assertTrue(parameters["enable_search"])
        search_options = parameters["search_options"]
        self.assertTrue(search_options["enable_source"])
        self.assertTrue(search_options["enable_citation"])
        self.assertTrue(search_options["forced_search"])
        self.assertEqual(search_options["search_strategy"], "turbo")
        self.assertEqual(search_options["citation_format"], "[ref_<number>]")
        self.assertEqual(search_options["assigned_site_list"], ["weather.com.cn"])

    def test_parse_response_maps_search_results_to_web_results(self):
        provider = DashScopeWebSearchProvider(make_settings())
        payload = {
            "output": {
                "choices": [
                    {
                        "message": {
                            "content": "杭州今日多云，最高气温约 24 摄氏度。[ref_1]\n出行建议关注临近预报。[ref_2]",
                        }
                    }
                ],
                "search_info": {
                    "search_results": [
                        {
                            "index": 1,
                            "title": "杭州天气预报",
                            "url": "https://www.weather.com.cn/weather/101210101.shtml",
                            "site_name": "中国天气网",
                        },
                        {
                            "index": 2,
                            "title": "浙江气象",
                            "url": "https://zj.cma.gov.cn/",
                            "site_name": "浙江气象局",
                            "snippet": "浙江省气象服务信息。",
                        },
                    ]
                },
            }
        }

        results = provider._parse_response(payload)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "杭州天气预报")
        self.assertEqual(results[0].domain, "www.weather.com.cn")
        self.assertIn("[ref_1]", results[0].excerpt)
        self.assertEqual(results[1].excerpt, "浙江省气象服务信息。")
        self.assertGreater(results[0].provider_score or 0, results[1].provider_score or 0)

    def test_configured_falls_back_to_dashscope_api_key(self):
        provider = DashScopeWebSearchProvider(make_settings(web_search_api_key="", dashscope_api_key="dashscope-key"))

        self.assertTrue(provider.configured)

    def test_compatible_mode_base_url_is_normalized_to_native_generation_endpoint(self):
        provider = DashScopeWebSearchProvider(
            make_settings(web_search_base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
        )

        self.assertEqual(provider._base_url, "https://dashscope.aliyuncs.com")
        self.assertEqual(provider._endpoint_path, "/api/v1/services/aigc/text-generation/generation")

    def test_plain_non_dashscope_root_url_is_ignored(self):
        provider = DashScopeWebSearchProvider(make_settings(web_search_base_url="https://example.invalid"))

        self.assertEqual(provider._base_url, "https://dashscope.aliyuncs.com")
        self.assertEqual(provider._endpoint_path, "/api/v1/services/aigc/text-generation/generation")


if __name__ == "__main__":
    unittest.main()
