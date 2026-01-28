import os, re, urllib.request, urllib.parse, textwrap

default_user_agent = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36'

def make_fname_safe(s):
  return re.sub(r'[^a-zA-Z0-9- ]+', '_', s)

def main():
  download_dir = os.environ.get('PODCAST_DIR', '~/Downloads/Unscanned/Podcasts')
  download_dir = os.path.expandvars(os.path.expanduser(download_dir))
  max_recent_podcasts = int(os.environ.get('MAX_RECENT_PODCASTS', '30'))
  bufsize = int(os.environ.get('PODCAST_BUFSIZE', 1024**2))
  user_agent = os.environ.get('PODCAST_USER_AGENT', default_user_agent)

  print('Enter a podcast URL')
  url = input('> ')
  req = urllib.request.Request(url, headers={ 'User-Agent': user_agent})
  feed = urllib.request.urlopen(req).read().decode()
  m = re.search(r'(?s)<title.*?>(.+?)</title', feed)
  if m:
    feed_title = m.group(1).strip()
  else:
    feed_title = 'UNKNOWNFEED'
  episodes = []
  for item in re.findall(r'(?s)<item.*?>(.+?)</item', feed):
    m = re.search(r'(?s)<title.*?>(.+?)</title', item)
    if not m:
      print('Episode missing title:')
      textwrap.indent(item, '  ')
      raise Exception()
    episode = {'title': m.group(1)}
    m = re.search(r'(?s)<enclosure.+?url="(.+?)"', item)
    if not m:
      print('Episode missing URL:')
      textwrap.indent(item, '  ')
      raise Exception()
    episode['url'] = m.group(1)
    episodes.append(episode)
  print('')
  print(f'Feed: {feed_title}')
  print('')
  for idx, episode in enumerate(episodes[:max_recent_podcasts]):
    print(f'{idx}) {episode['title']}')
    print('')
  print('Enter episode numbers separated by tabs or spaces')
  nums = input('> ')
  for num in nums.split():
    print(f'Handling episode at {num}...')
    episode = episodes[int(num)]
    episode_url = episode['url']
    path = urllib.parse.urlparse(episode_url).path
    i = path.rfind('.')
    if i != -1:
      ext =  path[i:]
    else:
      ext = '.mp3'
    os.makedirs(download_dir, exist_ok = True)
    fname = os.path.join(download_dir,
                         make_fname_safe(feed_title) + ' - ' +
                         make_fname_safe(episode['title']) + ext)
    print(f'Downloading {fname}...')
    req = urllib.request.Request(episode_url, headers={ 'User-Agent': user_agent })
    res = urllib.request.urlopen(req)
    with open(fname, 'xb') as f:
      while True:
        buf = res.read(bufsize)
        if len(buf) < 1:
          break
        f.write(buf)
    print('')

if __name__ == '__main__':
  main()
