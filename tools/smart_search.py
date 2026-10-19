import ast
import json
import time
from collections.abc import Generator
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from dify_plugin import Tool
from dify_plugin.entities.model.message import SystemPromptMessage, UserPromptMessage
from dify_plugin.entities.tool import ToolInvokeMessage

MAX_RESULTS = 10
MAX_CONTENT = 5000
MAX_FETCH_PAGES = 5
BACKEND_TIMEOUT = 15
DEEPSEEK_SEARCH_URL = "https://api.deepseek.com/v1/tools/search"
DEEPSEEK_MIN_SCORE = 1.5      # official "quality" cutoff; measured garbage sits at 0.1-0.85
DEEPSEEK_MAX_SUMMARY = 800    # cap the long summary fed to the LLM
USER_AGENT = "SmartSearchDifyPlugin/0.0.1 (+https://github.com/Kagurazaka135/dify-smart-search-full)"

_S1 = (
    "You are a search strategist. Given a user question, produce 2-3 search engine "
    "queries that cover different angles. Output ONLY a JSON array of strings, "
    'for example: ["angle A", "angle B"].'
)

_S3 = (
    "You evaluate search results for a question. Return ONLY JSON in this shape: "
    '{"relevant_count": N, "total": N, "sufficiency": '
    '"sufficient|borderline|insufficient", "new_keywords": ["new angle"]}. '
    'If at least 3 results are clearly relevant and cover the question, use '
    '"sufficient". Otherwise add 1-2 new search angles in new_keywords.'
)

_S4 = (
    "Extract the parts of the page that are relevant to the question. Be concise, "
    "and keep numbers, dates, names and quotations."
)

_S5 = (
    "Answer the question strictly from the search results and page content below. "
    "Return ONLY JSON in this shape: "
    '{"supporting": [{"point": "...", "sources": ["url"]}], '
    '"opposing": [{"point": "...", "sources": ["url"]}], '
    '"neutral_facts": [{"fact": "...", "source": "url"}], '
    '"summary": "200-300 word synthesis", "confidence": "high|medium|low"}. '
    "Do not invent facts; if sources conflict, point it out."
)


class SmartSearchTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        query = str(tool_parameters.get("query") or "").strip()
        if not query:
            raise ValueError("The 'query' parameter is required.")

        model_cfg = self._normalize_model(tool_parameters.get("model"))
        max_rounds = self._clamp_int(tool_parameters.get("max_rounds"), 3, 1, 10)
        fetch_content = bool(tool_parameters.get("fetch_content"))
        credentials = self.runtime.credentials or {}

        search_process: list[dict[str, Any]] = []
        collected: list[tuple[int, str, str, list[dict[str, str]]]] = []
        seen_queries: set[str] = set()

        queue = self._expand_queries(model_cfg, query)
        seen_queries.update(q.lower() for q in queue)

        round_idx = 0
        while queue and round_idx < max_rounds:
            round_idx += 1
            current = queue
            queue = []

            round_results: list[dict[str, str]] = []
            for keyword in current:
                backend, results = self._search(credentials, keyword, query)
                if results:
                    round_results.extend(results)
                    collected.append((round_idx, keyword, backend, results))

            verdict = self._evaluate(model_cfg, query, round_results)
            search_process.append(
                {
                    "round": round_idx,
                    "queries": current,
                    "relevant": int(verdict.get("relevant_count") or 0),
                    "verdict": verdict.get("sufficiency") or "insufficient",
                }
            )

            if str(verdict.get("sufficiency", "")).lower() in ("sufficient", "足够"):
                break

            for new_keyword in verdict.get("new_keywords") or []:
                new_keyword = str(new_keyword).strip()
                if new_keyword and new_keyword.lower() not in seen_queries:
                    seen_queries.add(new_keyword.lower())
                    queue.append(new_keyword)

        extractions: list[str] = []
        if fetch_content:
            extractions = self._fetch_top(model_cfg, query, collected)

        summary = self._summarize(model_cfg, query, collected, extractions)

        result = {
            "search_process": search_process,
            "supporting": summary.get("supporting", []),
            "opposing": summary.get("opposing", []),
            "neutral_facts": summary.get("neutral_facts", []),
            "summary": summary.get("summary", ""),
            "confidence": summary.get("confidence", "low"),
        }
        yield self.create_json_message(result)
        yield self.create_text_message(result["summary"] or "")

    # ---------- LLM (reverse invocation) ----------

    def _llm(self, model_cfg: dict[str, Any], system: str, user: str) -> str:
        messages = [
            SystemPromptMessage(content=system),
            UserPromptMessage(content=user),
        ]
        result = self.session.model.llm.invoke(
            model_config=model_cfg,
            prompt_messages=messages,
            stream=False,
        )
        return result.message.content or ""

    def _expand_queries(self, model_cfg: dict[str, Any], query: str) -> list[str]:
        raw = self._llm(model_cfg, _S1, f"Question: {query}")
        parsed = self._parse_json(raw)
        if isinstance(parsed, list):
            cleaned = [str(q).strip() for q in parsed if str(q).strip()]
            if cleaned:
                return cleaned[:3]
        return [query]

    def _evaluate(
        self, model_cfg: dict[str, Any], query: str, results: list[dict[str, str]]
    ) -> dict[str, Any]:
        if not results:
            return {"relevant_count": 0, "sufficiency": "insufficient", "new_keywords": []}
        raw = self._llm(
            model_cfg, _S3, f"Question: {query}\nResults:\n{self._format_results(results)}"
        )
        parsed = self._parse_json(raw)
        if isinstance(parsed, dict):
            return parsed
        return {"relevant_count": 0, "sufficiency": "insufficient", "new_keywords": []}

    def _summarize(
        self,
        model_cfg: dict[str, Any],
        query: str,
        collected: list[tuple[int, str, str, list[dict[str, str]]]],
        extractions: list[str],
    ) -> dict[str, Any]:
        body = ""
        for round_idx, keyword, backend, results in collected:
            body += f"\n--- round {round_idx} | query: {keyword} | backend: {backend} ---\n"
            body += self._format_results(results)
        if extractions:
            body += "\n\n--- fetched page content ---\n" + "\n\n".join(extractions)

        raw = self._llm(model_cfg, _S5, f"Question: {query}\nSearch results:\n{body}")
        parsed = self._parse_json(raw)
        if isinstance(parsed, dict):
            return parsed
        return {"summary": raw.strip(), "confidence": "low"}

    # ---------- search backends (official APIs only, no scraping) ----------

    def _search(
        self, credentials: dict[str, Any], query: str, original_query: str = ""
    ) -> tuple[str, list[dict[str, str]]]:
        backends = [
            (
                "DeepSeek",
                lambda: self._deepseek(
                    credentials.get("deepseek_api_key"), query, original_query
                ),
            ),
            ("Serper", lambda: self._serper(credentials.get("serper_api_key"), query)),
            ("SerpApi", lambda: self._serpapi(credentials.get("serpapi_api_key"), query)),
            (
                "Google",
                lambda: self._google(
                    credentials.get("google_api_key"), credentials.get("google_cx"), query
                ),
            ),
            ("Bing", lambda: self._bing(credentials.get("bing_api_key"), query)),
            ("SearXNG", lambda: self._searxng(credentials.get("searxng_base_url"), query)),
        ]
        for name, fn in backends:
            for attempt in range(3):
                try:
                    results = fn()
                except requests.RequestException:
                    if attempt < 2:
                        time.sleep(1)
                        continue
                    break
                if results:
                    return name, results
                break
        return "none", []

    def _deepseek(
        self, key: str | None, query: str, original_query: str = ""
    ) -> list[dict[str, str]]:
        if not key:
            return []
        payload: dict[str, Any] = {"query": query, "count": MAX_RESULTS}
        if original_query:
            payload["ori_question"] = original_query[:128]
        resp = requests.post(
            DEEPSEEK_SEARCH_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            timeout=BACKEND_TIMEOUT,
        )
        resp.raise_for_status()
        hits: list[dict[str, str]] = []
        for item in resp.json().get("results", [])[:MAX_RESULTS]:
            if float(item.get("rerank_score") or 0) < DEEPSEEK_MIN_SCORE:
                continue
            hit = self._hit(item.get("title"), item.get("snippet"), item.get("url"))
            summary = (item.get("summary") or "").strip()
            if summary:
                hit["detail"] = summary[:DEEPSEEK_MAX_SUMMARY]
            hits.append(hit)
        return hits

    def _serper(self, key: str | None, query: str) -> list[dict[str, str]]:
        if not key:
            return []
        resp = requests.post(
            "https://google.serper.dev/search",
            json={"q": query, "num": MAX_RESULTS},
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            timeout=BACKEND_TIMEOUT,
        )
        resp.raise_for_status()
        return [
            self._hit(item.get("title"), item.get("snippet"), item.get("link"))
            for item in resp.json().get("organic", [])[:MAX_RESULTS]
        ]

    def _serpapi(self, key: str | None, query: str) -> list[dict[str, str]]:
        if not key:
            return []
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={"engine": "google", "q": query, "num": MAX_RESULTS, "api_key": key},
            timeout=BACKEND_TIMEOUT,
        )
        resp.raise_for_status()
        return [
            self._hit(item.get("title"), item.get("snippet"), item.get("link"))
            for item in resp.json().get("organic_results", [])[:MAX_RESULTS]
        ]

    def _google(self, key: str | None, cx: str | None, query: str) -> list[dict[str, str]]:
        if not key or not cx:
            return []
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": key, "cx": cx, "q": query, "num": min(MAX_RESULTS, 10)},
            timeout=BACKEND_TIMEOUT,
        )
        resp.raise_for_status()
        return [
            self._hit(item.get("title"), item.get("snippet"), item.get("link"))
            for item in resp.json().get("items", [])[:MAX_RESULTS]
        ]

    def _bing(self, key: str | None, query: str) -> list[dict[str, str]]:
        if not key:
            return []
        resp = requests.get(
            "https://api.bing.microsoft.com/v7.0/search",
            params={"q": query, "count": MAX_RESULTS},
            headers={"Ocp-Apim-Subscription-Key": key},
            timeout=BACKEND_TIMEOUT,
        )
        resp.raise_for_status()
        items = resp.json().get("webPages", {}).get("value", [])
        return [
            self._hit(item.get("name"), item.get("snippet"), item.get("url"))
            for item in items[:MAX_RESULTS]
        ]

    def _searxng(self, base_url: str | None, query: str) -> list[dict[str, str]]:
        if not base_url:
            return []
        url = base_url.rstrip("/") + "/search?" + urlencode({"q": query, "format": "json"})
        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=BACKEND_TIMEOUT
        )
        resp.raise_for_status()
        return [
            self._hit(item.get("title"), item.get("content"), item.get("url"))
            for item in resp.json().get("results", [])[:MAX_RESULTS]
        ]

    # ---------- content fetch (opt-in, robots.txt aware) ----------

    def _fetch_top(
        self,
        model_cfg: dict[str, Any],
        query: str,
        collected: list[tuple[int, str, str, list[dict[str, str]]]],
    ) -> list[str]:
        seen: set[str] = set()
        extractions: list[str] = []
        for _, _, _, results in collected:
            for hit in results:
                if len(extractions) >= MAX_FETCH_PAGES:
                    return extractions
                url = hit.get("url") or ""
                if not url or url in seen:
                    continue
                seen.add(url)
                page = self._fetch_page(url)
                if not page:
                    continue
                excerpt = self._llm(model_cfg, _S4, f"Question: {query}\nPage:\n{page}")
                if excerpt.strip():
                    extractions.append(excerpt.strip())
        return extractions

    def _fetch_page(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return ""
        if not self._robots_allows(url):
            return ""
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=BACKEND_TIMEOUT
            )
            resp.raise_for_status()
        except requests.RequestException:
            return ""
        if "html" not in resp.headers.get("Content-Type", "").lower():
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:MAX_CONTENT]

    @staticmethod
    def _robots_allows(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        try:
            resp = requests.get(
                robots_url, headers={"User-Agent": USER_AGENT}, timeout=10
            )
        except requests.RequestException:
            return False
        if resp.status_code == 404:
            return True
        parser = RobotFileParser()
        parser.parse(resp.text.splitlines())
        return parser.can_fetch("*", url)

    # ---------- helpers ----------

    @staticmethod
    def _normalize_model(model: Any) -> dict[str, Any]:
        if isinstance(model, dict):
            cfg = dict(model)
        elif isinstance(model, str) and model.strip():
            text = model.strip()
            parsed: Any = None
            if text[:1] in "{[":
                # Some Dify workflow runtimes serialize a model-selector value to a
                # string (Python repr or JSON) before handing it to the tool.
                try:
                    parsed = ast.literal_eval(text)
                except (ValueError, SyntaxError):
                    parsed = None
                if not isinstance(parsed, dict):
                    try:
                        parsed = json.loads(text)
                    except (json.JSONDecodeError, ValueError):
                        parsed = None
            cfg = dict(parsed) if isinstance(parsed, dict) else {"model": text}
        else:
            raise ValueError("The 'model' parameter is required.")
        cfg.setdefault("model_type", "llm")
        cfg.setdefault("mode", "chat")
        cfg.setdefault("completion_params", {})
        return cfg

    @staticmethod
    def _clamp_int(value: Any, default: int, low: int, high: int) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return default
        return max(low, min(high, number))

    @staticmethod
    def _hit(title: Any, snippet: Any, url: Any) -> dict[str, str]:
        return {
            "title": (title or "").strip(),
            "snippet": (snippet or "").strip(),
            "url": (url or "").strip(),
        }

    @staticmethod
    def _format_results(results: list[dict[str, str]]) -> str:
        lines = []
        for index, hit in enumerate(results, 1):
            body = hit.get("detail") or hit.get("snippet", "")[:200]
            lines.append(f"[{index}] {hit['title']}\n    {body}\n    {hit['url']}")
        return "\n".join(lines)

    @staticmethod
    def _parse_json(raw: str) -> Any:
        text = (raw or "").strip()
        if text.startswith("```"):
            text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            if text[:4].lower() == "json":
                text = text[4:]
            text = text.strip()
        try:
            return json.loads(text)
        except (json.JSONDecodeError, ValueError):
            pass
        for opener, closer in (("[", "]"), ("{", "}")):
            start = text.find(opener)
            end = text.rfind(closer)
            if start != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except (json.JSONDecodeError, ValueError):
                    continue
        return None
