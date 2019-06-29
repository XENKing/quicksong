from functools import partial
from itertools import cycle

from fake_useragent import UserAgent
from lxml.html import fromstring
from vinanti import Vinanti


class Proxy:

    def __init__(self, proxy_url=None, proxy_numbers=20):
        self.proxy_url = proxy_url if proxy_url else "https://www.sslproxies.org/"
        self.proxies = set()
        self.user_agent = UserAgent()
        self._usage_cnt = 0
        self._valid_proxies = set()
        self._proxy_num = proxy_numbers if 0 < proxy_numbers < 101 else 20
        self.__get_proxies__()
        self._proxy_pool = cycle(self.proxies)

    def __get_proxies_callback__(self, vnt, *args):
        parser = fromstring(args[-1].html)
        for tr in parser.xpath("//tbody/tr")[:self._proxy_num]:
            p = ":".join([tr.xpath(".//td[1]/text()")[0], tr.xpath(".//td[2]/text()")[0]])
            self.proxies.add(p)
        if vnt.tasks_remaining() == 0:
            del vnt

    def __get_proxies__(self):
        vnt = Vinanti(block=True, multiprocess=True, timeout=10)
        vnt.get(self.proxy_url, hdrs={"User-Agent": self.get_useragent()},
                onfinished=partial(self.__get_proxies_callback__, vnt))

    def get_after(self, interval=10, groups=1):
        current_p = [self.get() for _ in range(groups)]
        for p in range(int(self._proxy_num / groups) * interval):
            if p % interval == 0:
                current_p = [self.get() for _ in range(groups)]
            self._usage_cnt += 1
            for group_p in current_p:
                yield group_p

    def get(self):
        if self._usage_cnt > 1000:
            self.refresh()
        self._usage_cnt += 1
        return next(self._proxy_pool)

    def get_useragent_after(self, interval=10, groups=1):
        current_ua = [self.user_agent.chrome for _ in range(groups)]
        for p in range(int(self._proxy_num / groups) * interval):
            if p % interval == 0:
                current_ua = [self.user_agent.chrome for _ in range(groups)]
            for group_ua in current_ua:
                yield group_ua

    def __test_proxies_callback__(self, vnt, proxy, *args):
        r = args[-1]
        if not r or r.error:
            print(r.error)
            self.proxies.remove(proxy)

        if vnt.tasks_remaining() == 0:
            print("valid proxies: ", len(self.proxies))
            del vnt
            self.test_proxies("http://osu.ppy.sh/")

    def test_proxies(self, test_url=None):
        vnt = Vinanti(block=False, multiprocess=True, timeout=30)
        url = test_url if test_url else "http://osu.ppy.sh/legal/terms"
        for p in self.proxies:
            vnt.head(url, hdrs={"User-Agent": self.get_useragent()}, proxies={"http": "http://{}/".format(p), },
                     wait=0.5, onfinished=partial(self.__test_proxies_callback__, vnt, p))

    def get_useragent(self):
        return self.user_agent.chrome

    def refresh(self):
        self.__get_proxies__()
        self._usage_cnt = 0
