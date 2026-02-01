import jinja2
import enum
import util

BUILD_DIR = 'build'
TEMPLATES_DIR = 'templates'
PAGES_DIR = 'pages'
STYLES_DIR = 'styles'
SCRIPTS_DIR = 'scripts'

class DocTree:
    def __init__(self, metadata, nodes):
        self.metadata = metadata
        self.nodes = nodes

class DocNode:
    def __init__(self, type_):
        self.type = type_
        self.rawtext = None
        self.children = []

    def inner_text(self):
        if self.rawtext is not None:
            return self.rawtext
        return ''.join([child.inner_text() for child in self.children])

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

class Pandoc:
    """Helper functions to navigate Pandoc's JSON format."""

    @staticmethod
    def get_type(block):
        """Returns the type string of a Pandoc block."""
        return block.get('t')
    
    @staticmethod
    def get_content(block):
        """Returns the content field of a Pandoc block."""
        return block.get('c')
    
    @staticmethod
    def unwrap_attr(attr):
        """Unpacks a Pandoc Attr tuple: (identifier, classes, key-value pairs)."""
        # Pandoc Schema: [id, [class1, class2], [[key, val], ...]]
        return {
            'id': attr[0],
            'cls': attr[1],
            'kvs': dict(attr[2])
        }
    
    @staticmethod
    def unwrap_block(block):
        t = Pandoc.get_type(block)
        c = Pandoc.get_content(block)
    
        if t not in Pandoc.unwrapper_map:
            raise TypeError(f'Unhandled block type: {t}')
    
        node = Pandoc.unwrapper_map[t](t, c)
    
        return node
    
    @staticmethod
    def unwrap_blocks(blocks):
        return [Pandoc.unwrap_block(block) for block in blocks]
    
    def unwrap_code(type_, content):
        node = DocNode(NodeType.CODE)
    
        attr, text = content
        attr = Pandoc.unwrap_attr(attr)
    
        node.rawtext = text
        node.name = attr['id']
        node.inline = (type_ == 'Code')
    
        classes = attr['cls']
        if len(classes) > 0:
            assert(len(classes) == 1)
            node.language = classes[0]
    
        return node
    
    @staticmethod
    def unwrap_header_or_para(type_, content):
        def convert_to_task(node):
            is_todo = (node.children[0].rawtext == 'todo')
            is_done = (node.children[0].rawtext == 'done')
            assert(is_todo or is_done)
            node.type = NodeType.TASK
            node.done = is_done
            # Strip task keyword and first space
            node.children = node.children[2:]
    
        def apply_tags(node):
            # Tags occur at the end of a line, separated by non-breaking spaces
            first_tag_idx = -1
            for i, child in enumerate(node.children):
                if child.type == NodeType.TAG:
                    first_tag_idx = i
                    break
            if first_tag_idx >= 0:
                node.tags = [node.rawtext for node in node.children[first_tag_idx:]
                             if node.type == NodeType.TAG]
                node.children = node.children[:first_tag_idx]
            else:
                node.tags = []
    
        if type_ == 'Header':
            node = DocNode(NodeType.HEADING)
    
            level, attr, inlines = content
            attr = Pandoc.unwrap_attr(attr)
    
            node.level = level
        else:
            assert(type_ == 'Para')
            node = DocNode(NodeType.PARAGRAPH)
            inlines = content
    
        node.children = Pandoc.unwrap_blocks(inlines)
    
        if node.children[0].type == NodeType.TAG:
            convert_to_task(node)
    
        # Must be done after task conversion, since tasks are tags
        apply_tags(node)
    
        return node
    
    @staticmethod
    def unwrap_link(type_, content):
        node = DocNode(NodeType.LINK)
    
        attr, inlines, target = content
        attr = Pandoc.unwrap_attr(attr)
    
        target, title = target
        node.title = title
        node.target = target
    
        i = target.find(':')
        if i >= 0 and i < len(target) - 1 and target[i + 1] != ':':
            scheme = target[:i]
            if scheme == 'http' or scheme == 'https':
                node.external = True
            elif scheme == 'file':
                node.external = False
            else:
                raise ValueError(f'Unhandled link scheme: {scheme}')
        else:
            node.external = False
    
        node.children = Pandoc.unwrap_blocks(inlines)
    
        return node
    
    @staticmethod
    def unwrap_list(type_, content):
        node = DocNode(NodeType.LIST)
    
        node.ordered = (type_ == 'OrderedList')
    
        if node.ordered:
            listattrs, items = content
            start, style, delim = listattrs
            node.start = start
            node.style = Pandoc.get_type(style)
            node.delim = Pandoc.get_type(delim)
        else:
            items = content
    
        for block in items:
            item = DocNode(NodeType.LIST_ITEM)
            item.children = Pandoc.unwrap_blocks(block)
            node.children.append(item)
    
        return node
    
    @staticmethod
    def unwrap_meta(type_, content):
        node = DocNode(NodeType.META)
        node.rawtext = content
        return node
    
    @staticmethod
    def unwrap_rawblock(type_, content):
        fmt, text = content
        assert(fmt == 'org')
    
        matches = util.regex_match(r'#\+(\w+):\s+(.+)', text)
        assert(matches is not None)
    
        node = DocNode(NodeType.META)
        node.key = matches[0].lower()
        node.value = matches[1]
    
        return node
    
    @staticmethod
    def unwrap_span(type_, content):
        attr, inlines = content
        attr = Pandoc.unwrap_attr(attr)
    
        if 'spurious-link' in attr['cls']:
            node = DocNode(NodeType.LINK)
    
            node.target = attr['kvs']['target']
            node.external = False
    
            # Spurious links get wrapped in an 'Emph' block
            assert(len(inlines) == 1)
            node.children = Pandoc.unwrap_blocks(inlines)[0].children
        else:
            node = DocNode(NodeType.TAG)
    
            if 'tag' in attr['cls']:
                tag = attr['kvs']['tag-name']
            else:
                tag = attr['cls'][0]
    
            node.rawtext = tag
    
        return node
    
    @staticmethod
    def unwrap_table(type_, content):
        def unwrap_cell(cell, is_header=False):
            attr, align, rowspan, colspan, children = cell
            attr = Pandoc.unwrap_attr(attr)
    
            node = DocNode(NodeType.TABLE_CELL)
            node.is_header = is_header
            node.rowspan = rowspan
            node.colspan = colspan
            node.children = Pandoc.unwrap_blocks(children)
    
            return node
    
        def unwrap_row(row, is_header=False):
            attr, cells = row
            attr = Pandoc.unwrap_attr(attr)
    
            node = DocNode(NodeType.TABLE_ROW)
            node.children = [unwrap_cell(cell, is_header) for cell in cells]
    
            return node
    
        def unwrap_head(head):
            attr, rows = head
            attr = Pandoc.unwrap_attr(attr)
    
            assert(len(rows) <= 1)
    
            if len(rows) == 0:
                return None
            return unwrap_row(rows[0], is_header=True)
    
        def unwrap_body(body):
            assert(len(body) == 1)
    
            attr, rowheadcols, head, rows = body[0]
            attr = Pandoc.unwrap_attr(attr)
    
            assert(len(head) == 0)
    
            return [unwrap_row(row) for row in rows]
    
        node = DocNode(NodeType.TABLE)
    
        attr, caption, colspecs, tablehead, tablebody, tablefoot = content
        attr = Pandoc.unwrap_attr(attr)
    
        header = unwrap_head(tablehead)
        if header is not None:
            node.children.append(header)
    
        node.children += unwrap_body(tablebody)
    
        return node
    
    def unwrap_textblock(type_, content):
        node = DocNode(NodeType.TEXT)
        node.children = Pandoc.unwrap_blocks(content)
    
        node.strong = (type_ == 'Strong')
        node.emph = (type_ == 'Emph')
    
        return node
    
    @staticmethod
    def unwrap_token(type_, content):
        node = DocNode(NodeType.TOKEN)
    
        if content is not None:
            node.rawtext = content
        else:
            node.rawtext = ' '
    
        return node
    
    unwrapper_map = {
        'Code': unwrap_code,
        'CodeBlock': unwrap_code,
        'BulletList': unwrap_list,
        'Emph': unwrap_textblock,
        'Header': unwrap_header_or_para,
        'Link': unwrap_link,
        'MetaString': unwrap_meta,
        'OrderedList': unwrap_list,
        'Para': unwrap_header_or_para,
        'Plain': unwrap_textblock,
        'RawBlock': unwrap_rawblock,
        'SoftBreak': unwrap_token,
        'Space': unwrap_token,
        'Span': unwrap_span,
        'Str': unwrap_token,
        'Strong': unwrap_textblock,
        'Table': unwrap_table,
    }

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
    def __init__(self, name):
        self.id = util.html_slugify(name)
        self.name = name


def parse_org_file(fpath):
    args = ['-f', 'org', '-t', 'json', fpath]
    json = util.process_run('pandoc', args)
    ast = util.json_parse(json)

    metadata = {}
    for key, block in ast['meta'].items():
        metadata[key] = Pandoc.unwrap_block(block).inner_text()
    
    mtime = util.file_get_mtime(fpath)
    mdate = util.datetime_timestamp_to_date(mtime)
    metadata['modified'] = mdate

    nodes = Pandoc.unwrap_blocks(ast['blocks'])

    return DocTree(metadata, nodes)

def generate_page(ast, page_url):
    title = ast.metadata['title']
    cdate = ast.metadata['date']
    mdate = ast.metadata['modified']
    category = ast.metadata['category']
    abstract = ast.metadata['abstract']
    page = Page(title, cdate, mdate, category, abstract)

    main_view = generate_doc_view(ast)
    main_view.url = util.path_join(page_url, 'doc')
    page.views.append(main_view)

    task_view = generate_task_view(ast)
    task_view.url = util.path_join(page_url, 'tasks')
    page.views.append(task_view)

    page.default_view = main_view

    return page

def generate_doc_view(ast):
    view = PageView('Doc')

    headings = []
    view.content = ''
    for node in ast.nodes:
        node_html = render_node(node)
        if node.type == NodeType.HEADING:
            headings.append(node)
        view.content += node_html

    view.toc = '<h1>Table of Contents</h1>'
    prev_level = 0
    for node in headings:
        if node.level > prev_level:
            view.toc += '<ul><li>' * (node.level - prev_level)
        else:
            if node.level < prev_level:
                view.toc += '</li></ul>' * (prev_level - node.level)
            view.toc += '</li><li>'
        text = node.inner_text()
        id_ = util.html_slugify(text)
        view.toc += f'<a href="#{id_}">{text}</a>'
        prev_level = node.level
    view.toc += '</li></ul>' * prev_level

    return view

def render_nodes(nodes):
    html = ''
    for node in nodes:
        html += render_node(node)
    return html

def render_code(node):
    text = util.html_escape(node.rawtext).strip()

    if node.inline:
        html = f'<code class="code-inline">{text}</code>'
    else:
        html = '<figure class="code-block">'
        if len(node.name) > 0:
            html += f'<figcaption>{node.name}</figcaption>'
        html += f'<pre><code class="language-{node.language}">'
        html += text
        html += '</code></pre></figure>'

    return html

def render_default(node, tag, **kwargs):
    body = render_nodes(node.children)
    attrs = ''.join([f' {k}="{v}"' for k,v in kwargs.items()])
    return f'<{tag}{attrs}>{body}</{tag}>'

def render_heading(node):
    id_ = util.html_slugify(node.inner_text())
    tag = f'h{node.level}'
    return render_default(node, tag, id=id_)

def render_link(node):
    target = node.target
    if not node.external:
        i = target.find('::')
        if i >= 0:
            fname = target[:i]
            frag = target[i + 2:]
        elif target[0] == '*' or target[0] == '#':
            fname = ''
            frag = target
        else:
            fname = target
            frag = ''
        fname = fname.replace('.org', '.html')
        frag = '#' + util.html_slugify(frag[1:])
        target = fname + frag
    return render_default(node, 'a', href=target)

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
    return util.html_escape(node.rawtext)

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
    view = PageView('Tasks')
    view.tasks = []

    stack = []
    for node in ast.nodes:
        if node.type == NodeType.HEADING:
            while len(stack) > 0 and node.level <= stack[-1].level:
                stack.pop()
            stack.append(node)

        if node.type != NodeType.TASK:
            continue

        task = DocNode(NodeType.TASK)
        task.state = 'done' if node.done else 'todo'

        if len(stack) == 0:
            task.section = '—'
        else:
            task.section = ' > '.join([heading.inner_text() for heading in stack])

        task.description = node.inner_text().strip()

        task.labels = []
        task.tags = []
        for tag in node.tags:
            if tag in ['easy', 'med', 'hard']:
                label = 'Diff'
            elif tag in ['low', 'mid', 'high']:
                label = 'Prio'
            else:
                continue

            if label in task.labels:
                title = ast.metadata['title']
                desc = task.description
                raise ValueError(f'Multiple {label} tags for task "{desc}" in page "{title}".')

            task.labels.append(label)
            task.tags.append(tag)

        view.tasks.append(task)

    return view

def render_page(template, *args, **kwargs):
    jinja_template = jinja_env.get_template(template)
    return jinja_template.render(*args, **kwargs)

def render_page_view(page, view):
    jinja_template = jinja_env.get_template(f'view_{view.id}.html')
    return jinja_template.render(page=page, view=view)


util.dir_make(BUILD_DIR)
util.dir_empty(BUILD_DIR)

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
    trim_blocks=True,
    lstrip_blocks=True
)

pages = []
for dirpath, fname, ext in util.dir_walk(PAGES_DIR):
    if fname[0] == '.' or fname[0] == '#' or ext != '.org':
        continue

    fpath = util.path_join(dirpath, fname + ext)
    ast = parse_org_file(fpath)
    
    page_url = util.path_join(PAGES_DIR, fname)
    page = generate_page(ast, page_url)
    
    for view in page.views:
        view_html = render_page_view(page, view)
        outpath = util.path_join(BUILD_DIR, view.url, 'index.html')
        util.file_write(outpath, view_html)

    pages.append(page)

homepage_html = render_page('index.html', title='Home', pages=pages)
outpath = util.path_join(BUILD_DIR, 'index.html')
util.file_write(outpath, homepage_html)

outdir = util.path_join(BUILD_DIR, STYLES_DIR)
util.dir_copy(STYLES_DIR, outdir)

outdir = util.path_join(BUILD_DIR, SCRIPTS_DIR)
util.dir_copy(SCRIPTS_DIR, outdir)
