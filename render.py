import logging
logger = logging.getLogger(__name__)
import jinja2
from parse import NodeType
import util

TEMPLATES_DIR = 'templates'

class DocView:
    name = 'doc'

    def generate(self, ast):
        content = self._render_node(ast.root)

        toc = ''
        prev_depth = 0
        for node in ast.get_nodes_of_type(NodeType.SECTION):
            if node.depth > prev_depth:
                toc += '<ul><li>' * (node.depth - prev_depth)
            else:
                if node.depth < prev_depth:
                    toc += '</li></ul>' * (prev_depth - node.depth)
                toc += '</li><li>'
            id_ = util.html_slugify(node.rawtext)
            toc += f'<a href="#{id_}">{node.rawtext}</a>'
            prev_depth = node.depth
        toc += '</li></ul>' * prev_depth

        return {'content': content, 'toc': toc}

    def _render_node(self, node):
        if node.type not in self._render_map:
            raise TypeError(f'Unhandled node type: {node.type}')
    
        renderer = self._render_map[node.type]
        if renderer is None:
            return ''
    
        html = renderer(self, node)
        return html

    def _render_nodes(self, nodes):
        html = ''
        for node in nodes:
            html += self._render_node(node)
        return html

    def _render_code(self, node):
        text = util.html_escape(node.rawtext).strip()
    
        if node.attrs['inline']:
            html = f'<code class="code-inline">{text}</code>'
        else:
            name = node.attrs['name']
            lang = node.attrs['language']
    
            html = '<figure class="code-block">'
            if len(name) > 0:
                html += f'<figcaption>{name}</figcaption>'
            html += f'<pre><code class="language-{lang}">'
            html += text
            html += '</code></pre></figure>'
    
        return html
    
    def _render_default(self, node, tag, **kwargs):
        body = self._render_nodes(node.inlines)
        attrs = ''.join([f' {k}="{v}"' for k,v in kwargs.items()])
        return f'<{tag}{attrs}>{body}</{tag}>'
    
    def _render_heading(self, node):
        id_ = util.html_slugify(node.inner_text())
        level = node.attrs['level']
        tag = f'h{level}'
        return self._render_default(node, tag, id=id_)
    
    def _render_link(self, node):
        target = node.attrs['target']
        if not node.attrs['external']:
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
        return self._render_default(node, 'a', href=target)
    
    def _render_list(self, node):
        tag = 'ol' if node.attrs['ordered'] else 'ul'
        return self._render_default(node, tag)
    
    def _render_list_item(self, node):
        return self._render_default(node, 'li')
    
    def _render_paragraph(self, node):
        return self._render_default(node, 'p')
    
    def _render_root(self, node):
        return self._render_nodes(node.children)
    def _render_section(self, node):
        html = '<section>'
        html += self._render_nodes(node.children)
        html += '</section>'
        return html
    def _render_table(self, node):
        return self._render_default(node, 'table')
    
    def _render_table_row(self, node):
        return self._render_default(node, 'tr')
    
    def _render_table_cell(self, node):
        tag = 'th' if node.attrs['is_header'] else 'td'
        return self._render_default(node, tag)
    
    def _render_text(self, node):
        if node.attrs['strong']:
            return self._render_default(node, 'strong')
        if node.attrs['emph']:
            return self._render_default(node, 'em')
        return self._render_nodes(node.inlines)
    
    def _render_token(self, node):
        return util.html_escape(node.rawtext)

    _render_map = {
        NodeType.CODE: _render_code,
        NodeType.HEADING: _render_heading,
        NodeType.LINK: _render_link,
        NodeType.LIST: _render_list,
        NodeType.LIST_ITEM: _render_list_item,
        NodeType.META: None,
        NodeType.PARAGRAPH: _render_paragraph,
        NodeType.ROOT: _render_root,
        NodeType.SECTION: _render_section,
        NodeType.TABLE: _render_table,
        NodeType.TABLE_ROW: _render_table_row,
        NodeType.TABLE_CELL: _render_table_cell,
        NodeType.TAG: None,
        NodeType.TASK: None,
        NodeType.TEXT: _render_text,
        NodeType.TOKEN: _render_token,
    }

class DexView:
    name = 'dex'

    def generate(self, ast):
        link_prefix = ''
        image_prefix = ''
        for node in ast.get_nodes_of_type(NodeType.META):
            if node.attrs['key'] == 'image_prefix':
                image_prefix = node.attrs['value']
            elif node.attrs['key'] == 'link_prefix':
                link_prefix = node.attrs['value']
    
        dex_table = None
        for node in ast.get_nodes_of_type(NodeType.TABLE):
            if node.attrs['name'] == 'dex':
                dex_table = node
                break
    
        if dex_table is None:
            logger.error('No dex table found!')
            return {}
    
        dex_attrs = [col.lower() for col in dex_table.attrs['cols']]
    
        dex = []
        progress = 0
        for row in dex_table.inlines[1:]:
            values = [cell.inner_text() for cell in row.inlines]
            item = dict(zip(dex_attrs, values))
    
            item['checked'] = (item['checked'].lower() == 'y')
            if 'image' in item and item['image']:
                item['image'] = image_prefix + item['image']
            if 'link' in item and item['link']:
                item['link'] = link_prefix + item['link']
    
            if item['checked']:
                progress += 1
    
            dex.append(item)
    
        return { 'dex': dex, 'progress': progress }

class LogView:
    name = 'log'

    def generate(self, ast):
        log_table = None
        for node in ast.get_nodes_of_type(NodeType.TABLE):
            if node.attrs['name'] == 'log':
                log_table = node
                break
    
        log = { 'cols': [], 'rows': [] }
        if log_table is not None:
            log['cols'] = log_table.attrs['cols']
    
            for row in log_table.inlines[1:]:
                values = [cell.inner_text() for cell in row.inlines]
                log['rows'].append(values)
        else:
            logger.warning('No log table found!')
    
        return { 'log': log }

class TaskView:
    name = 'task'

    def generate(self, ast):
        tasks = []
    
        for node in ast.get_nodes_of_type(NodeType.TASK):
            task = {}
            task['state'] = node.attrs['state']
            task['description'] = node.inner_text()
            if node.parent.type == NodeType.ROOT:
                section = '-'
            else:
                sections = [section.rawtext for section in node.walk_parents()]
                section = ' > '.join(sections[1:])
            task['section'] = section
            task['diff'] = node.attrs.get('diff', None)
            task['prio'] = node.attrs.get('prio', None)
            tasks.append(task)
    
        return {'tasks': tasks}

def render_home_page(index):
    pages = list(index.items())
    return _apply_jinja_template('index.html', pages=pages)

def render_page(name, meta, ast):
    views = []

    page_type = meta.get('type', 'doc')
    view_objs = [cls() for cls in _view_map[page_type]]
    for view in view_objs:
        view_data = view.generate(ast)
        view_data['name'] = view.name
        view_html = _apply_jinja_template(
            f'view_{view.name}.html',
            page=meta,
            view=view_data,
            views=view_objs,
            name=name)
        views.append((view.name, view_html))

    return views

_view_map = {
    'doc': [DocView, TaskView],
    'dex': [DexView, LogView, TaskView],
}

def _apply_jinja_template(template, *args, **kwargs):
    jinja_template = jinja_env.get_template(template)
    return jinja_template.render(*args, **kwargs)

def timestamp_to_date(timestamp):
    import datetime as dt
    dt_obj = dt.datetime.fromtimestamp(timestamp, dt.UTC)
    return dt_obj.strftime('%Y-%m-%d')

jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
    trim_blocks=True,
    lstrip_blocks=True
)
jinja_env.filters['timestamp_to_date'] = timestamp_to_date
