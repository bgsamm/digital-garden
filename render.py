from parse import NodeType
import jinja2
import logging

logger = logging.getLogger(__name__)


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
