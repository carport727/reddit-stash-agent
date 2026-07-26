from app.database.database import SessionLocal


def run():

    db = SessionLocal()

    try:
        print("✓ Database ready")

    finally:
        db.close()
