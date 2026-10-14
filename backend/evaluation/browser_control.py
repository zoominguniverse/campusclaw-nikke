"""Reversible fault controls confined to the disposable UI fixture."""
import os
from pathlib import Path
import sys
from sqlalchemy.engine import make_url

if os.getenv('QUALITY_DISPOSABLE_DATABASE') != 'true' or make_url(os.environ['DATABASE_URL']).database != 'quality_browser':
    raise RuntimeError('requires isolated quality_browser database')

from app import create_app
from app.database import db
from app.models import ClassMembership, KnowledgeChunk, Material, User

app = create_app({'INITIALIZE_DATABASE': False, 'SEED_DEMO_DATA': False})
with app.app_context():
    command = sys.argv[1]
    if command in {'fault-on', 'fault-off'}:
        marker = Path('/tmp/quality-provider-fail')
        marker.touch() if command == 'fault-on' else marker.unlink(missing_ok=True)
    elif command in {'legacy', 'modern'}:
        material = Material.query.filter_by(class_id=1, title='浏览器验证原文').one()
        KnowledgeChunk.query.filter_by(material_id=material.id, searchable_active=True).update({'provenance_version': 'legacy' if command == 'legacy' else 'source-map-v1'})
        db.session.commit()
    elif command in {'revoke', 'restore'}:
        user = User.query.filter_by(username='zhouchengxi').one()
        if command == 'revoke':
            ClassMembership.query.filter_by(user_id=user.id, class_id=user.class_id).delete()
        elif not ClassMembership.query.filter_by(user_id=user.id, class_id=user.class_id).first():
            db.session.add(ClassMembership(user_id=user.id, class_id=user.class_id, is_teacher=False))
        db.session.commit()
    else:
        raise ValueError('unsupported fixture command')
