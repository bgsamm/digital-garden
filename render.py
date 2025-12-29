import os
import pandoc
import re

PAGES_DIR = 'pages'

def walk_directory(root, extension='*'):
    for dirpath, dirnames, filenames in os.walk(root):
        for filename in filenames:
            fname, ext = os.path.splitext(filename)
            if extension == '*' or ext == extension:
                fpath = os.path.join(dirpath, filename)
                yield fpath

def parse_org_file(fpath):
    ast = pandoc.read(file=fpath)

    # Unwrap 'Meta' object
    metadata = ast[0][0]
    for k, v in metadata.items():
        # Unwrap 'MetaString' object
        metadata[k] = v[0]
    
    ast[0] = metadata

    ast[1] = unwrap_blocks(ast[1])

    return tuple(ast)

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
            'is-todo': 'todo' in block[0][1],
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

def regex_match(pattern, string):
    match_obj = re.match(pattern, string)
    if match_obj is not None:
        return match_obj.groups()
    return None

def ast_to_html(ast):
    html = '<div id="content">'

    html += ast_nodes_to_html(ast[1])

    html += '</div>'

    return html

def html_escape(s):
    return s.replace('&', '&amp;') \
            .replace('<', '&lt;') \
            .replace('>', '&gt;')

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


for fpath in walk_directory(PAGES_DIR, extension='.org'):
    ast = parse_org_file(fpath)
    
    content = ast_to_html(ast)
    with open('test.html', 'w+') as f:
        f.write(content)
