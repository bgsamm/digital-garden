import re
import os
import shutil
import jinja2
import pandoc
import enum
import pandoc.types as pdt

BUILD_DIR = 'build'
TEMPLATES_DIR = 'templates'
PAGES_DIR = 'pages'
STYLES_DIR = 'styles'

class OrgTree:
    def __init__(self, metadata, nodes):
        self.metadata = metadata
        self.nodes = nodes

class OrgNode:
    def __init__(self, type_):
        self.type_ = type_
        self.text = ''
        self.children = []

        self.id_ = None
        self.cls = []
        self.attrs = {}

class NodeType(enum.Enum):
    CODE = enum.auto()
    HEAD = enum.auto()
    ITEM = enum.auto()
    LINK = enum.auto()
    LIST = enum.auto()
    META = enum.auto()
    PARA = enum.auto()
    SPAN = enum.auto()
    TEXT = enum.auto()
    TODO = enum.auto()
    TOKN = enum.auto()


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

    return OrgTree(metadata, nodes)

def unwrap_blocks(blocks):
    return [unwrap_block(block) for block in blocks]

def unwrap_code(block):
    node = OrgNode(NodeType.CODE)
    node.text = block[1]
    node.inline = (type(block) is pdt.Code)
    node.id_, node.cls, node.attrs = block[0]

    return node

def unwrap_head_or_para(block):
    if type(block) is pdt.Header:
        node = OrgNode(NodeType.HEAD)
        node.level = block[0]
        node.id_, node.cls, node.attrs = block[1]
        i = 2
    else:
        node = OrgNode(NodeType.PARA)
        i = 0

    node.children = unwrap_blocks(block[i])

    is_todo = 'todo' in node.children[0].cls
    is_done = 'done' in node.children[0].cls
    if is_todo or is_done:
        node.type_ = NodeType.TODO
        node.done = is_done
        del node.children[0]

    return node

def unwrap_link_or_span(block):
    if type(block) is pdt.Link:
        node = OrgNode(NodeType.LINK)
        node.target = block[2][0]
        # Appears to be unused
        node.title = block[2][1]
    else:
        node = OrgNode(NodeType.SPAN)

    node.id_, node.cls, node.attrs = block[0]
    node.children = unwrap_blocks(block[1])

    return node

def unwrap_list(block):
    node = OrgNode(NodeType.LIST)

    node.ordered = (type(block) is pdt.OrderedList)

    if node.ordered:
        node.start = block[0][0]
        node.style = str(block[0][1])[:-2] # Strip trailing parens
        node.delim = str(block[0][2])[:-2] # ""
        i = 1
    else:
        i = 0

    for item in block[i]:
        item_node = OrgNode(NodeType.ITEM)
        item_node.children = unwrap_blocks(item)

    return node

def unwrap_rawblock(block):
    assert(block[0][0] == 'org')

    matches = regex_match(r'#\+(\w+):\s+(.+)', block[1])
    assert(matches is not None)

    node = OrgNode(NodeType.META)
    node.key = matches[0].lower()
    node.value = matches[1]

    return node

def unwrap_textblock(block):
    node = OrgNode(NodeType.TEXT)
    node.children = unwrap_blocks(block[0])

    node.strong = (type(block) is pdt.Strong)
    node.emph = (type(block) is pdt.Emph)

    return node

def unwrap_token(block):
    node = OrgNode(NodeType.TOKN)

    if type(block) is pdt.Str:
        node.text = block[0]
    else:
        node.text = ' '

    return node

pandoc_type_map = {
    pdt.Code: unwrap_code,
    pdt.CodeBlock: unwrap_code,
    pdt.Emph: unwrap_textblock,
    pdt.Header: unwrap_head_or_para,
    pdt.Link: unwrap_link_or_span,
    pdt.OrderedList: unwrap_list,
    pdt.Para: unwrap_head_or_para,
    pdt.Plain: unwrap_textblock,
    pdt.RawBlock: unwrap_rawblock,
    pdt.SoftBreak: unwrap_token,
    pdt.Space: unwrap_token,
    pdt.Span: unwrap_link_or_span,
    pdt.Str: unwrap_token,
    pdt.Strong: unwrap_textblock
}

def unwrap_block(block):
    pandoc_type = type(block)

    if pandoc_type not in pandoc_type_map:
        raise TypeError(f'Unhandled block type: {pandoc_type}')

    node = pandoc_type_map[pandoc_type](block)

    return node

def ast_to_html(ast):
    headings = []

    content = ''
    for node in ast.nodes:
        node_html = render_node(node)
        if node.type_ == NodeType.HEAD:
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

    html = '<div id="table-of-contents">' + toc + '</div>' + \
           '<div id="content">' + content + '</div>'

    return html

def render_nodes(nodes):
    html = ''
    for node in nodes:
        html += render_node(node)
    return html

def render_code(node):
    text = html_escape(node.text)

    html = f'<code>{text}</code>'
    if not node.inline:
        html = f'<figure><pre>{html}</pre></figure>'

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

def render_ignore(node):
    return ''

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
    NodeType.HEAD: render_heading,
    NodeType.ITEM: lambda node: render_default(node, 'li'),
    NodeType.LINK: render_link,
    NodeType.LIST: render_list,
    NodeType.META: render_ignore,
    NodeType.PARA: lambda node: render_default(node, 'p'),
    NodeType.SPAN: render_ignore,
    NodeType.TEXT: render_text,
    NodeType.TODO: render_ignore,
    NodeType.TOKN: render_token,
}

def render_node(node):
    if node.type_ not in html_render_map:
        raise TypeError(f'Unhandled node type: {node.type_}')

    html = html_render_map[node.type_](node)

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
    if fname[0] == '.' or ext != '.org':
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
