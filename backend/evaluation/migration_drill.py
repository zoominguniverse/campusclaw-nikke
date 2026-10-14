"""Real-provider upgrade/rollback drill on an explicitly restored disposable copy."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from sqlalchemy import text
from sqlalchemy.engine import make_url


def snapshot(db, uploads):
    sources = dict(db.session.execute(text('SELECT id,body_text FROM knowledge_entries')).all())
    vectors = dict(db.session.execute(text('SELECT id,embedding::text FROM knowledge_chunks WHERE embedding IS NOT NULL')).all())
    files = {str(p.relative_to(uploads)): hashlib.sha256(p.read_bytes()).hexdigest() for p in uploads.rglob('*') if p.is_file()}
    return {'sources': {str(k): hashlib.sha256(v.encode()).hexdigest() for k,v in sources.items()},
            'legacy_vectors': {str(k): hashlib.sha256(v.encode()).hexdigest() for k,v in vectors.items()}, 'files': files}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--legacy-root', type=Path, required=True)
    args = parser.parse_args()
    url = make_url(os.getenv('DATABASE_URL','sqlite://'))
    if os.getenv('QUALITY_DISPOSABLE_DATABASE') != 'true' or url.get_backend_name() != 'postgresql' or not (url.database or '').startswith('quality_'):
        parser.error('requires an explicitly disposable restored quality_* PostgreSQL database')
    from app import create_app
    from app.database import db, initialize_database
    from app.indexing import backfill_entries, _eligible_query
    from app.generation_restore import restore_generation
    from app.models import KnowledgeIndexGeneration
    from app.providers import ProviderUnavailable
    from app.profiles import profile_identity
    app = create_app({'INITIALIZE_DATABASE':False,'SEED_DEMO_DATA':False,'SEMANTIC_RELEASE':False})
    if app.config['EMBEDDING_PROVIDER'] != 'openai-compatible':
        parser.error('real embedding provider required')
    report = {'semantic_release_passed':False,'status':'incomplete','checks':{}}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    try:
        with app.app_context():
            uploads = Path(app.config['UPLOAD_DIR'])
            before = snapshot(db,uploads)
            old = dict(db.session.execute(text('SELECT knowledge_entry_id,id FROM knowledge_index_generations WHERE is_current')).all())
            assert old and before['sources'] and before['files']
            initialize_database(); initialize_database()
            assert snapshot(db,uploads) == before
            report['checks']['upgrade_twice_preserves_hashes'] = True
            current = lambda: dict(db.session.execute(text('SELECT knowledge_entry_id,id FROM knowledge_index_generations WHERE is_current')).all())
            dry = backfill_entries(100,force=True,dry_run=True)
            assert dry['completed']==0 and dry['failed']==0 and current()==old
            report['dry_run'] = dry
            first = backfill_entries(2,force=True)
            assert first['completed']==2 and first['failed']==0 and first['has_more']
            resumed = backfill_entries(100,force=True,after=first['cursor'])
            assert resumed['failed']==0 and not resumed['has_more']
            assert first['completed']+resumed['completed']==len(old)
            assert _eligible_query(0,False).count()==0
            report['checks']['real_force_resume_complete'] = True
            ready = current()
            with patch('app.indexing.embedding_client',side_effect=ProviderUnavailable('controlled disposable failure')):
                failed = backfill_entries(1,force=True)
            assert failed['failed']==1 and current()==ready
            retried = backfill_entries(1,force=True)
            assert retried['completed']==1 and retried['failed']==0
            report['checks']['failed_build_keeps_current_and_real_retry_recovers'] = True
            assert not list(db.session.execute(text('SELECT knowledge_entry_id FROM knowledge_index_generations WHERE is_current GROUP BY knowledge_entry_id HAVING count(*)<>1')))
            assert snapshot(db,uploads)==before
            report['checks']['current_unique_and_source_file_old_vectors_unchanged'] = True
            report.update(profile_fingerprint=profile_identity()['fingerprint'],before_hashes=before,compatible_entries=len(old),force_first=first,resume=resumed,retry=retried)
            for entry_id,generation_id in old.items():
                active=current()
                assert restore_generation(entry_id,generation_id,legacy_only=True,dry_run=True)['status']=='dry_run'
                assert current()==active
                restore_generation(entry_id,generation_id,legacy_only=True)
            assert current()==old and snapshot(db,uploads)==before
            report['checks']['legacy_current_restored_before_old_application'] = True
            from app.models import KnowledgeEntry, KnowledgeChunk
            from app.retrieval import retrieve
            for entry_id,generation_id in old.items():
                entry=db.session.get(KnowledgeEntry,entry_id)
                chunk=KnowledgeChunk.query.filter_by(generation_id=generation_id).first()
                assert retrieve(class_id=entry.class_id,subject_ids={entry.subject_id},query=chunk.chunk_text[:50],mode='keyword')['hits']
            report['checks']['restored_legacy_keyword_works_in_new_app'] = True
            db.session.rollback()
        # Run the actual pre-change app in a separate interpreter on this copy.
        code = '''
import json,sys
sys.path.insert(0,sys.argv[1])
from app import create_app
from app.database import db
from app.models import User,KnowledgeEntry
from app.security import hash_password
app=create_app({'INITIALIZE_DATABASE':False,'SEED_DEMO_DATA':False})
with app.app_context():
 user=User.query.filter_by(username='linzimo').one()
 original=user.password_hash
 user.password_hash=hash_password('quality-rollback-only'); db.session.commit()
 try:
  client=app.test_client()
  assert client.get('/health').status_code==200
  login=client.post('/api/auth/login',json={'username':'linzimo','password':'quality-rollback-only'})
  assert login.status_code==200
  token=login.get_json()['access_token']
  entry=KnowledgeEntry.query.filter_by(class_id=user.class_id).first()
  for mode in ['keyword','vector','hybrid']:
   response=client.post('/api/classes/1/knowledge/retrieve',headers={'Authorization':'Bearer '+token},json={'query':entry.body_text,'mode':mode,'subject_id':entry.subject_id})
   assert response.status_code==200 and response.get_json()['hits']
  print(json.dumps({'health':True,'authenticated_keyword_vector_hybrid':True}))
 finally:
  user.password_hash=original; db.session.commit()
'''
        env={**os.environ,'EMBEDDING_PROVIDER':'deterministic','EMBEDDING_DIMENSIONS':'64','CHAT_PROVIDER':'deterministic','UPLOAD_DIR':'/tmp/legacy-verification-uploads'}
        checked=subprocess.run([sys.executable,'-c',code,str(args.legacy_root)],cwd='/tmp',env=env,capture_output=True,text=True,timeout=60)
        assert checked.returncode==0, 'old application verification failed'
        report['old_application']=json.loads(checked.stdout)
        report['status']='passed'
    except Exception as error:
        report.update(reason='drill_failed',error_type=type(error).__name__)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Migration drill:',report['status'])
    return 0 if report['status']=='passed' else 2


if __name__=='__main__':
    raise SystemExit(main())
