from unittest.mock import patch

import pytest
from app.extensions import db
from app.models import Material, KnowledgeEntry, KnowledgeIndexGeneration
from app.indexing import index_entry
from app.retrieval import retrieve, ReindexRequired


def test_empty_material_scope_skips_embedding_and_none_preserves_old_scope(app):
    with app.app_context():
        with patch('app.retrieval.embedding_client') as provider:
            assert retrieve(class_id=1,query='数学',material_ids=[])['hits'] == []
            provider.assert_not_called()
        assert retrieve(class_id=1,query='1 班数学示例材料内容',mode='keyword')['hits']


@pytest.mark.parametrize('mode', ['keyword','vector','hybrid'])
def test_only_bound_materials_compete_and_foreign_material_is_excluded(app, mode):
    with app.app_context():
        material = Material.query.filter_by(class_id=1).first()
        ident = material.id
        entry = KnowledgeEntry.query.filter_by(material_id=ident).one()
        entry.body_text = '去括号时，括号外面的数要乘到括号里的每一项。'
        db.session.commit()
        index_entry(entry,None)
        foreign = Material.query.filter_by(class_id=2).first()
        hits = retrieve(class_id=1,query='去括号',mode=mode,material_ids={ident,foreign.id})['hits']
        assert hits and {h['material_id'] for h in hits} == {ident}
        assert retrieve(class_id=1,query='去括号',mode=mode,material_ids={foreign.id})['hits'] == []


def test_incompatible_unbound_material_does_not_block(app):
    with app.app_context():
        original = Material.query.filter_by(class_id=1).first()
        source = Material(class_id=1,subject_id=original.subject_id,uploader_id=original.uploader_id,title='unbound',original_filename='x.txt',storage_path='seeded',content_type='text/plain')
        db.session.add(source)
        db.session.flush()
        entry = KnowledgeEntry(material_id=source.id,class_id=1,subject_id=source.subject_id,body_text='unbound math')
        db.session.add(entry)
        db.session.commit()
        # Unindexed sources are explicitly incompatible.
        with pytest.raises(ReindexRequired):
            retrieve(class_id=1,query='数学')
        assert retrieve(class_id=1,query='数学',material_ids={original.id})['hits']
