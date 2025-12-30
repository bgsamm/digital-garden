import re
import os
import shutil
import jinja2
import pandoc

BUILD_DIR = 'build'
TEMPLATES_DIR = 'templates'
PAGES_DIR = 'pages'
STYLES_DIR = 'styles'

class AST:
    def __init__(self, metadata, nodes):
        self.metadata = metadata
        self.nodes = nodes

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

def path_join(*args):
    """Join several path elements together with the OS-appropriate
    path separator.
    """
    return os.path.join(*args)

def make_dir(path):
    """Create a directory (and all necessary parent directories) if it
    does not already exist.
    """
    os.makedirs(path, exist_ok=True)

def empty_dir(root):
    """Delete the contents of a directory.
    """
    for itemname in os.listdir(root):
        itempath = os.path.join(root, itemname)
        if os.path.isdir(itempath):
            shutil.rmtree(itempath)
        else:
            os.remove(itempath)
def copy_dir(indir, outdir):
    """Copy the contents of one directory to another.
    """
    shutil.copytree(indir, outdir, dirs_exist_ok=True)

def walk_dir(root):
    """Walk recursively through the files in a directory tree,
    yielding for each file its containing directory, name, and
    extension.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        for filename in filenames:
            fname, ext = os.path.splitext(filename)
            yield dirpath, fname, ext

def parse_org_file(fpath):
    ast = pandoc.read(file=fpath)

    # Unwrap 'Meta' object
    metadata = ast[0][0]
    for k, v in metadata.items():
        assert(type(v) is pandoc.types.MetaString)
        # Unwrap 'MetaString' object
        metadata[k] = v[0]

    nodes = unwrap_blocks(ast[1])

    return AST(metadata, nodes)

def unwrap_blocks(blocks):
    return [unwrap_block(block) for block in blocks]

def unwrap_block(block):
    pandoc_type = type(block)
    if pandoc_type is pandoc.types.RawBlock:
        assert(block[0][0] == 'org')
        matches = regex_match(r'#\+(\w+):\s+(.+)', block[1])
        assert(matches is not None)
        node_type = 'org-directive'
        node_attrs = {
            'type': matches[0].lower(),
            'value': matches[1]
        }
    elif pandoc_type is pandoc.types.Header:
        assert(block[1][1] == [] and block[1][2] == [])
        node_type = 'heading'
        node_attrs = {
            'level': block[0],
            'children': unwrap_blocks(block[2])
        }
    elif pandoc_type is pandoc.types.Para:
        node_type = 'paragraph'
        node_attrs = { 'children': unwrap_blocks(block[0]) }
    elif pandoc_type is pandoc.types.Plain:
        node_type = 'plain-text'
        node_attrs = { 'children': unwrap_blocks(block[0]) }
    elif pandoc_type is pandoc.types.Strong:
        node_type = 'strong-text'
        node_attrs = { 'children': unwrap_blocks(block[0]) }
    elif pandoc_type is pandoc.types.Emph:
        node_type = 'emphasized-text'
        node_attrs = { 'children': unwrap_blocks(block[0]) }
    elif pandoc_type is pandoc.types.OrderedList:
        node_type = 'ordered-list'
        node_attrs = {
            'start': block[0][0],
            'style': str(block[0][1])[:-2], # Strip trailing parens
            'delim': str(block[0][2])[:-2], # ""
            'children': [(
                'list-item',
                { 'children': unwrap_blocks(item) }
            ) for item in block[1]]
        }
    elif pandoc_type is pandoc.types.CodeBlock:
        assert(len(block[0][1]) == 1)
        node_type = 'code-block'
        node_attrs = {
            'name': block[0][0],
            'language': block[0][1][0],
            'text': block[1]
        }
    elif pandoc_type is pandoc.types.Code:
        assert(block[0][0] == '' and block[0][2] == [])
        assert(len(block[0][1]) == 1 and block[0][1][0] == 'verbatim')
        node_type = 'inline-code'
        node_attrs = {
            'text': block[1]
        }
    elif pandoc_type is pandoc.types.Link:
        assert(block[0] == ('', [], []))
        assert(block[2][1] == '')
        node_type = 'link'
        node_attrs = {
            'children': unwrap_blocks(block[1]),
            'target': block[2][0]
        }
    elif pandoc_type is pandoc.types.Span:
        node_type = 'span'
        node_attrs = {
            'is-todo': 'todo' in block[0][1] or 'done' in block[0][1],
            'children': unwrap_blocks(block[1])
        }
    elif pandoc_type is pandoc.types.Str:
        node_type = 'string'
        node_attrs = { 'text': block[0] }
    elif pandoc_type is pandoc.types.Space:
        node_type = 'space'
        node_attrs = {}
    elif pandoc_type is pandoc.types.SoftBreak:
        node_type = 'soft-break'
        node_attrs = {}
    else:
        raise TypeError(f'Unhandled block type: {pandoc_type}')

    if node_type == 'heading' or node_type == 'paragraph':
        children = node_attrs['children']
        assert(len(children) > 0)
        first_child_type, first_child_attrs = children[0]
        if first_child_type == 'span' and first_child_attrs['is-todo']:
            node_type = 'todo-item'
            children[0] = first_child_attrs['children'][0]

    return (node_type, node_attrs)

def ast_to_html(ast):
    headings = []

    content = ''
    for node in ast.nodes:
        node_html = ast_node_to_html(node)
        if node[0] == 'heading':
            headings.append((node[1]['level'], node_html[4:-5]))
        content += node_html

    toc = '<h1>Table of Contents</h1>'
    prev_level = 0
    for level, text in headings:
        if level > prev_level:
            toc += '<ul><li>' * (level - prev_level)
        else:
            if level < prev_level:
                toc += '</li></ul>' * (prev_level - level)
            toc += '</li><li>'
        toc += text
        prev_level = level
    toc += '</li></ul>' * prev_level

    html = '<div id="table-of-contents">' + toc + '</div>' + \
           '<div id="content">' + content + '</div>'

    return html

def ast_nodes_to_html(nodes):
    html = ''
    for node in nodes:
        html += ast_node_to_html(node)
    return html

def ast_node_to_html(node):
    html = ''

    node_type, node_attrs = node

    if node_type == 'org-directive':
        pass
    elif node_type == 'todo-item':
        pass
    elif node_type == 'heading':
        n = node_attrs['level']
        html += f'<h{n}>'
        html += ast_nodes_to_html(node_attrs['children'])
        html += f'</h{n}>'
    elif node_type == 'paragraph':
        html += '<p>'
        html += ast_nodes_to_html(node_attrs['children'])
        html += '</p>'
    elif node_type == 'plain-text':
        html += ast_nodes_to_html(node_attrs['children'])
    elif node_type == 'strong-text':
        html += '<strong>'
        html += ast_nodes_to_html(node_attrs['children'])
        html += '</strong>'
    elif node_type == 'emphasized-text':
        html += '<em>'
        html += ast_nodes_to_html(node_attrs['children'])
        html += '</em>'
    elif node_type == 'ordered-list':
        html += '<ol>'
        html += ast_nodes_to_html(node_attrs['children'])
        html += '</ol>'
    elif node_type == 'list-item':
        html += '<li>'
        html += ast_nodes_to_html(node_attrs['children'])
        html += '</li>'
    elif node_type == 'inline-code':
        html += '<code>'
        html += html_escape(node_attrs['text'])
        html += '</code>'
    elif node_type == 'code-block':
        name = node_attrs['name']
        html += '<figure>'
        if len(name) > 0:
            html += '<figcaption>'
            html += html_escape(name)
            html += '</figcaption>'
        html += '<pre><code>'
        html += html_escape(node_attrs['text'])
        html += '</code></pre></figure>'
    elif node_type == 'link':
        target = node_attrs['target']
        html += f'<a href="{target}">'
        html += ast_nodes_to_html(node_attrs['children'])
        html += '</a>'
    elif node_type == 'string':
        html += html_escape(node_attrs['text'])
    elif node_type == 'space':
        html += ' '
    elif node_type == 'soft-break':
        html += ' '
    else:
        print(node)
        raise TypeError(f'Unhandled node type: {node_type}')

    return html

def render_page(template, *args, **kwargs):
    jinja_template = jinja_env.get_template(template)
    return jinja_template.render(*args, **kwargs)

def write_to_file(fpath, string):
    with open(fpath, 'w+', encoding='utf-8') as f:
        f.write(string)


make_dir(BUILD_DIR)
empty_dir(BUILD_DIR)

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
    trim_blocks=True,
    lstrip_blocks=True
)

pages = []
for dirpath, fname, ext in walk_dir(PAGES_DIR):
    if ext != '.org':
        continue

    fpath = path_join(dirpath, fname + ext)
    ast = parse_org_file(fpath)

    page_content = ast_to_html(ast)

    page_html = render_page('page.html', ast.metadata, content=page_content)

    url = fname + '.html'
    outpath = path_join(BUILD_DIR, url)
    write_to_file(outpath, page_html)
    
    ast.metadata['url'] = url
    pages.append(ast.metadata)

homepage_html = render_page('index.html', title='Home', pages=pages)
outpath = path_join(BUILD_DIR, 'index.html')
write_to_file(outpath, homepage_html)

outdir = path_join(BUILD_DIR, STYLES_DIR)
copy_dir(STYLES_DIR, outdir)
