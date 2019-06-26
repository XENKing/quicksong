import os
import re
from pathlib import Path
from typing import FrozenSet, Generator, Optional

from vinanti import Vinanti

from config import Config


def get_song_id(url: str):
    song_id = re.split(r'/([0-9]{5,7})', url)
    int_id = None
    for raw_id in song_id:
        try:
            int_id = int(raw_id)
        except ValueError:
            pass
        else:
            break
    return int_id


class Parser:

    def __init__(self, song_urls, config_path=None, download_path=None, songs_path=None, auto_start=None) -> None:
        self._config = Config(config_path)
        self._config.update({'download_path': download_path, 'songs_path': songs_path})
        self._header = {"User-Agent": "Mozilla/5.0", "Cookie": self._config.get_cookie()}
        self.download_path = Path(self._config['download_path']).resolve(strict=True)
        self.songs_path = Path(self._config['songs_path']).resolve(strict=True)

        if len(song_urls) > 5:
            self.vnt = Vinanti(block=False, hdrs=self._header, binary=True, multiprocess=True, session=True, wait=5,
                               timeout=60, max_requests=5)
        else:
            self.vnt = Vinanti(block=False, hdrs=self._header, binary=True, session=True, wait=5,
                               timeout=60, max_requests=5)
        self.existed_ids: Optional[FrozenSet[int]] = frozenset(self.get_existing_ids())
        self.song_ids = []
        self.auto_start = auto_start
        self.urls_to_ids(song_urls)

    def urls_to_ids_callback(self, *args):
        new_url = args[-1].url
        self.song_ids.append(get_song_id(new_url))

    def get_existing_ids(self) -> Generator[int, None, None]:
        if not self.songs_path.is_dir():
            raise IsADirectoryError

        for beatmap in self.songs_path.iterdir():
            match = re.search(r"(\d+)", beatmap.name)

            if match:
                yield int(match.group(1))

    def urls_to_ids(self, urls: list):
        for url in urls:
            new_url = re.sub(r'/b/', '/beatmaps/', url)

            if not new_url == url:
                vnt = Vinanti(block=True, hdrs={"User-Agent": "Mozilla/5.0"}, timeout=10)
                vnt.head(new_url, onfinished=self.urls_to_ids_callback)
            else:
                self.song_ids.append(get_song_id(url))

    def postdownloading_callback(self, *args):
        r = args[-1]
        if r.status == 429:
            print("Error 429: retrying: ", args[-2])
            song_id = get_song_id(args[-2])
            self.vnt.get(f"http://osu.ppy.sh/beatmapsets/{song_id}/download?noVideo=1",
                         onfinished=self.postdownloading_callback,
                         out=str(self.download_path.joinpath(f"beatmap_{song_id}.osz")))
        try:
            old_filename = Path(r.out_file).resolve(strict=True)
            name = r.info._headers[6][1].split('"')[1::2][0]
            name = re.sub(r'[^\w_.)( -]', '', name)
            name = old_filename.parent.joinpath(name)
            old_filename.replace(name)
        except Exception as e:
            print(e)
            print(f"Failed to rename beatmap: {args[-2]}")
            pass
        else:
            if self.auto_start:
                os.startfile(name)
            print(f"Successfully downloaded: {name}")

    def parse_songs(self):
        for idx in range(len(self.song_ids) - 1, -1, -1):
            song_id = self.song_ids.pop(idx)
            if song_id in self.existed_ids:
                print(f"Beatmap already exist: {song_id}")
            else:
                self.vnt.get(f"http://osu.ppy.sh/beatmapsets/{song_id}/download?noVideo=1",
                             onfinished=self.postdownloading_callback,
                             out=str(self.download_path.joinpath(f"beatmap_{song_id}.osz")))
