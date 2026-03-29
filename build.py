from datetime import datetime
from pathlib import Path
from typing import Iterator
import json
import logging
import parse
import shutil

logger = logging.getLogger(__name__)


INDEX_FILE_PATH = Path('index.json')

index: dict = {}

def load_page_index():
    global index

    try:
        with open(INDEX_FILE_PATH, 'r') as fp:
            index = json.load(fp)
    except FileNotFoundError:
        logger.warning(f'Index file missing')
    except json.JSONDecodeError:
        logger.warning(f'Index file empty')


def dump_page_index():
    global index

    with open(INDEX_FILE_PATH, 'w+') as fp:
        json.dump(index, fp)


def get_page_index_entry(page: str) -> dict:
    global index

    return index.setdefault(page, {})


def get_page_metadata(page: str) -> dict:
    entry = get_page_index_entry(page)
    return entry.setdefault('metadata', {})


def set_page_metadata(page: str, metadata: dict):
    entry = get_page_index_entry(page)
    entry['metadata'] = metadata


def get_page_last_mtime(page: str) -> float:
    entry = get_page_index_entry(page)
    return entry.setdefault('mtime', 0)


def set_page_last_mtime(page: str, mtime: float):
    entry = get_page_index_entry(page)
    entry['mtime'] = mtime


def get_subpage_last_mtime(page: str, subpage: str) -> float:
    entry = get_page_index_entry(page)
    subpages: dict = entry.setdefault('subpages', {})
    return subpages.setdefault(subpage, 0)


def set_subpage_last_mtime(page: str, subpage: str, mtime: float):
    entry = get_page_index_entry(page)
    subpages: dict = entry.setdefault('subpages', {})
    subpages[subpage] = mtime


def iter_input_files(dirpath: Path) -> Iterator[Path]:
    yield from dirpath.glob('*.org')


def iter_input_file_subfiles(path: Path) -> Iterator[Path]:
    dirpath = path.parent / path.stem
    yield from dirpath.glob('*.org')


def file_needs_build(path: Path):
    page = path.stem

    mtime = path.stat().st_mtime
    last_mtime = get_page_last_mtime(page)
    needs_build = (mtime > last_mtime)

    set_page_last_mtime(page, mtime)

    logger.debug(f'Last modified: {datetime.fromtimestamp(mtime)}')

    for subpath in iter_input_file_subfiles(path):
        subpage = subpath.stem

        mtime = subpath.stat().st_mtime
        last_mtime = get_subpage_last_mtime(page, subpage)
        needs_build = needs_build or (mtime > last_mtime)

        set_subpage_last_mtime(page, subpage, mtime)

        logger.debug(f'> Subpage: "{subpage}"')
        logger.debug(f'> Last modified: {datetime.fromtimestamp(mtime)}')
    
    return needs_build


def build_input_file(path: Path):
    ast = parse.parse(path)

    # TODO Finish rewrite
    # metadata.setdefault('type', 'doc')
    # set_page_metadata(metadata)

    # views = render.render_page(fname, metadata, ast)

    # page_dir = output_dir / 'pages' / fname
    # for view_name, view_html in views:
    #     view_path = page_dir / view_name / 'index.html'
    #     view_path.parent.mkdir(parents=True, exist_ok=True)
    #     with open(view_path, 'w+', encoding='utf-8') as f:
    #         f.write(view_html)


def process_input_file(path: Path, force_rebuild=False):
    page = path.stem
    
    logger.info(f'Page: {page}')

    if force_rebuild or file_needs_build(path):
        logger.info(f'Building page')

        build_input_file(path)
    else:
        logger.debug(f'Page up-to-date; skipping build')


def process_input_dir(dirpath: Path, rebuild_all=False):
    for path in iter_input_files(dirpath):
        process_input_file(path, force_rebuild=rebuild_all)


def build_home_page(pages):
    # TODO Finish rewrite
    # home_html = render.render_home_page(index)
    # outpath = Path(output_dir, 'index.html')
    # with open(outpath, 'w+', encoding='utf-8') as f:
    #     f.write(home_html)
    ...


def make_output_dir(dirpath: Path, clean=False):
    if clean and dirpath.is_dir():
        shutil.rmtree(dirpath)
    dirpath.mkdir(parents=True, exist_ok=True)


def copy_resource_dirs(resource_dirs: list[Path], dest: Path):
    for dirpath in resource_dirs:
        shutil.copytree(dirpath, dest / dirpath.name, dirs_exist_ok=True)


def build(indir: Path,
          outdir: Path,
          resource_dirs: list[Path] | None = None,
          clean=False):
    # No need to load the index if rebuilding everything anyway
    if not clean:
        load_page_index()

    pages = process_input_dir(indir, rebuild_all=clean)

    home = build_home_page(pages)

    make_output_dir(outdir, clean)

    # TODO Write pages

    copy_resource_dirs(resource_dirs, outdir)

    dump_page_index()
