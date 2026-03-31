from datetime import datetime
from page import Page
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


def get_page_index_entry(name: str) -> dict:
    global index

    return index.setdefault(name, {})


def get_page_metadata(name: str) -> dict:
    entry = get_page_index_entry(name)
    return entry.setdefault('metadata', {})


def set_page_metadata(name: str, metadata: dict):
    entry = get_page_index_entry(name)
    entry['metadata'] = metadata


def get_page_last_mtime(name: str) -> float:
    entry = get_page_index_entry(name)
    return entry.setdefault('mtime', 0)


def set_page_last_mtime(name: str, mtime: float):
    entry = get_page_index_entry(name)
    entry['mtime'] = mtime


def get_subpage_last_mtime(name: str, subpage: str) -> float:
    entry = get_page_index_entry(name)
    subpages: dict = entry.setdefault('subpages', {})
    return subpages.setdefault(subpage, 0)


def set_subpage_last_mtime(name: str, subpage: str, mtime: float):
    entry = get_page_index_entry(name)
    subpages: dict = entry.setdefault('subpages', {})
    subpages[subpage] = mtime


def write_file(path: Path, contents: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w+', encoding='utf-8') as f:
        f.write(contents)


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


def build_input_file(path: Path, outdir: Path):
    metadata, ast = parse.parse(path)

    page = Page(path.stem, metadata)
    
    for view in page.iter_views():
        write_file(outdir / view.url / 'index.html', view.render(ast))

    return page


def process_input_file(path: Path, outdir: Path, force_rebuild=False) -> Page:
    name = path.stem
    
    logger.info(f'Page: {name}')

    if force_rebuild or file_needs_build(path):
        logger.info(f'Building page')

        page = build_input_file(path, outdir)
    else:
        logger.debug(f'Page up-to-date; skipping build')

        metadata = get_page_metadata(name)
        page = Page(name, metadata)
    
    return page


def process_input_dir(indir: Path, outdir: Path, rebuild_all=False) -> list[Page]:
    pages = []

    for path in iter_input_files(indir):
        page = process_input_file(path, outdir, force_rebuild=rebuild_all)
        pages.append(page)
    
    return pages


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

    make_output_dir(outdir, clean)

    pages = process_input_dir(indir, outdir, rebuild_all=clean)

    home = build_home_page(pages)

    copy_resource_dirs(resource_dirs, outdir)

    dump_page_index()
