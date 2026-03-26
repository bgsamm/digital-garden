from pathlib import Path
import build
import logging

logger = logging.getLogger(__name__)


DEFAULT_INPUT_DIR = Path('pages')
DEFAULT_OUTPUT_DIR = Path('build')
DEFAULT_RESOURCE_DIRS = [Path('styles'), Path('scripts')]
DEFAULT_LOGFILE_PATH = Path('log.txt')


def parse_args():
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-i', '--input-dir',
        type=Path,
        default=DEFAULT_INPUT_DIR)
    
    parser.add_argument(
        '-o', '--output-dir',
        type=Path,
        default=DEFAULT_OUTPUT_DIR)
    
    parser.add_argument(
        '--resource-dirs',
        nargs='*',
        default=DEFAULT_RESOURCE_DIRS)
    
    parser.add_argument(
        '--clean',
        action='store_true')
    
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


def init_logging(console_level=logging.NOTSET, 
                 logfile_level=logging.NOTSET,
                 logfile_path=None):
    import sys, io
    
    def make_console_handler(formatter, log_level):
        utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        handler = logging.StreamHandler(utf8_stdout)
        handler.setFormatter(formatter)
        handler.setLevel(log_level)
        return handler
    
    def make_logfile_handler(formatter, log_level):
        handler = logging.FileHandler(logfile_path, encoding='utf-8', mode='w')
        handler.setFormatter(formatter)
        handler.setLevel(log_level)
        return handler

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.NOTSET)

    formatter = logging.Formatter('[%(module)s:%(levelname)s] %(message)s')

    if console_level != logging.NOTSET:
        root_logger.addHandler(make_console_handler(formatter, console_level))

    if logfile_level != logging.NOTSET and logfile_path is not None:
        root_logger.addHandler(make_logfile_handler(formatter, logfile_level))


def main(args):
    build.build(args.input_dir,
                args.output_dir,
                args.resource_dirs,
                args.clean)


if __name__ == '__main__':
    args = parse_args()

    init_logging(args.console_log_level,
                 args.logfile_log_level,
                 args.logfile_path)

    main(args)
