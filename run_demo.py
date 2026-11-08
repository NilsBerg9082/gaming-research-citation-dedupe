from uuid import uuid4

from citation_service import InfraiClient, ResearchNote, collect_citation, embed_text


def main() -> None:
    note = ResearchNote(
        title="Player-created asset moderation",
        source_url="https://example.com/game-backend-notes",
        text="Live events can feed player-generated assets into a moderation queue.",
        asset_type="player_asset",
    )
    embedding = embed_text(note.text)
    client = InfraiClient(collection=f"gaming-research-citations-{uuid4().hex}")
    client.create_collection(len(embedding))
    try:
        print(collect_citation(client, note, embedding))
    finally:
        client.delete_collection()
        print(f"Deleted and verified collection: {client.collection}")


if __name__ == "__main__":
    main()
