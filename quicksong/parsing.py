import os
import re
import sys
from copy import deepcopy
from functools import partial
from pathlib import Path
from typing import Generator

from config import Config
from connection import Proxy
from vinanti import Vinanti

errors = ['403', '404']
retry_errors = ['400', '429', '503' '10060', '10054', '10061', '100541',
                'Remote end closed connection without response']
retry_ids = set()


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


def get_existing_ids(paths) -> Generator[int, None, None]:
    for path in paths:
        if not path.is_dir():
            raise IsADirectoryError

        for beatmap in path.iterdir():
            match = re.search(r"(\d{4,7})", beatmap.name)
            if match:
                yield int(match.group(1))


class Parser:

    def __init__(self, song_urls, config_path=None, download_path=None, songs_path=None, auto_start=None, multiprocess=None,
                 use_proxy=None):
        self._config = Config(config_path)
        self._config.update({'download_path': download_path, 'songs_path': songs_path, 'use_proxy': use_proxy})
        self._header = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "Accept-Encoding": "gzip, deflate, br",
            "Cookie": self._config.get_cookie()}
        self._multiprocess = multiprocess if multiprocess else 6
        self._proxy = Proxy(proxy_numbers=100) if self._config['use_proxy'] else None
        self.download_path = Path(self._config['download_path']).resolve(strict=True)
        self.songs_path = Path(self._config['songs_path']).resolve(strict=True)
        vnt_args = {"wait": 3, "timeout": 30, "max_requests": 5, "log": False}
        if self._multiprocess:
            vnt_args.update({"multiprocess": True, "max_requests": self._multiprocess + 1})
        if self._proxy:
            vnt_args.update({"wait": 1, "timeout": 60})
        self.vnt = Vinanti(**vnt_args)
        self.existed_ids = frozenset(get_existing_ids([self.songs_path, self.download_path]))
        self.song_ids = []
        self.auto_start = auto_start
        self.urls_to_ids(song_urls)

    def urls_to_ids_callback(self, *args):
        new_url = args[-1].url
        self.song_ids.append(get_song_id(new_url))

    def urls_to_ids(self, urls: list):
        vnt = Vinanti(block=True, hdrs={"User-Agent": "Mozilla/5.0"}, timeout=10)
        for url in urls:
            new_url = re.sub(r'/b/', '/beatmaps/', url)

            if not new_url == url:
                vnt.head(new_url, onfinished=self.urls_to_ids_callback)
            else:
                self.song_ids.append(get_song_id(url))
        del vnt

    def postdownloading_callback(self, input_kwargs, *args):
        r = args[-1]
        url = args[-2]
        if not r:
            print("Error: No response\n")
            return
        song_id = get_song_id(url)
        if r.error:
            print(f"Error: {r.error}", file=sys.stderr)
            if any(err in r.error for err in errors):
                print(f"Error: Beatmap not found: {url}\n", file=sys.stderr)
            if any(rerr in r.error for rerr in retry_errors):
                print(f"{url}\nAdded retry after queue end\n")
                if input_kwargs and "proxies" in input_kwargs:
                    proxy = re.search(r"//([^/]*)/", input_kwargs["proxies"]["http"]).group(1)
                    if proxy in self._proxy.proxies:
                        self._proxy.proxies.remove(proxy)
                    if len(self._proxy.proxies) < 2:
                        print("No valid proxies, exiting\n")
                        del self._proxy
                return self.retry_download(url)
            return

        if r.url == 'https://osu.ppy.sh/p/error':
            print("Error: Osu site internal error", file=sys.stderr)
            return Path(r.out_file).unlink()

        try:
            old_filename = Path(r.out_file).resolve(strict=True)
            name = r.info._headers[6][1].split('"')[1::2][0]
            name = re.sub(r'[^\w_.)( -]', '', name)
            name = old_filename.parent.joinpath(name)
            old_filename.replace(name)
        except Exception as e:
            print(f"Error: Failed to rename beatmap: {url}\n{e}", file=sys.stderr)
            pass
        else:
            if self.auto_start:
                os.startfile(name)
            print(f"Successfully downloaded: {name.stem}")
            del old_filename, name
        del r, song_id

    def parse_songs(self, sids=None):
        hdr = self._header
        kwargs = {}
        sids = sids if sids else self.song_ids
        if self._proxy:
            kwargs["proxies"] = {"http": "http://{}/".format(self._proxy.get())}
            hdr = deepcopy(self._header)
            hdr.update({"User-Agent": self._proxy.get_useragent()})

        for idx in range(len(sids) - 1, -1, -1):
            sid = self.song_ids.pop(idx)
            if sid in self.existed_ids:
                continue
            if self._proxy and idx % 4 == 0:
                del hdr, kwargs
                kwargs = {"proxies": {"http": "http://{}/".format(self._proxy.get())}}
                hdr = deepcopy(self._header)
                hdr.update({"User-Agent": self._proxy.get_useragent()})

            self.__download_song__(sid, hdr, kwargs)
        print("tasks count: ", self.vnt.tasks_count())
        print("tasks remaining: ", self.vnt.tasks_remaining())

    def __download_song__(self, sid, hdrs, kwargs):
        url = "http://osu.ppy.sh/beatmapsets/{}/download".format(sid)
        self.vnt.get(url, hdrs=hdrs, onfinished=partial(self.postdownloading_callback, kwargs), params={'noVideo': '1'},
                     out=str(self.download_path.joinpath("beatmap_{}.osz".format(sid))), **kwargs)

    def retry_download(self, url):
        retry_ids.add(get_song_id(url))
        if self.vnt.tasks_remaining() < 2:
            self.parse_songs(retry_ids)

    def parse_songs_parallel_proxyes(self):
        for idx in range(len(self.song_ids) - 1, -1, -1):
            sid = self.song_ids[idx]
            if sid in self.existed_ids:
                self.song_ids.pop(idx)

        proxies = self._proxy.get_after(2, self._multiprocess)
        useragents = self._proxy.get_useragent_after(2, self._multiprocess)
        for group, proxy, useragent in zip(range(len(self.song_ids) - self._multiprocess, -1, -self._multiprocess),
                                           proxies, useragents):
            hdrs = [deepcopy(self._header) for _ in range(self._multiprocess)]
            for client, header in zip(range(self._multiprocess - 1, -1, -1), hdrs):
                sid = self.song_ids.pop(group + client)
                header.update({"User-Agent": useragent})
                self.__download_song__(sid, header, {"proxies": {"http": "http://{}/".format(proxy)}, "wait": 0.2})
            del hdrs
        print("tasks count: ", self.vnt.tasks_count())
        print("tasks remaining: ", self.vnt.tasks_remaining())
