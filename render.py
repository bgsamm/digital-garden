import os
import jinja2
import pandoc

PAGES_DIR = 'pages'
BUILD_DIR = 'build'
TEMPLATES_DIR = 'templates'

def unwrap_metadata(metadata):
    # Unwrap 'Meta' object
    metadata = metadata[0]

    unwrapped = {}
    for k, v in metadata.items():
        # Unwrap 'MetaString' object
        unwrapped[k] = v[0]

    return unwrapped

def write_to_file(fpath, s):
    with open(fpath, 'w+') as f:
        f.write(s)

os.makedirs(BUILD_DIR, exist_ok=True)

file_system_loader = jinja2.FileSystemLoader(TEMPLATES_DIR)
jinja_env = jinja2.Environment(loader=file_system_loader)

home_template = jinja_env.get_template('index.html')
page_template = jinja_env.get_template('page.html')

pages = []
for dirpath, dirnames, filenames in os.walk(PAGES_DIR):
    for filename in filenames:
        fname, ext = os.path.splitext(filename)
        if ext != '.org':
            continue

        inpath = os.path.join(dirpath, filename)

        doc = pandoc.read(file=inpath)
        metadata = unwrap_metadata(doc[0])

        content = pandoc.write(doc, format='html')
        html = page_template.render(metadata, content=content)

        url = f'{fname}.html'
        outpath = os.path.join(BUILD_DIR, url)
        write_to_file(outpath, html)

        metadata['url'] = url
        pages.append(metadata)

html = home_template.render(title='Home', pages=pages)
outpath = os.path.join(BUILD_DIR, 'index.html')
write_to_file(outpath, html)
