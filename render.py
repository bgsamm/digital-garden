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


def render_home_page(index):
    pages = list(index.items())
    return _apply_jinja_template('index.html', pages=pages)

