import jinja2
import pandoc
import enum
import pandoc.types as pdt
import re
import os
import shutil
import datetime

BUILD_DIR = 'build'
TEMPLATES_DIR = 'templates'
PAGES_DIR = 'pages'
STYLES_DIR = 'styles'
SCRIPTS_DIR = 'scripts'

class NodeType(enum.Enum):
    CODE = enum.auto()
    HEADING = enum.auto()
    LINK = enum.auto()
    LIST = enum.auto()
    LIST_ITEM = enum.auto()
    META = enum.auto()
    PARAGRAPH = enum.auto()
    TABLE = enum.auto()
    TABLE_ROW = enum.auto()
    TABLE_CELL = enum.auto()
    TAG = enum.auto()
    TASK = enum.auto()
    TEXT = enum.auto()
    TOKEN = enum.auto()

class DocTree:
    def __init__(self, metadata, nodes):
        self.metadata = metadata
        self.nodes = nodes

class DocNode:
    def __init__(self, type_):
        self.type = type_
        self.text = ''
        self.children = []

    def inner_text(self):
        if len(self.text) > 0:
            return self.text
        return ''.join([child.inner_text() for child in self.children])

class Page:
    def __init__(self, title, cdate, mdate, category, abstract):
        self.title = title
        self.cdate = cdate
        self.mdate = mdate
        self.category = category
        self.abstract = abstract

        self.views = []
        self.default_view = None

class PageView:
    def __init__(self, name, content):
        self.id = name.lower().replace(' ', '-')
        self.name = name
        self.content = content


def parse_org_file(contents):
    ast = pandoc.read(source=contents, format='org')

    # Unwrap 'Meta' object
    metadata = ast[0][0]
    for k, v in metadata.items():
        assert(type(v) is pandoc.types.MetaString)
        # Unwrap 'MetaString' object
        metadata[k] = v[0]
    
    mtime = get_file_mtime(fpath)
    mdate = timestamp_to_date(mtime)
    metadata['modified'] = mdate

    nodes = unwrap_blocks(ast[1])

    return DocTree(metadata, nodes)

def unwrap_blocks(blocks):
    return [unwrap_block(block) for block in blocks]

def unwrap_code(block):
    node = DocNode(NodeType.CODE)
    node.text = block[1]
    node.inline = (type(block) is pdt.Code)

    return node

def unwrap_head_or_para(block):
    if type(block) is pdt.Header:
        node = DocNode(NodeType.HEADING)
        node.level = block[0]
        i = 2
    else:
        node = DocNode(NodeType.PARAGRAPH)
        i = 0

    node.children = unwrap_blocks(block[i])

    if node.children[0].type == NodeType.TAG:
        is_todo = (node.children[0].text == 'todo')
        is_done = (node.children[0].text == 'done')
        assert(is_todo or is_done)
        node.type = NodeType.TASK
        node.done = is_done
        # Skip TODO keyword and first space
        node.children = node.children[2:]

    first_tag_idx = -1
    for i, child in enumerate(node.children):
        if child.type == NodeType.TAG:
            first_tag_idx = i
            break

    if first_tag_idx >= 0:
        node.tags = [tag.text for tag in node.children[first_tag_idx:]
                     if tag.type == NodeType.TAG]
        node.children = node.children[:first_tag_idx]
    else:
        node.tags = []

    return node

def unwrap_link(block):
    node = DocNode(NodeType.LINK)
    node.target = block[2][0]
    # Appears to be unused
    node.title = block[2][1]

    node.children = unwrap_blocks(block[1])

    return node

def unwrap_list(block):
    node = DocNode(NodeType.LIST)

    node.ordered = (type(block) is pdt.OrderedList)

    if node.ordered:
        node.start = block[0][0]
        node.style = str(block[0][1])[:-2] # Strip trailing parens
        node.delim = str(block[0][2])[:-2] # ""
        i = 1
    else:
        i = 0

    for item in block[i]:
        item_node = DocNode(NodeType.LIST_ITEM)
        item_node.children = unwrap_blocks(item)
        node.children.append(item_node)

    return node

def unwrap_rawblock(block):
    assert(block[0][0] == 'org')

    matches = regex_match(r'#\+(\w+):\s+(.+)', block[1])
    assert(matches is not None)

    node = DocNode(NodeType.META)
    node.key = matches[0].lower()
    node.value = matches[1]

    return node

def unwrap_span(block):
    node = DocNode(NodeType.TAG)

    if 'tag' in block[0][1]:
        key, tag = block[0][2][0]
        assert(key == 'tag-name')
    else:
        tag = block[0][1][0]
        assert(tag == 'todo' or tag == 'done')
    node.text = tag

    return node

def unwrap_table(block):
    def unwrap_cell(cell, is_header=False):
        node = DocNode(NodeType.TABLE_CELL)
        node.is_header = is_header
        assert(cell[2][0] == 1)
        assert(cell[3][0] == 1)
        assert(len(cell[4]) <= 1)
        node.children = unwrap_blocks(cell[4])
        return node

    def unwrap_row(row, is_header=False):
        node = DocNode(NodeType.TABLE_ROW)
        node.children = [unwrap_cell(cell, is_header) for cell in row[1]]
        return node

    node = DocNode(NodeType.TABLE)

    table_head = block[3]
    if len(table_head[1]) != 0:
        assert(len(table_head[1]) == 1)
        node.children.append(unwrap_row(table_head[1][0], is_header=True))

    assert(len(block[4]) == 1)
    table_body = block[4][0]
    assert(table_body[1][0] == 0)
    assert(len(table_body[2]) == 0)

    node.children += [unwrap_row(row) for row in table_body[3]]

    return node

def unwrap_textblock(block):
    node = DocNode(NodeType.TEXT)
    node.children = unwrap_blocks(block[0])

    node.strong = (type(block) is pdt.Strong)
    node.emph = (type(block) is pdt.Emph)

    return node

def unwrap_token(block):
    node = DocNode(NodeType.TOKEN)

    if type(block) is pdt.Str:
        node.text = block[0]
    else:
        node.text = ' '

    return node

pandoc_type_map = {
    pdt.BulletList: unwrap_list,
    pdt.Code: unwrap_code,
    pdt.CodeBlock: unwrap_code,
    pdt.Emph: unwrap_textblock,
    pdt.Header: unwrap_head_or_para,
    pdt.Link: unwrap_link,
    pdt.OrderedList: unwrap_list,
    pdt.Para: unwrap_head_or_para,
    pdt.Plain: unwrap_textblock,
    pdt.RawBlock: unwrap_rawblock,
    pdt.SoftBreak: unwrap_token,
    pdt.Space: unwrap_token,
    pdt.Span: unwrap_span,
    pdt.Str: unwrap_token,
    pdt.Strong: unwrap_textblock,
    pdt.Table: unwrap_table,
}

def unwrap_block(block):
    pandoc_type = type(block)

    if pandoc_type not in pandoc_type_map:
        raise TypeError(f'Unhandled block type: {pandoc_type}')

    node = pandoc_type_map[pandoc_type](block)

    return node

def generate_page(ast):
    title = ast.metadata['title']
    cdate = ast.metadata['date']
    mdate = ast.metadata['modified']
    category = ast.metadata['category']
    abstract = ast.metadata['abstract']
    page = Page(title, cdate, mdate, category, abstract)

    main_view = generate_main_view(ast)
    page.views.append(main_view)

    task_view = generate_task_view(ast)
    page.views.append(task_view)

    page.default_view = main_view

    return page

def generate_main_view(ast):
    headings = []
    content = ''
    for node in ast.nodes:
        node_html = render_node(node)
        if node.type == NodeType.HEADING:
            headings.append((node.level, node_html[4:-5]))
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

    html = '<div class="table-of-contents">' + toc + '</div>' + \
           '<div class="content">' + content + '</div>'

    return PageView('Main', html)

def render_nodes(nodes):
    html = ''
    for node in nodes:
        html += render_node(node)
    return html

def render_code(node):
    text = html_escape(node.text).strip()

    if node.inline:
        html = f'<code class="code-inline">{text}</code>'
    else:
        html = '<figure class="code-block">'
        html += '<pre><code class="language-python">'
        html += text
        html += '</code></pre></figure>'

    return html

def render_default(node, tag, **kwargs):
    body = render_nodes(node.children)
    attrs = ''.join([f' {k}="{v}"' for k,v in kwargs.items()])
    return f'<{tag}{attrs}>{body}</{tag}>'

def render_heading(node):
    tag = f'h{node.level}'
    return render_default(node, tag)

def render_link(node):
    return render_default(node, 'a', href=node.target)

def render_list(node):
    tag = 'ol' if node.ordered else 'ul'
    return render_default(node, tag)

def render_table_cell(node):
    tag = 'th' if node.is_header else 'td'
    return render_default(node, tag)

def render_text(node):
    if node.strong:
        return render_default(node, 'strong')
    if node.emph:
        return render_default(node, 'em')
    return render_nodes(node.children)

def render_token(node):
    return html_escape(node.text)

html_render_map = {
    NodeType.CODE: render_code,
    NodeType.HEADING: render_heading,
    NodeType.LINK: render_link,
    NodeType.LIST: render_list,
    NodeType.LIST_ITEM: lambda node: render_default(node, 'li'),
    NodeType.META: None,
    NodeType.PARAGRAPH: lambda node: render_default(node, 'p'),
    NodeType.TABLE: lambda node: render_default(node, 'table'),
    NodeType.TABLE_ROW: lambda node: render_default(node, 'tr'),
    NodeType.TABLE_CELL: render_table_cell,
    NodeType.TAG: None,
    NodeType.TASK: None,
    NodeType.TEXT: render_text,
    NodeType.TOKEN: render_token,
}

def render_node(node):
    if node.type not in html_render_map:
        raise TypeError(f'Unhandled node type: {node.type}')

    renderer = html_render_map[node.type]
    if renderer is None:
        return ''

    html = renderer(node)
    return html

def generate_task_view(ast):
    html = '<div class="task-list">'

    stack = []
    for node in ast.nodes:
        if node.type == NodeType.HEADING:
            while len(stack) > 0 and node.level <= stack[-1].level:
                stack.pop()
            stack.append(node)

        if node.type != NodeType.TASK:
            continue

        state = 'done' if node.done else 'todo'
        if len(stack) == 0:
            section = '—'
        else:
            section = ' > '.join([heading.inner_text() for heading in stack])

        html += f'<div class="task {state}">'
        html += f'<div class="task-header">'
        html += f'<div class="task-state">{state.upper()}</div>'
        html += f'<div class="task-tags">'
        for tag in node.tags:
            if tag in ['easy', 'med', 'hard']:
                label = 'Diff'
            elif tag in ['low', 'mid', 'high']:
                label = 'Prio'
            else:
                continue
            html += f'<span class="task-tag {tag}">{label}: {tag.capitalize()}</span>'
        html += '</div>'
        html += '</div>'
        html += f'<div class="task-section">{section}</div>'
        html += f'<div class="task-desc">{node.inner_text()}</div>'
        html += '</div>'

    html += '</div>'

    return PageView('Tasks', html)

def render_page(template, *args, **kwargs):
    jinja_template = jinja_env.get_template(template)
    return jinja_template.render(*args, **kwargs)

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

def read_file(path):
    """Return the contents of a UTF-8 file as a string.
    """
    with open(fpath, 'r', encoding='utf-8') as f:
        contents = f.read()
    return contents

def write_file(fpath, string):
    """Write a string to a file with UTF-8 encoding.
    """
    with open(fpath, 'w+', encoding='utf-8') as f:
        f.write(string)

def get_file_mtime(path):
    """Get the Unix timestamp for the last modification time of a file
    as recorded by the file system
    """
    return os.path.getmtime(path)

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

def timestamp_to_date(timestamp):
    datetime_obj = datetime.datetime.fromtimestamp(timestamp, datetime.UTC)
    return datetime_obj.strftime('%Y-%m-%d')

def debug_print_ast(ast):
    print(f'Metadata: {ast.metadata}')
    print('Nodes:')
    for node in ast.nodes:
        debug_print_node(node, indent=1)

def debug_print_node(node, indent=0):
    tab = ' ' * 2
    ind = tab * indent

    print(f'{ind}Type: {node.type}', end=' ')
    if len(node.text) > 0:
        print(f'("{node.text}")', end='')
    print()

    ind += tab

    n_children = len(node.children)
    if n_children > 0:
        print(f'{ind}Children: {n_children}')
        for child in node.children:
            debug_print_node(child, indent=indent + 2)


make_dir(BUILD_DIR)
empty_dir(BUILD_DIR)

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
    trim_blocks=True,
    lstrip_blocks=True
)

pages = []
for dirpath, fname, ext in walk_dir(PAGES_DIR):
    if fname[0] == '.' or ext != '.org':
        continue

    fpath = path_join(dirpath, fname + ext)
    contents = read_file(fpath)
    
    ast = parse_org_file(contents)
    
    page = generate_page(ast)
    
    page_html = render_page('page.html', title=page.title, page=page)
    
    page.url = fname + '.html'
    outpath = path_join(BUILD_DIR, page.url)
    write_file(outpath, page_html)

    pages.append(page)

homepage_html = render_page('index.html', title='Home', pages=pages)
outpath = path_join(BUILD_DIR, 'index.html')
write_file(outpath, homepage_html)

outdir = path_join(BUILD_DIR, STYLES_DIR)
copy_dir(STYLES_DIR, outdir)

outdir = path_join(BUILD_DIR, SCRIPTS_DIR)
copy_dir(SCRIPTS_DIR, outdir)
