from parse import DocTree, DocNode, NodeType
from pathlib import Path
from typing import Iterator
import jinja2
import logging

logger = logging.getLogger(__name__)


TEMPLATES_DIR = Path('templates')


class View:
    name = ''
    template = ''

    def __init__(self, page: Page):
        self.page = page
    
    def render(self, *args) -> str:
        return ''
    
    def apply_template(self, **kwargs):
        return apply_jinja_template(self.template, page=self.page, view=self, **kwargs)
    
    @property
    def title(self):
        return self.name.capitalize()
    
    @property
    def url(self):
        return self.page.base_url / self.name


class DocView(View):
    name = 'doc'
    template = 'view_doc.html'
    
    def render(self, ast: DocTree) -> str:
        return self.apply_template(
            content=self.render_content(ast),
            toc=self.render_toc(ast)
        )
    
    def render_content(self, ast: DocTree) -> str:
        return render_node(ast.root)
    
    def render_toc(self, ast: DocTree) -> str:
        def render_toc_item(node: DocNode) -> str:
            target = f'#{node.attrs['id']}'

            content = make_html_tag('a', node.rawtext, href=target)
            content += make_child_list(node)
            
            return make_html_tag('li', content)
        
        def make_child_list(node: DocNode) -> str:
            items = [render_toc_item(child) for child in node.children
                    if child.type == NodeType.SECTION]

            if items:
                return make_html_tag('ul', ''.join(items))
            
            return ''
        
        return make_child_list(ast.root)


class DexView(View):
    name = 'dex'
    template = 'view_dex.html'
    
    def render(self, *args) -> str:
        return ''


class LogView(View):
    name = 'log'
    template = 'view_log.html'
    
    def render(self, ast: DocTree) -> str:
        return ''


class TaskView(View):
    name = 'tasks'
    template = 'view_task.html'
    
    def render(self, ast: DocTree) -> str:
        return self.apply_template(tasks=self.get_tasks(ast))
    
    def get_tasks(self, ast: DocTree) -> list:
        return [self.make_task_from_node(node) for node in ast.walk(NodeType.TASK)]
    
    def make_task_from_node(self, node: DocNode) -> dict:
        task = {}

        task['state'] = node.attrs['state']
        task['description'] = node.inner_text()

        if node.parent.type == NodeType.ROOT:
            section = '-'
        else:
            sections = [parent.rawtext for parent in node.iter_parents()
                        if parent.type == NodeType.SECTION]
            section = ' > '.join(sections)
        task['section'] = section

        task['diff'] = node.attrs.get('diff')
        task['prio'] = node.attrs.get('prio')

        return task


class Page:
    view_lookup = {
        'doc': [DocView, TaskView],
        'dex': [DexView, LogView, TaskView],
    }

    def __init__(self, name: str, metadata: dict):
        self.name = name
        self.type = metadata.get('type', 'doc')
        self.metadata = metadata

        views = self.view_lookup.get(self.type, [])
        if len(views) == 0:
            logger.error(f'Unknown view type "{self.type}"')
        self.views: list[View] = [cls(self) for cls in views]
    
    def iter_views(self) -> Iterator[View]:
        yield from self.views
    
    @property
    def title(self):
        return self.metadata.get('title')
    
    @property
    def base_url(self):
        return Path('pages') / self.name
    
    @property
    def default_url(self):
        if len(self.views) == 0:
            return self.base_url
        return self.views[0].url


def slugify(s: str) -> str:
    """Convert an arbitrary string to a valid CSS identifier
    by replacing non-alphanumeric characters with hyphens.
    """
    import re
    # Suggested by Gemini
    return re.sub(r'[^a-zA-Z0-9]', '-', s).lower()


def escape(s: str) -> str:
    """Replace problematic characters in a string with their
    corresponding HTML escape sequences.
    """
    import html
    return html.escape(s)


def timestamp_to_date(timestamp: float) -> str:
    """Convert a Unix timestamp to a date string in the format YYY-MM-DD.
    """
    import datetime as dt
    return dt.datetime.fromtimestamp(timestamp, dt.UTC).strftime('%Y-%m-%d')


# Modified from version by Gemini
def make_html_tag(
        tag: str,
        content: str,
        id: str | None = None,
        classes: list[str] | None = None,
        **attrs: str
    ) -> str:
    """Create an HTML tag with optional id, class list, and attributes.
    """
    parts = [tag]

    if id:
        parts.append(f'id="{slugify(id)}"')
    
    if classes:
        parts.append(f'class="{" ".join(classes)}"')
    
    if attrs:
        parts += [f'{k}="{escape(v)}"' for k, v in attrs.items()]

    return f'<{" ".join(parts)}>{content}</{tag}>'


def render_node(node: DocNode) -> str:
    renderer = default_render_map.get(node.type)

    if renderer is None:
        logger.error(f'Unhandled node type: {node.type}')
        return ''

    return renderer(node)


def render_node_content(node: DocNode) -> str:
    return ''.join(render_node(n) for n in node.inlines + node.children)


def render_basic(node: DocNode, tag: str) -> str:
    return make_html_tag(tag, render_node_content(node))


def render_code(node: DocNode) -> str:
    text = escape(node.rawtext.strip())

    if node.attrs['inline']:
        html = make_html_tag('code', text, classes=['code-inline'])
    else:
        name = node.attrs['name']
        lang = node.attrs['language']

        caption = make_html_tag('figcaption', name) if name else ''
        
        code = make_html_tag('code', text, classes=[f'language-{lang}'])
        pre = make_html_tag('pre', code)

        html = make_html_tag('figure', caption + pre, classes=['code-block'])

    return html


def render_heading(node: DocNode) -> str:
    level = node.attrs['level']
    return render_basic(node, f'h{level}')


def render_link(node: DocNode) -> str:
    target = node.attrs['target']

    if not node.attrs['external']:
        # TODO Figure out what the heck I was doing here
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
        frag = f'#{slugify(frag[1:])}'
        target = fname + frag
    
    content = render_node_content(node)
    return make_html_tag('a', content, href=target)


def render_list(node: DocNode) -> str:
    tag = 'ol' if node.attrs['ordered'] else 'ul'
    return render_basic(node, tag)


def render_section(node: DocNode) -> str:
    content = render_node_content(node)
    node.attrs['id'] = slugify(node.rawtext)
    return make_html_tag('section', content, id=node.attrs['id'])


def render_table_cell(node: DocNode):
    tag = 'th' if node.attrs['is_header'] else 'td'
    return render_basic(node, tag)


def render_text(node: DocNode):
    if node.attrs['strong']:
        return render_basic(node, 'strong')
    if node.attrs['emph']:
        return render_basic(node, 'em')
    return render_node_content(node)


default_render_map = {
    NodeType.CODE:          render_code,
    NodeType.HEADING:       render_heading,
    NodeType.LINK:          render_link,
    NodeType.LIST:          render_list,
    NodeType.LIST_ITEM:     lambda node: render_basic(node, 'li'),
    NodeType.PARAGRAPH:     lambda node: render_basic(node, 'p'),
    NodeType.ROOT:          lambda node: render_node_content(node),
    NodeType.SECTION:       render_section,
    NodeType.TABLE:         lambda node: render_basic(node, 'table'),
    NodeType.TABLE_ROW:     lambda node: render_basic(node, 'tr'),
    NodeType.TABLE_CELL:    render_table_cell,
    #NodeType.TAG:           lambda node: '',
    NodeType.TASK:          lambda node: '',
    NodeType.TEXT:          render_text,
    NodeType.TOKEN:         lambda node: escape(node.rawtext),
}


def apply_jinja_template(template: str, *args, **kwargs) -> str:
    global jinja_env

    jinja_template = jinja_env.get_template(template)
    return jinja_template.render(*args, **kwargs)


def init_jinja_environment(templates_dir: Path):
    global jinja_env

    jinja_env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates_dir),
        trim_blocks=True,
        lstrip_blocks=True
    )

    jinja_env.filters['timestamp_to_date'] = timestamp_to_date


jinja_env = None

init_jinja_environment(TEMPLATES_DIR)
