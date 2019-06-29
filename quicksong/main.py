import multiprocessing
from argparse import ArgumentParser
from re import match

from parsing import Parser


def main():
    arg_parser = ArgumentParser(
        prog="osu! beatmaps downloader",
        description="App to download beatmaps from osu! site")
    arg_parser.add_argument(
        "-o", "--out",
        dest="download_path",
        help="Path to download folder")
    arg_parser.add_argument(
        "-s", "--songs-path",
        dest="songs_path",
        help="Path to osu!'s 'Songs' directory. If specified, existing beatmaps won't be downloaded")
    arg_parser.add_argument(
        "-c", "--config-path",
        dest="config_path",
        help="Path to configuration file")
    arg_parser.add_argument(
        "-m", "--multiprocess",
        dest="multiprocess",
        type=int,
        choices=range(4, 12),
        help="Program will run with the specified number (4-12) of subprocesses, instead of threads by default")
    arg_parser.add_argument(
        "-a", "--auto-start",
        dest="auto_start",
        action="store_true",
        help="If specified, automatic open beatmaps when it finished downloading")
    arg_parser.add_argument(
        "-p", "--use-proxy",
        dest="use_proxy",
        action="store_true",
        help="If specified, program will be used proxy to all connections")
    arg_parser.add_argument(
        "-pp", "--use-proxy-parallel",
        dest="use_proxy_parallel",
        action="store_true",
        help="If specified, program will be trying to use proxy on parallel download on each process")

    group = arg_parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "urls",
        nargs='*',
        default=[],
        help="Beatmaps urls or file with links")
    group.add_argument(
        "-d", "--dump-exists",
        nargs='?',
        dest="dump_path",
        help="Dump existed beatmaps to file")

    args = arg_parser.parse_args()
    urls = []
    for url in args.urls:
        if match(r"((https?):((//)|(\\\\))+([\w\d:#@%/;$()~_?+-=\\.&](#!)?)*)", url):
            print("Using urls")
            urls = args.urls
            break
        else:
            print("Using links file")
            with open(url) as f:
                urls = f.read().splitlines()
    use_proxy = True if args.use_proxy or args.use_proxy_parallel else False
    parser = Parser(urls, args.config_path, args.download_path, args.songs_path, args.auto_start, args.multiprocess, use_proxy)
    if args.dump_path is None:
        parser.parse_songs_parallel() if args.use_proxy_parallel else parser.parse_songs()
    else:
        with open(args.dump_path, 'w') as f:
            f.writelines([f"http://osu.ppy.sh/beatmapsets/{el}\n" for el in parser.existed_ids])


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
