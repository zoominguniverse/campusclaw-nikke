"""Execute the frozen corpus only against an explicitly disposable PostgreSQL."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import time
from contextlib import ExitStack
from unittest.mock import patch

from sqlalchemy import event
from sqlalchemy.engine import make_url

from .report import summarize, validate_corpus, write_report


def load_fixture(corpus):
    from app.database import db
    from app.indexing import index_entry, _eligible_query
    from app.models import KnowledgeEntry, KnowledgeIndexGeneration, Material, Role, SchoolClass, ClassSubject, User
    classes, subjects = {}, {}
    if not db.session.get(Role, "teacher"):
        db.session.add(Role(name="teacher"))
    db.session.flush()
    for material in corpus["materials"]:
        code = f"Q-{material['class']}"
        if code not in classes:
            school_class = SchoolClass.query.filter_by(code=code).first()
            if not school_class:
                school_class = SchoolClass(code=code, name=code)
                db.session.add(school_class)
                db.session.flush()
            classes[material["class"]] = school_class.id
        key = material["class"], material["subject"]
        if key not in subjects:
            subject = ClassSubject.query.filter_by(class_id=classes[material["class"]], subject_key=material["subject"]).first()
            if not subject:
                subject = ClassSubject(class_id=classes[material["class"]], subject_key=material["subject"], name=material["subject"], normalized_name=material["subject"], status="active")
                db.session.add(subject)
                db.session.flush()
            subjects[key] = subject.id
        user = User.query.filter_by(username="quality-fixture-owner").first()
        if not user:
            user = User(username="quality-fixture-owner", password_hash="disabled-fixture-login", role="teacher", class_id=classes[material["class"]], is_active=False)
            db.session.add(user)
            db.session.flush()
        record = db.session.get(Material, material["id"])
        if not record:
            record = Material(id=material["id"], class_id=classes[material["class"]], subject_id=subjects[key], uploader_id=user.id, title=material["title"], original_filename=f"{material['id']}.md", storage_path="seeded", content_type="text/markdown")
            db.session.add(record)
            db.session.flush()
            entry = KnowledgeEntry(material_id=record.id, class_id=record.class_id, subject_id=record.subject_id, body_text=material["text"])
            db.session.add(entry)
            db.session.commit()
        else:
            entry = KnowledgeEntry.query.filter_by(material_id=record.id).one()
            if entry.body_text != material["text"]:
                raise ValueError("Fixture source changed; use a fresh disposable database")
        if _eligible_query(0, False).filter(KnowledgeEntry.id == entry.id).first():
            index_entry(entry)
            db.session.commit()
    # Denied classes/subjects deliberately exist but contain no allowed evidence.
    for case in corpus["cases"]:
        code = f"Q-{case['scope']['class']}"
        if case["scope"]["class"] not in classes:
            school_class = SchoolClass.query.filter_by(code=code).first()
            if not school_class:
                school_class = SchoolClass(code=code, name=code)
                db.session.add(school_class)
                db.session.flush()
            classes[case["scope"]["class"]] = school_class.id
    db.session.commit()
    return classes, subjects


def execute(corpus, config, split, modes):
    from app.database import db
    from app.retrieval import retrieve
    from app.providers import ProviderUnavailable
    from app.answers import answer_question, AnswerValidationError
    classes, subjects = load_fixture(corpus)
    results = []
    elapsed = {"db": 0.0, "embedding": 0.0, "chat": 0.0}
    from app.providers import embedding_client, chat_client
    def timed_factory(factory, method, stage):
        def create():
            client = factory()
            original = getattr(client, method)
            def measured(*args, **kwargs):
                started = time.perf_counter()
                try:
                    return original(*args, **kwargs)
                finally:
                    elapsed[stage] += (time.perf_counter() - started) * 1000
            setattr(client, method, measured)
            return client
        return create
    def before(conn, cursor, statement, parameters, context, many):
        context.quality_start = time.perf_counter()
    def after(conn, cursor, statement, parameters, context, many):
        elapsed["db"] += (time.perf_counter() - context.quality_start) * 1000
    event.listen(db.engine, "before_cursor_execute", before)
    event.listen(db.engine, "after_cursor_execute", after)
    timers = ExitStack()
    timers.enter_context(patch('app.retrieval.embedding_client', timed_factory(embedding_client, 'embed_batch', 'embedding')))
    timers.enter_context(patch('app.answers.chat_client', timed_factory(chat_client, 'answer', 'chat')))
    try:
        for case in corpus["cases"]:
            if case["split"] != split or case["category"] == "permission":
                continue  # HTTP permission scenarios are a separate required suite.
            selected_modes = ["ask"] if case["category"] in {"answer", "adversarial"} else modes
            for mode in selected_modes:
                for stage in elapsed:
                    elapsed[stage] = 0.0
                started = time.perf_counter()
                row = {"case_id": case["id"], "mode": mode}
                if (mode != "keyword" and config["EMBEDDING_PROVIDER"] == "deterministic") or (mode == "ask" and config["CHAT_PROVIDER"] == "deterministic"):
                    results.append({**row, "status": "incomplete", "reason": "real_provider_required"})
                    continue
                scoped = {subjects[(case["scope"]["class"], subject)] for subject in case["scope"]["subjects"] if (case["scope"]["class"], subject) in subjects}
                try:
                    if mode == "ask":
                        output = answer_question(class_id=classes[case["scope"]["class"]], subject_ids=scoped, question=case["query"], include_claims=True)
                        row.update(status="ok", answer=output["answer"], answer_status=output["status"], demo_mode=output["demo_mode"], citations=output["citations"], claims=output.get('claims', []), human_review="pending")
                    else:
                        output = retrieve(class_id=classes[case["scope"]["class"]], subject_ids=scoped, query=case["query"], mode=mode, limit=10)
                        hits = [{"material": h["material_id"], "chunk_id": h["chunk_id"], "source_spans": h.get("source_spans", []), "excerpt": h["excerpt"]} for h in output["hits"]]
                        row.update(status="ok", hits=hits, chat_calls=0)
                except (ProviderUnavailable, AnswerValidationError):
                    row.update(status="incomplete", reason="provider_or_response_unavailable")
                row["latency_ms"] = {**elapsed, "total": (time.perf_counter() - started) * 1000}
                results.append(row)
    finally:
        timers.close()
        event.remove(db.engine, "before_cursor_execute", before)
        event.remove(db.engine, "after_cursor_execute", after)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["dev", "release"], default="dev")
    parser.add_argument("--modes", nargs="+", choices=["keyword", "vector", "hybrid"], default=["keyword", "vector", "hybrid"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, default=Path(__file__).with_name("corpus-v1.json"))
    args = parser.parse_args()
    url = os.environ.get("DATABASE_URL", "")
    if os.getenv("QUALITY_DISPOSABLE_DATABASE") != "true" or not make_url(url).database.startswith("quality_"):
        parser.error("evaluation requires an explicitly disposable quality_* PostgreSQL database")
    from app import create_app
    from app.database import initialize_database
    app = create_app({"INITIALIZE_DATABASE": False, "SEED_DEMO_DATA": False})
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    validate_corpus(corpus)
    with app.app_context():
        initialize_database()
        results = execute(corpus, app.config, args.split, args.modes)
        metadata = {"embedding_provider": app.config["EMBEDDING_PROVIDER"], "embedding_model": app.config["EMBEDDING_MODEL"], "embedding_revision": app.config.get("EMBEDDING_REVISION", "unconfirmed"), "dimensions": app.config["EMBEDDING_DIMENSIONS"], "chat_provider": app.config["CHAT_PROVIDER"], "chat_model": app.config["CHAT_MODEL"], "hardware": platform.platform(), "structural_browser_performance_gates": "incomplete"}
        from app.profiles import profile_identity, PROCESSING_VERSION
        from app.retrieval import RETRIEVAL_VERSION
        from app.providers import CHAT_PROMPT_VERSION
        import hashlib
        metadata.update(profile_fingerprint=profile_identity()["fingerprint"], processing_version=PROCESSING_VERSION, vector_threshold=app.config["VECTOR_THRESHOLD"], corpus_hash=hashlib.sha256(args.corpus.read_bytes()).hexdigest())
        metadata.update(retrieval_version=RETRIEVAL_VERSION, chat_prompt_version=CHAT_PROMPT_VERSION)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".results.json").write_text(json.dumps({"metadata": metadata, "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = summarize(corpus, results, metadata, args.split)
    write_report(report, args.output)
    return 0 if report["semantic_release_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
