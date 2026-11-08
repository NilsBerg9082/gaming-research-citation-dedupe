from citation_service import ResearchNote, collect_citation


class FakeClient:
    def __init__(self, score):
        self.score = score
        self.upserted = False

    def query(self, embedding):
        return {"matches": [{"score": self.score, "metadata": {"source_url": "https://other.example/ref"}}]}

    def upsert(self, note, embedding):
        self.upserted = True


def test_near_duplicate_stays_out_of_moderation_queue():
    client = FakeClient(0.97)
    result = collect_citation(client, ResearchNote("Raid event", "https://new.example/ref", "A live event"), [0.1, 0.2])
    assert result == {"status": "duplicate", "source_url": "https://new.example/ref", "review": "skip"}
    assert client.upserted is False


def test_new_source_is_stored_for_review():
    client = FakeClient(0.30)
    result = collect_citation(client, ResearchNote("Moderation queue", "https://new.example/ref", "Queue notes"), [0.1, 0.2])
    assert result["status"] == "accepted"
    assert result["review"] == "moderation_queue"
    assert client.upserted is True


def test_demo_cleans_up_when_collection_work_fails(monkeypatch):
    import runpy
    import citation_service
    import pytest

    calls = []

    class DemoClient:
        def __init__(self, collection):
            self.collection = collection

        def create_collection(self, dimension):
            calls.append('create')

        def delete_collection(self):
            calls.append('delete')

    def fail(*args):
        raise RuntimeError('query failed')

    monkeypatch.setattr(citation_service, 'InfraiClient', DemoClient)
    monkeypatch.setattr(citation_service, 'embed_text', lambda text: [0.1, 0.2])
    monkeypatch.setattr(citation_service, 'collect_citation', fail)
    with pytest.raises(RuntimeError, match='query failed'):
        runpy.run_path('run_demo.py', run_name='__main__')
    assert calls == ['create', 'delete']


def test_collection_cleanup_verifies_absence(monkeypatch):
    from citation_service import InfraiClient, InfraiError

    client = InfraiClient(api_key='test', collection='temporary-test')
    calls = []

    def request(method, path, payload):
        calls.append((method, path, payload))
        if method == 'GET':
            raise InfraiError('NOT_FOUND', {}, 404)
        return {}

    monkeypatch.setattr(client, '_request', request)
    client.delete_collection()
    assert calls == [
        ('DELETE', '/v1/vector/collection/delete', {'collection': 'temporary-test'}),
        ('GET', '/v1/vector/collection/get', {'collection': 'temporary-test'}),
    ]


def test_collection_cleanup_rejects_remaining_collection(monkeypatch):
    import pytest
    from citation_service import InfraiClient

    client = InfraiClient(api_key='test', collection='temporary-test')
    monkeypatch.setattr(client, '_request', lambda *args: {})
    with pytest.raises(RuntimeError, match='still exists'):
        client.delete_collection()
