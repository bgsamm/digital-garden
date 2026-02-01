import re
import json
import os
import shutil
import subprocess
import datetime

def regex_match(pattern, string):
    """Return the list of match groups for a given regex pattern
    and input string, or None if the string was not a match
    """
    match_obj = re.match(pattern, string)
    if match_obj is not None:
        return match_obj.groups()
    return None


def html_escape(string):
    """Replace the '&', '<', and '>' characters in a string with their
    corresponding HTML escape sequences.
    """
    return string.replace('&', '&amp;') \
                 .replace('<', '&lt;') \
                 .replace('>', '&gt;')

def html_slugify(string):
    """Convert an arbitrary string to a valid CSS identifier
    by replacing non-alphanumeric characters with hyphens.
    """
    slug = ''
    for c in string:
        slug += c.lower() if c.isalnum() else '-'
    return slug

def html_strip_tag(string):
    """Remove the outermost HTML tag from a string.
    """
    start = min(0, string.find('>'))
    end = string.rfind('<')
    if end < 0:
        end = len(string)
    return string[start:end]


def json_parse(s):
    """Parses a JSON string into a corresponding Python object
    (e.g. dict, list, etc.).
    """
    return json.loads(s)


def path_join(*args):
    """Join several path elements together with the OS-appropriate
    path separator.
    """
    return os.path.join(*args)


def file_read(fpath):
    """Return the contents of a UTF-8 file as a string.
    """
    with open(fpath, 'r', encoding='utf-8') as f:
        contents = f.read()
    return contents

def file_write(fpath, string):
    """Write a string to a file with UTF-8 encoding.
    """
    dirpath = os.path.split(fpath)[0]
    os.makedirs(dirpath, exist_ok=True)
    with open(fpath, 'w+', encoding='utf-8') as f:
        f.write(string)

def file_get_mtime(path):
    """Get the Unix timestamp for the last modification time of a file
    as recorded by the file system
    """
    return os.path.getmtime(path)


def dir_make(path):
    """Create a directory (and all necessary parent directories) if it
    does not already exist.
    """
    os.makedirs(path, exist_ok=True)

def dir_empty(root):
    """Delete the contents of a directory.
    """
    for itemname in os.listdir(root):
        itempath = os.path.join(root, itemname)
        if os.path.isdir(itempath):
            shutil.rmtree(itempath)
        else:
            os.remove(itempath)
def dir_copy(indir, outdir):
    """Copy the contents of one directory to another.
    """
    shutil.copytree(indir, outdir, dirs_exist_ok=True)

def dir_walk(root):
    """Walk recursively through the files in a directory tree,
    yielding for each file its containing directory, name, and
    extension.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        for filename in filenames:
            fname, ext = os.path.splitext(filename)
            yield dirpath, fname, ext


def process_run(name, args, input_str=None):
      """Run an external process with the given arguments and input string.
      Returns the process's standard output as a string.
      """
      process = subprocess.run(
          [name] + args,
          input=input_str,
          capture_output=True,
          check=True,
          encoding='utf-8'
      )
      return process.stdout


def datetime_timestamp_to_date(timestamp):
    """Convert a Unix timestamp to a string of the form YYYY-MM-DD"""
    datetime_obj = datetime.datetime.fromtimestamp(timestamp, datetime.UTC)
    return datetime_obj.strftime('%Y-%m-%d')
