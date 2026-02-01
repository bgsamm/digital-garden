import jinja2
import parse
from parse import NodeType, DocNode
import util

BUILD_DIR = 'build'
TEMPLATES_DIR = 'templates'
PAGES_DIR = 'pages'
STYLES_DIR = 'styles'
SCRIPTS_DIR = 'scripts'

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
    ast = parse.parse_org_file(fpath)
    
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
