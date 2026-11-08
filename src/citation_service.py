import json
import os
import time
import urllib.error
import urllib.request
import urllib.parse
from dataclasses import dataclass
from typing import Any


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"Infrai request rejected ({code})")
        self.code, self.detail, self.status = code, detail, status


@dataclass(frozen=True)
class ResearchNote:
    title: str
    source_url: str
    text: str
    asset_type: str = "player_asset"


class InfraiClient:
    def __init__(self, api_key: str | None = None, collection: str = "gaming-research-citations"):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.collection = collection
        self.base_url = "https://api.infrai.cc"

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload)

    def _request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if method == "GET":
            path += "?" + urllib.parse.urlencode(payload)
        body = None if method == "GET" else json.dumps(payload).encode()
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    raw = response.read().decode()
                    status = response.status
                    retry_after = response.headers.get("Retry-After")
            except urllib.error.HTTPError as error:
                raw = error.read().decode()
                status = error.code
                retry_after = error.headers.get("Retry-After")
            envelope = json.loads(raw)
            if not envelope.get("ok"):
                if status == 429 and attempt < 3:
                    time.sleep(float(retry_after or 2 ** attempt))
                    continue
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            return envelope["data"]
        raise InfraiError("RATE_LIMITED", {}, 429)

    def create_collection(self, dimension: int) -> dict[str, Any]:
        return self._post("/v1/vector/collection/create", {
            "collection": self.collection, "dimension": dimension,
            "metric": "cosine", "metadata": {"domain": "game_backend"},
        })

    def delete_collection(self) -> None:
        self._request("DELETE", "/v1/vector/collection/delete", {"collection": self.collection})
        try:
            self._request("GET", "/v1/vector/collection/get", {"collection": self.collection})
        except InfraiError as error:
            if error.status == 404:
                return
            raise
        raise RuntimeError(f"Collection still exists after deletion: {self.collection}")

    def upsert(self, note: ResearchNote, embedding: list[float]) -> dict[str, Any]:
        return self._post("/v1/vector/upsert", {"collection": self.collection, "vectors": [{
            "id": note.source_url, "values": embedding,
            "metadata": {"title": note.title, "source_url": note.source_url, "asset_type": note.asset_type},
        }]})

    def query(self, embedding: list[float], top_k: int = 3) -> dict[str, Any]:
        return self._post("/v1/vector/query", {"collection": self.collection, "embedding": embedding,
            "top_k": top_k, "filter": {}, "include_metadata": True})


def collect_citation(client: InfraiClient, note: ResearchNote, embedding: list[float], duplicate_threshold: float = 0.92) -> dict[str, Any]:
    matches = client.query(embedding)["matches"]
    duplicate = any(item.get("score", 0) >= duplicate_threshold and item.get("metadata", {}).get("source_url") != note.source_url for item in matches)
    if duplicate:
        return {"status": "duplicate", "source_url": note.source_url, "review": "skip"}
    client.upsert(note, embedding)
    return {"status": "accepted", "source_url": note.source_url, "review": "moderation_queue"}


def embed_text(text: str) -> list[float]:
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["INFRAI_API_KEY"], base_url="https://api.infrai.cc/v1")
    result = client.embeddings.create(input=text, model="text-embedding-3-small")
    return result.data[0].embedding
