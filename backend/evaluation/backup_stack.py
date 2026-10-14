"""Local Compose backup before development-stack upgrade; no secret output."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = '''
import hashlib,json
from pathlib import Path
from app import create_app
from app.models import KnowledgeEntry,KnowledgeChunk,Material
app=create_app({'INITIALIZE_DATABASE':False,'SEED_DEMO_DATA':False})
with app.app_context():
    root=Path('/app/uploads').resolve()
    entries={str(e.id):hashlib.sha256(e.body_text.encode('utf-8')).hexdigest() for e in KnowledgeEntry.query.all()}
    vectors={str(c.id):hashlib.sha256(json.dumps(c.embedding,separators=(',',':')).encode()).hexdigest() for c in KnowledgeChunk.query.all() if c.embedding is not None}
    files={}
    for m in Material.query.all():
        if m.storage_path=='seeded': continue
        path=(root/m.storage_path).resolve()
        if not path.is_relative_to(root) or not path.is_file(): raise RuntimeError('source file missing or outside upload root')
        files[str(m.id)]=hashlib.sha256(path.read_bytes()).hexdigest()
    print(json.dumps({'entries':entries,'legacy_vectors':vectors,'files':files},sort_keys=True))
'''

def run(arguments, destination):
    with destination.open('wb') as stream:
        subprocess.run(['docker', 'compose', *arguments], cwd=ROOT, stdout=stream, check=True)

def snapshot(destination):
    run(['exec','-T','api','python','-c',SNAPSHOT], destination)
    return json.loads(destination.read_text(encoding='utf-8'))

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'verify':
        directory = Path(sys.argv[2]).resolve()
        if not directory.is_relative_to(ROOT / '.retrieval-backups'): raise RuntimeError('backup must be inside the intended workspace directory')
        before = json.loads((directory/'before.json').read_text(encoding='utf-8')); after = snapshot(directory/'after.json')
        for key, values in before.items():
            if any(after[key].get(identifier) != value for identifier,value in values.items()): raise RuntimeError(f'{key} changed during upgrade')
        print('Preserved original sources, files and legacy vectors:', {key:len(value) for key,value in before.items()})
    else:
        directory=ROOT/'.retrieval-backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); directory.mkdir(parents=True)
        run(['exec','-T','postgres','sh','-c','pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc'], directory/'database.dump')
        run(['exec','-T','api','tar','-czf','-','-C','/app','uploads'], directory/'uploads.tar.gz')
        values=snapshot(directory/'before.json')
        manifest={path.name:{'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()} for path in directory.iterdir() if path.is_file()}
        (directory/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        print('Backup:',directory)
        print('Counts:', {key:len(value) for key,value in values.items()})
