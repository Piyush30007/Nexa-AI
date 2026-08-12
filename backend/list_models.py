from database import SessionLocal, Chunk

db = SessionLocal()

terms = [
    "within one hour",
    "one hour",
    "illness",
    "tardiness",
    "unforeseen",
]

for term in terms:
    print("\n" + "=" * 70)
    print("SEARCH:", term)
    print("=" * 70)

    chunks = (
        db.query(Chunk)
        .filter(Chunk.text.ilike(f"%{term}%"))
        .all()
    )

    print("FOUND:", len(chunks))

    for chunk in chunks:
        print("\nPage:", chunk.page)
        print("Chunk ID:", chunk.id)
        print("Text:")
        print(chunk.text)

db.close()