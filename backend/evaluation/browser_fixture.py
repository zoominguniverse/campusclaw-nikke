"""Isolated UI fixture; NEVER started by the production entrypoint."""
import os
from pathlib import Path
from sqlalchemy.engine import make_url

if os.getenv("QUALITY_DISPOSABLE_DATABASE") != "true" or make_url(os.environ["DATABASE_URL"]).database != "quality_browser":
    raise RuntimeError("browser fixture requires its isolated quality_browser database")

from tests.conftest import DEMO_ACCOUNT_PASSWORDS  # fake passwords and fast test hash
from app import create_app
from app.database import db
from app.indexing import reindex_entry
from app.models import KnowledgeEntry, Material
from app.providers import DeterministicEmbeddingClient, DeterministicChatClient, ProviderUnavailable
import app.indexing as indexing
import app.answers as answers

app = create_app({"INITIALIZE_DATABASE": True, "SEED_DEMO_DATA": True, "DEMO_ACCOUNT_PASSWORDS": DEMO_ACCOUNT_PASSWORDS})
with app.app_context():
    entry = KnowledgeEntry.query.filter_by(class_id=1).first()
    if entry and "浏览器验证原文" not in entry.body_text:
        material = db.session.get(Material, entry.material_id)
        material.title = "浏览器验证原文"
        entry.body_text = "😀浏览器验证原文，前言应保留。\n<script>alert('不应执行')</script>\n\n# 细胞章节\n" + "背景资料。" * 100 + "\n😀细胞是生物体结构和功能的基本单位。\n细胞膜控制物质进出细胞。\n参考：https://example.com/" + "x" * 170 + "\n邮箱：teacher@example.com\n"
        db.session.commit()
        reindex_entry(entry, {"strategy": "hierarchy", "preprocess": {"remove_urls": True, "remove_emails": True}})

class FaultEmbedding(DeterministicEmbeddingClient):
    def embed_batch(self, texts):
        if Path('/tmp/quality-provider-fail').exists():
            raise ProviderUnavailable('isolated browser injected failure')
        return super().embed_batch(texts)

class FixtureChat(DeterministicChatClient):
    def answer(self, question, evidence, history, *, repair=False):
        if "服务失败验收" in question:
            raise ProviderUnavailable('isolated browser injected failure')
        if "资料不足验收" in question:
            return {"status": "insufficient", "claims": []}
        if "多段高亮验收" in question:
            quotes = ['细胞是生物体结构和功能的基本单位。', '细胞膜控制物质进出细胞。']
            refs = []
            for quote in quotes:
                for index, item in enumerate(evidence, 1):
                    if any(quote in segment['text'] for segment in item['source_segments']):
                        refs.append({'index': index, 'quote': quote}); break
            return {'status': 'answered', 'claims': [{'text': '细胞是基本单位，细胞膜控制物质进出。', 'evidence': refs}]}
        return super().answer(question, evidence, history, repair=repair)

if os.getenv('QUALITY_REAL_BROWSER') == 'true':
    if any(app.config[key] != 'openai-compatible' for key in ['EMBEDDING_PROVIDER', 'CHAT_PROVIDER']):
        raise RuntimeError('real browser acceptance requires both real providers')
    with app.app_context():
        from app.indexing import backfill_entries
        result = backfill_entries(100)
        if result.get('failed', 0):
            raise RuntimeError('real browser fixture indexing failed')
else:
    indexing.embedding_client = lambda: FaultEmbedding(64)
    answers.chat_client = lambda: FixtureChat()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
