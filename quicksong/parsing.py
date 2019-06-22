import os
import re
import sys
import requests
from multiprocessing.dummy import Pool as ThreadPool
from pathlib import Path
from typing import FrozenSet, Generator, Optional
from urllib.error import URLError, HTTPError
from time import sleep

from config import Config
from cookiesApi import CookiesApi


def get_cacert():
    if getattr(sys, 'frozen', False):
        # if frozen, get embeded file
        return os.path.join(os.path.dirname(sys.executable), 'cacert.pem')
    else:
        # else just get the default file
        return requests.certs.where()


def get_existing_ids(songs_path: str) -> Generator[int, None, None]:
    path: Path = Path(songs_path).resolve(strict=True)

    if not path.is_dir():
        raise IsADirectoryError

    for beatmap in path.iterdir():
        match = re.match(r"(\d+)", beatmap.name)

        if match:
            yield int(match.group((1)))


def get_song_id(url: str):
    if re.match(r'/b/', url):
        old_url = url + "#osu-site-switcher"
        new_url = requests.get(url).url
    else:
        new_url = url

    song_id = re.split(r'/([0-9]{5,7})', new_url)
    int_id = None
    for raw_id in song_id:
        try:
            int_id = int(raw_id)
        except ValueError:
            pass
        else:
            break
    return int_id


def parse_songs(song_ids, config_path=None, download_path=None, songs_path=None, auto_start=None):
    config = Config(config_path)
    config.update({'download_path': download_path, 'songs_path': songs_path})
    config_download_path: Path = Path(config['download_path'])

    existing_ids: Optional[FrozenSet[int]] = frozenset(get_existing_ids(config['songs_path']))

    cookies: CookiesApi = CookiesApi(config).cookies

    for song_id in song_ids:
        if song_id in existing_ids:
            print(f"Beatmap already exist:   {song_id}")
            song_ids.remove(song_id)

    def get_song(s_id):
        urls = [
            f"http://osu.ppy.sh/beatmapsets/{s_id}/download?noVideo=1",
            f"http://osu.ppy.sh/d/{s_id}",
            f"http://bloodcat.com/osu/s/{s_id}"
        ]
        head_url = f"http://osu.ppy.sh/beatmapsets/{s_id}"

        for url in urls:
            try:
                print(f"Beatmap {s_id}: {url}")
                read = requests.get(url, cookies=cookies, verify=True)
                while read.status_code == 429:
                    sleep(10)
                    read = requests.get(url, cookies=cookies, verify=True)

                filename = config_download_path.joinpath("beatmap_" + str(s_id) + ".osz")
                with open(str(filename), 'wb') as w:
                    for chunk in read.iter_content(chunk_size=512):
                        if chunk:
                            w.write(chunk)
                head = requests.get(head_url)
                get_beatmap_name = None
                for i, chunk in enumerate(head.iter_content(chunk_size=512)):
                    if chunk and i == 4:
                        get_beatmap_name = re.search(r'<title>([^\xB7]*)\s+[\xB7]', chunk.decode('utf8'), re.IGNORECASE)
                        break
                del head
                if get_beatmap_name:
                    valid_file_name = re.sub(r'[^\w_.)( -]', '', str(s_id) + " " + get_beatmap_name.group(1) + ".osz")
                    named_beatmap = config_download_path.joinpath(valid_file_name)
                    filename.replace(named_beatmap)
                    # print("Beatmap saved in:", named_beatmap)
            except HTTPError as e:
                print("The server couldn't fulfill the request")
                print(f"Url: {url}")
                print("Error code: ", e.code)
                return
            except URLError as e:
                print("We failed to reach a server")
                print(f"Url: {url}")
                print("Reason: ", e.reason)
                return
            else:
                if auto_start:
                    os.startfile(filename)
            print(f"Successfully downloaded: {s_id}")
            return
        else:
            print(f"Failed to download: {s_id}")

    pool = ThreadPool()
    pool.map(get_song, song_ids)

    pool.close()
    pool.join()
