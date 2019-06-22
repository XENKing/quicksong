from argparse import ArgumentParser

import parsing


def main():
    arg_parser = ArgumentParser(
        prog="osu! beatmap downloader",
        description="App to download beatmaps from osu! site. If beatmap cannot be downloaded from the main site"
                    "(for whatever reason), retry from bloodcat.com")
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
        "-a", "--auto-start",
        dest="auto_start",
        action="store_true",
        help="If specified, automatic open beatmap when it finished downloading")

    group = arg_parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "urls",
        nargs='*',
        default=[],
        help="Beatmap links")
    group.add_argument(
        "-l", "--list-urls",
        nargs='?',
        dest="list_urls",
        help="File with beatmap links")

    args = arg_parser.parse_args()
    urls = []
    if args.list_urls is not None:
        print("Using links file")
        with open(args.list_urls) as f:
            urls = f.read().splitlines()
    else:
        print("Using urls")
        urls = args.urls

    song_ids = [parsing.get_song_id(url) for url in urls if url]

    parsing.parse_songs(song_ids, args.config_path, args.download_path, args.songs_path, args.auto_start)


if __name__ == '__main__':
    main()
