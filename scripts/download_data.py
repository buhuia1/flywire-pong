"""Fetch the versioned runtime matrices, verifying every byte before installation."""
from pathlib import Path
import hashlib,json,os,tempfile,urllib.request,zipfile

ROOT=Path(__file__).resolve().parents[1]
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def main():
 manifest=json.loads((ROOT/'data/runtime-download.json').read_text())
 if all((ROOT/name).is_file() and digest(ROOT/name)==meta['sha256'] for name,meta in manifest['files'].items()):
  print('Runtime data already present and verified.');return
 with tempfile.TemporaryDirectory(prefix='flywire-pong-') as temp:
  archive=Path(temp)/'runtime.zip'
  request=urllib.request.Request(manifest['url'],headers={'User-Agent':'FlyWire-Pong-data-downloader'})
  print('Downloading 112 MiB of runtime data from GitHub Releases...',flush=True)
  with urllib.request.urlopen(request,timeout=180) as response,archive.open('wb') as out:
   for block in iter(lambda:response.read(1024*1024),b''):out.write(block)
  if archive.stat().st_size!=manifest['bytes'] or digest(archive)!=manifest['sha256']:raise RuntimeError('Archive checksum mismatch')
  with zipfile.ZipFile(archive) as z:
   if set(z.namelist())!=set(manifest['files']):raise RuntimeError('Unexpected archive contents')
   staged=[]
   for name,meta in manifest['files'].items():
    # Only exact, version-controlled manifest paths are permitted.
    target=(ROOT/name).resolve()
    if target.parent!=(ROOT/'data').resolve():raise RuntimeError('Unsafe data path')
    temporary=Path(temp)/target.name
    with z.open(name) as source,temporary.open('wb') as out:
     for block in iter(lambda:source.read(1024*1024),b''):out.write(block)
    if temporary.stat().st_size!=meta['bytes'] or digest(temporary)!=meta['sha256']:raise RuntimeError('Data checksum mismatch: '+name)
    staged.append((temporary,target))
  for source,target in staged:
   target.parent.mkdir(exist_ok=True)
   # Copy to the destination volume, then replace atomically.
   pending=target.with_suffix('.tmp')
   with source.open('rb') as src,pending.open('wb') as dst:
    for block in iter(lambda:src.read(1024*1024),b''):dst.write(block)
   os.replace(pending,target)
 print('Both full matrices verified and ready.')

if __name__=='__main__':main()
