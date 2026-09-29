from app import create_app
from app.indexing import backfill_entries


app = create_app()

with app.app_context():
    print(backfill_entries())
