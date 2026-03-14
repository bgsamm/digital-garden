from datetime import datetime
import shutil
import os
import json
import argparse
from pathlib import Path
import sys
import io
import logging
logger = logging.getLogger(__name__)
import render
import parse
import util

INDEX_FILE_PATH = Path('index.json')
DEFAULT_PAGES_DIR = Path('pages')
DEFAULT_STYLES_DIR = Path('styles')
DEFAULT_SCRIPTS_DIR = Path('scripts')
DEFAULT_BUILD_DIR = Path('build')
DEFAULT_LOGFILE_PATH = Path('log.txt')

def init_logging(console_level=logging.NOTSET, 
                 logfile_level=logging.NOTSET,
                 logfile_path=None):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.NOTSET)

    formatter = logging.Formatter('[%(module)s:%(levelname)s] %(message)s')

    if console_level != logging.NOTSET:
        utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        console_handler = logging.StreamHandler(utf8_stdout)
        console_handler.setLevel(console_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    if logfile_level != logging.NOTSET and logfile_path is not None:
        logfile_handler = logging.FileHandler(logfile_path, encoding='utf-8', mode='w')
        logfile_handler.setLevel(logfile_level)
        logfile_handler.setFormatter(formatter)
        root_logger.addHandler(logfile_handler)

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-i', '--pages-dir',
        type=Path,
        default=DEFAULT_PAGES_DIR)
    parser.add_argument(
        '--styles-dir',
        type=Path,
        default=DEFAULT_STYLES_DIR)
    parser.add_argument(
        '--scripts-dir',
        type=Path,
        default=DEFAULT_SCRIPTS_DIR)
    parser.add_argument(
        '-o', '--build-dir',
        type=Path,
        default=DEFAULT_BUILD_DIR)
    parser.add_argument(
        '--console-log-level',
        type=str,
        default='INFO')
    parser.add_argument(
        '--logfile-log-level',
        type=str,
        default='DEBUG')
    parser.add_argument(
        '--logfile-path',
        type=Path,
        default=DEFAULT_LOGFILE_PATH)

    return parser.parse_args()

def load_page_index():
    index = {}

    try:
        with open(INDEX_FILE_PATH, 'r') as fp:
            index = json.load(fp)
    except FileNotFoundError:
        logger.warning(f'Index file missing')
    except json.JSONDecodeError:
        logger.warning(f'Index file empty')

    return index

def dump_page_index(index):
    with open(INDEX_FILE_PATH, 'w+') as fp:
        json.dump(index, fp)

def get_input_pages(input_dir):
    input_walker = input_dir.walk(top_down=True)

    # Get page list from root directory
    dirpath, _, filenames = next(input_walker)
    pages = {os.path.splitext(fname)[0]:[] for fname in filenames}

    # Subdirectories contain subpages
    for dirpath, _, filenames in input_walker:
        pages[dirpath.name] = filenames

    return pages

def main(args):
    input_dir = args.pages_dir
    styles_dir = args.styles_dir
    scripts_dir = args.scripts_dir
    output_dir = args.build_dir

    pages = get_input_pages(input_dir)
    logger.debug(f'Pages: {pages}')

    index = load_page_index()
    logger.debug(f'Index: {index}')

    for fname in pages:
        metadata = index.setdefault(fname, {})

        fpath = input_dir / (fname + '.org')
        mtime = fpath.stat().st_mtime

        logger.info(f'Page: {fname}')
        logger.debug(f'Last modified: {datetime.fromtimestamp(mtime)}')

        last_mtime = metadata.get('mtime', 0)
        do_build = (mtime > last_mtime)
        metadata['mtime'] = mtime

        subpages = metadata.setdefault('subpages', {})
        for subpage in pages[fname]:
            subpath = input_dir / fname / subpage
            sub_mtime = subpath.stat().st_mtime

            logger.debug(f'> Subpage: "{subpath}"')
            logger.debug(f'> Last modified: {datetime.fromtimestamp(sub_mtime)}')

            last_mtime = subpages.get(subpage, 0)
            do_build = do_build or (sub_mtime > last_mtime)
            subpages[subpage] = sub_mtime

        if do_build:
            logger.info(f'Rendering page')
            meta, ast = parse.parse_org_file(fpath)
            meta.setdefault('type', 'doc')
            metadata |= meta

            views = render.render_page(fname, metadata, ast)

            page_dir = output_dir / 'pages' / fname
            for view_name, view_html in views:
                view_path = page_dir / view_name / 'index.html'
                view_path.parent.mkdir(parents=True, exist_ok=True)
                with open(view_path, 'w+', encoding='utf-8') as f:
                    f.write(view_html)
        else:
            logger.info(f'Page up-to-date; skipping render')

    output_dir.mkdir(parents=True, exist_ok=True)

    home_html = render.render_home_page(index)
    outpath = Path(output_dir, 'index.html')
    with open(outpath, 'w+', encoding='utf-8') as f:
        f.write(home_html)

    styles_out = output_dir / 'styles'
    shutil.copytree(styles_dir, styles_out, dirs_exist_ok=True)

    scripts_out = output_dir / 'scripts'
    shutil.copytree(scripts_dir, scripts_out, dirs_exist_ok=True)

    # TODO: Delete orphaned pages

    dump_page_index(index)

if __name__ == '__main__':
    args = parse_args()

    init_logging(console_level=args.console_log_level,
                 logfile_level=args.logfile_log_level,
                 logfile_path=args.logfile_path)

    main(args)
