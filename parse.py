import enum
import util

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
        self.rawtext = None
        self.children = []

    def inner_text(self):
        if self.rawtext is not None:
            return self.rawtext
        return ''.join([child.inner_text() for child in self.children])


def parse_org_file(fpath):
    args = ['-f', 'org', '-t', 'json', fpath]
    json = util.process_run('pandoc', args)
    ast = util.json_parse(json)

    metadata = {}
    for key, block in ast['meta'].items():
        metadata[key] = _pandoc_unwrap_block(block).inner_text()
    
    mtime = util.file_get_mtime(fpath)
    mdate = util.datetime_timestamp_to_date(mtime)
    metadata['modified'] = mdate

    nodes = _pandoc_unwrap_blocks(ast['blocks'])

    return DocTree(metadata, nodes)


def _pandoc_unwrap_block(block):
    t = _pandoc_get_type(block)
    c = _pandoc_get_content(block)

    if t not in _pandoc_unwrapper_map:
        raise TypeError(f'Unhandled block type: {t}')

    node = _pandoc_unwrapper_map[t](t, c)

    return node

def _pandoc_unwrap_blocks(blocks):
    return [_pandoc_unwrap_block(block) for block in blocks]

def _pandoc_get_type(block):
    """Returns the type string of a Pandoc block."""
    return block.get('t')

def _pandoc_get_content(block):
    """Returns the content field of a Pandoc block."""
    return block.get('c')

def _pandoc_unwrap_attr(attr):
    """Unpacks a Pandoc Attr tuple: (identifier, classes, key-value pairs)."""
    # Pandoc Schema: [id, [class1, class2], [[key, val], ...]]
    return {
        'id': attr[0],
        'cls': attr[1],
        'kvs': dict(attr[2])
    }


def _pandoc_unwrap_code(type_, content):
    node = DocNode(NodeType.CODE)

    attr, text = content
    attr = _pandoc_unwrap_attr(attr)

    node.rawtext = text
    node.name = attr['id']
    node.inline = (type_ == 'Code')

    classes = attr['cls']
    if len(classes) > 0:
        assert(len(classes) == 1)
        node.language = classes[0]

    return node

def _pandoc_unwrap_header_or_para(type_, content):
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
        attr = _pandoc_unwrap_attr(attr)

        node.level = level
    else:
        assert(type_ == 'Para')
        node = DocNode(NodeType.PARAGRAPH)
        inlines = content

    node.children = _pandoc_unwrap_blocks(inlines)

    if node.children[0].type == NodeType.TAG:
        convert_to_task(node)

    # Must be done after task conversion, since tasks are tags
    apply_tags(node)

    return node

def _pandoc_unwrap_link(type_, content):
    node = DocNode(NodeType.LINK)

    attr, inlines, target = content
    attr = _pandoc_unwrap_attr(attr)

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

    node.children = _pandoc_unwrap_blocks(inlines)

    return node

def _pandoc_unwrap_list(type_, content):
    node = DocNode(NodeType.LIST)

    node.ordered = (type_ == 'OrderedList')

    if node.ordered:
        listattrs, items = content
        start, style, delim = listattrs
        node.start = start
        node.style = _pandoc_get_type(style)
        node.delim = _pandoc_get_type(delim)
    else:
        items = content

    for block in items:
        item = DocNode(NodeType.LIST_ITEM)
        item.children = _pandoc_unwrap_blocks(block)
        node.children.append(item)

    return node

def _pandoc_unwrap_meta(type_, content):
    node = DocNode(NodeType.META)
    node.rawtext = content
    return node

def _pandoc_unwrap_rawblock(type_, content):
    fmt, text = content
    assert(fmt == 'org')

    matches = util.regex_match(r'#\+(\w+):\s+(.+)', text)
    assert(matches is not None)

    node = DocNode(NodeType.META)
    node.key = matches[0].lower()
    node.value = matches[1]

    return node

def _pandoc_unwrap_span(type_, content):
    attr, inlines = content
    attr = _pandoc_unwrap_attr(attr)

    if 'spurious-link' in attr['cls']:
        node = DocNode(NodeType.LINK)

        node.target = attr['kvs']['target']
        node.external = False

        # Spurious links get wrapped in an 'Emph' block
        assert(len(inlines) == 1)
        node.children = _pandoc_unwrap_blocks(inlines)[0].children
    else:
        node = DocNode(NodeType.TAG)

        if 'tag' in attr['cls']:
            tag = attr['kvs']['tag-name']
        else:
            tag = attr['cls'][0]

        node.rawtext = tag

    return node

def _pandoc_unwrap_table(type_, content):
    def unwrap_cell(cell, is_header=False):
        attr, align, rowspan, colspan, children = cell
        attr = _pandoc_unwrap_attr(attr)

        node = DocNode(NodeType.TABLE_CELL)
        node.is_header = is_header
        node.rowspan = rowspan
        node.colspan = colspan
        node.children = _pandoc_unwrap_blocks(children)

        return node

    def unwrap_row(row, is_header=False):
        attr, cells = row
        attr = _pandoc_unwrap_attr(attr)

        node = DocNode(NodeType.TABLE_ROW)
        node.children = [unwrap_cell(cell, is_header) for cell in cells]

        return node

    def unwrap_head(head):
        attr, rows = head
        attr = _pandoc_unwrap_attr(attr)

        assert(len(rows) <= 1)

        if len(rows) == 0:
            return None
        return unwrap_row(rows[0], is_header=True)

    def unwrap_body(body):
        assert(len(body) == 1)

        attr, rowheadcols, head, rows = body[0]
        attr = _pandoc_unwrap_attr(attr)

        assert(len(head) == 0)

        return [unwrap_row(row) for row in rows]

    node = DocNode(NodeType.TABLE)

    attr, caption, colspecs, tablehead, tablebody, tablefoot = content
    attr = _pandoc_unwrap_attr(attr)

    header = unwrap_head(tablehead)
    if header is not None:
        node.children.append(header)

    node.children += unwrap_body(tablebody)

    return node

def _pandoc_unwrap_textblock(type_, content):
    node = DocNode(NodeType.TEXT)
    node.children = _pandoc_unwrap_blocks(content)

    node.strong = (type_ == 'Strong')
    node.emph = (type_ == 'Emph')

    return node

def _pandoc_unwrap_token(type_, content):
    node = DocNode(NodeType.TOKEN)

    if content is not None:
        node.rawtext = content
    else:
        node.rawtext = ' '

    return node


_pandoc_unwrapper_map = {
    'Code': _pandoc_unwrap_code,
    'CodeBlock': _pandoc_unwrap_code,
    'BulletList': _pandoc_unwrap_list,
    'Emph': _pandoc_unwrap_textblock,
    'Header': _pandoc_unwrap_header_or_para,
    'Link': _pandoc_unwrap_link,
    'MetaString': _pandoc_unwrap_meta,
    'OrderedList': _pandoc_unwrap_list,
    'Para': _pandoc_unwrap_header_or_para,
    'Plain': _pandoc_unwrap_textblock,
    'RawBlock': _pandoc_unwrap_rawblock,
    'SoftBreak': _pandoc_unwrap_token,
    'Space': _pandoc_unwrap_token,
    'Span': _pandoc_unwrap_span,
    'Str': _pandoc_unwrap_token,
    'Strong': _pandoc_unwrap_textblock,
    'Table': _pandoc_unwrap_table,
}
