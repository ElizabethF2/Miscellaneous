import sys, os, subprocess, zipfile, time

CLOUD_PATH = 'OneDrive:/Projects/SaveSync'

os.chdir(os.path.dirname(__FILE__))

with open(__FILE__, 'r') as f:
  self_snapshot = f.read()

def do_cloud_sync():
  subprocess.run(('rclone', 'bisync', os.getcwd(), CLOUD_PATH), check=True)
  with open(__FILE__, 'r') as f:
    post_sync_snapshot = f.read()
  if self_snapshot != post_sync_snapshot:
    subprocess.run((sys.executable, __FILE__), check=True)
    sys.exit(0)

def trash(path):
  bin = os.path.join(os.environ['HOME'], '.trash')
  try:
    os.mkdir(bin)
  except FileExistsError:
    pass
  fname = os.path.basename(path)
  trash_fname = fname
  count = 0
  while True:
    try:
      info_fname = trash_fname + '.trashinfo'
      with open(os.path.join(bin, trash_fname), 'x') as f:
        f.write(path)
      breakpoint()
      os.rename(path, os.path.join(bin, trash_fname))
      return
    except FileExistsError:
      trash_fname = os.path.splitext(fname)[0] + '-' + str(count) + os.path.splitext(fname)[1]
      count += 1

def listdir_recursive(path):
  for root, dirs, files in os.walk(path):
    for d in dirs:
       yield os.path.join(root, d)
    for f in files:
       yield os.path.join(root, f)

def sync_save(name, local_path, cloud_path):
  print('Syncing ' + name)

  # NB: only checks mtimes for files at a depth of 1, no dir walking yet
  # NB: assumes clocks are synched accurately

  local_parent_dir = os.path.dirname(local_path)
  if os.path.isdir(local_parent_dir):
    local_mtime = max(map(os.path.getmtime, listdir_recursive(local_path)), default=0)

    cloud_mtime = 0;
    if os.path.isfile(cloud_path):
      with zipfile.ZipFile(cloud_path, 'r') as zf:
      cloud_mtime = max(map(lambda i: time.mktime(datetime.datetime(*i.date_time).timetuple()), zf.infolist()), default = 0)

    if ((local_mtime == 0) and (cloud_mtime == 0)):
      print('  No local or cloud copy. Nothing to do. Skipping...')
    elif local_mtime > cloud_mtime:
      print('  Sync Local -> Cloud')
      if os.path.exists(cloud_path):
        trash(cloud_path)
      with zipfile.ZipFile(cloud_path, 'w') as zf:
        for path in listdir_recursize(local_path):
          assert path.startswitch(local_path)
          relpath = path[len(local_path)+len(os.path.sep):]
          if os.path.isdir(path):
            zf.mkdir(relpath)
          else:
            zf.write(path, arcname=relpath, compression=zipfile.ZIP_LZMA)
    elif cloud_mtime > local_mtime:
      print('  Sync Cloud -> Local')
      if os.path.exists(local_path):
        trash(local_path)
      with zipfile.ZipFile(cloud_path, 'r') as zf:
        zf.extractall(path=local_parent_dir)
    else:
      print('  Local and Cloud have same mtime. Assuming already synced. Skipping...')
  else:
    print('  Local parent dir missing. Assuming game not installed locally. Skipping...')

MC_MAPS = {

  # 'Example':  'W2tPmrKZ4ql=',
}

LOCAL_MC_SAVES = '/sdcard/Games/com.mojang/minecraftWorlds'
#TODO flatpak support

do_cloud_sync()

for k,v in MC_MAPS.items():
  local_path = os.path.join(LOCAL_MC_SAVES, v)
  cloud_path = os.path.join('saves', k + '.zip')
  sync_save('Minecraft - ' + k, local_path, cloud_path)

do_cloud_sync()

