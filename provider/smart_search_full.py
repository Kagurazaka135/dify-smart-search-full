from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError


class SmartSearchFullProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        serper = (credentials.get("serper_api_key") or "").strip()
        serpapi = (credentials.get("serpapi_api_key") or "").strip()
        google_key = (credentials.get("google_api_key") or "").strip()
        google_cx = (credentials.get("google_cx") or "").strip()
        bing = (credentials.get("bing_api_key") or "").strip()
        searxng = (credentials.get("searxng_base_url") or "").strip()

        if not any([serper, serpapi, google_key and google_cx, bing, searxng]):
            raise ToolProviderCredentialValidationError(
                "Configure at least one search backend: a Serper API key, a "
                "SerpApi key, a Google API key + Search Engine ID (cx), a Bing "
                "Web Search key, or a SearXNG base URL."
            )

        if google_key and not google_cx:
            raise ToolProviderCredentialValidationError(
                "The Google backend needs both the API key and the Search Engine "
                "ID (cx)."
            )

        if google_cx and not google_key:
            raise ToolProviderCredentialValidationError(
                "The Google backend needs both the API key and the Search Engine "
                "ID (cx)."
            )
