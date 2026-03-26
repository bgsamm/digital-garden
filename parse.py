import enum
import logging
logger = logging.getLogger(__name__)
import json
import subprocess
import re

class NodeType(enum.Enum):
    CODE       = enum.auto()
    DUMMY      = enum.auto()
    HEADING    = enum.auto()
    LINK       = enum.auto()
    LIST       = enum.auto()
    LIST_ITEM  = enum.auto()
    META       = enum.auto()
    PARAGRAPH  = enum.auto()
    ROOT       = enum.auto()
    SECTION    = enum.auto()
    TABLE      = enum.auto()
    TABLE_ROW  = enum.auto()
    TABLE_CELL = enum.auto()
    TAG        = enum.auto()
    TASK       = enum.auto()
    TEXT       = enum.auto()
    TOKEN      = enum.auto()

class DocTree:
    def __init__(self):
        self.root = DocNode(NodeType.ROOT)
        self._type_map = {}

    def insert_node(self, node, parent=None):
        node.parent = parent
        if parent is not None:
            parent.children.append(node)
            node.depth = parent.depth + 1

        nodes = self._type_map.setdefault(node.type, [])
        nodes.append(node)

    def walk(self):
        stack = [self.root]
        while len(stack) > 0:
            node = stack.pop()
            yield node
            for child in reversed(node.children):
                stack.append(child)

    def get_nodes_of_type(self, type):
        if type in self._type_map:
            yield from self._type_map[type]

class DocNode:
    def __init__(self, type_):
        self.type = type_
        self.depth = 0
        self.parent = None
        self.rawtext = None
        self.children = []
        self.inlines = []
        self.attrs = {}

    def inner_text(self):
        if self.rawtext is not None:
            return self.rawtext
        return ''.join([inline.inner_text() for inline in self.inlines])

    def walk_parents(self):
        if self.parent is not None:
            yield from self.parent.walk_parents()
            yield self.parent

    def __str__(self):
        return f'{self.type.name} {self.attrs} {repr(self.inner_text())}'

class PandocConverter:
    TASK_STATES = {'todo', 'done'}
    TASK_DIFFS = {'easy', 'med', 'hard'}
    TASK_PRIOS = {'low', 'mid', 'high'}
    URI_SCHEMES = {'http': True, 'https': True, 'file': False}

    def _get_block_type(self, block):
        return block.get('t')

    def _get_block_content(self, block):
        return block.get('c')

    def _unwrap_block_attr(self, attr):
        return {
            'id': attr[0],
            'cls': attr[1],
            'kvs': dict(attr[2])
        }

    def convert_metadata(self, pandoc_ast):
        metadata = {}
    
        for key, block in pandoc_ast['meta'].items():
            t = self._get_block_type(block)
            c = self._get_block_content(block)
    
            if t != 'MetaString':
                logger.warning(f'Unexpected type "{t}" encountered while parsing metadata')
    
            metadata[key] = c
    
        return metadata

    def convert_ast(self, pandoc_ast):
        ast = DocTree()
    
        sections = [ast.root]
        for block in pandoc_ast['blocks']:
            node = self._convert_block(block)
    
            if node.type == NodeType.HEADING:
                name = node.inner_text()
                level = node.attrs['level']
                
                if level < len(sections):
                    sections = sections[:level]
                elif level > len(sections):
                    logger.warning(f'Inconsistent heading level at "{name}"')
                
                section = DocNode(NodeType.SECTION)
                section.rawtext = name
                
                ast.insert_node(section, parent=sections[-1])
                sections.append(section)
    
            ast.insert_node(node, parent=sections[-1])
    
        return ast

    def _convert_blocks(self, blocks):
      return [self._convert_block(block) for block in blocks]

    def _convert_block(self, block):
        t = self._get_block_type(block)
        c = self._get_block_content(block)
    
        if t not in self._conversion_map:
            logger.warning(f'Unhandled block type: {t}')
            logger.debug(f'Block content: {c}')
            node = DocNode(NodeType.DUMMY)
        else:
            node = self._conversion_map[t](self, t, c)
    
        return node

    def _convert_code(self, type_, content):
        node = DocNode(NodeType.CODE)
    
        attr, text = content
        attr = self._unwrap_block_attr(attr)
    
        node.rawtext = text
        node.attrs['name'] = attr['id']
        node.attrs['inline'] = (type_ == 'Code')
    
        classes = attr['cls']
        if len(classes) > 0:
            assert(len(classes) == 1)
            node.attrs['language'] = classes[0]
    
        return node
    
    def _convert_head_or_para(self, type_, content):
        if type_ == 'Header':
            node = DocNode(NodeType.HEADING)
    
            level, attr, inlines = content
            attr = self._unwrap_block_attr(attr)
    
            node.attrs['level'] = level
        else:
            node = DocNode(NodeType.PARAGRAPH)
            inlines = content
    
        node.inlines = inlines = self._convert_blocks(inlines)
    
        if len(inlines) > 0 and inlines[0].type == NodeType.TASK:
            tnode = inlines[0]
    
            tags = [inline for inline in inlines
                    if inline.type == NodeType.TAG]
            
            for node in tags:
                tag = node.rawtext
                if tag in self.TASK_DIFFS:
                    if 'diff' not in tnode.attrs:
                        tnode.attrs['diff'] = tag
                    else:
                        logger.warning(f'Multiple difficult tags')
                elif tag in self.TASK_PRIOS:
                    if 'prio' not in tnode.attrs:
                        tnode.attrs['prio'] = tag
                    else:
                        logger.warning(f'Multiple priority tags')
                else:
                    logger.warning(f'Unknown tag "{tag}"')
            
            # Strip task keyword + following space, and all tags + preceding space
            stop = (inlines.index(tags[0]) - 1) if len(tags) > 0 else None
            tnode.inlines = inlines[2:stop]
    
            return tnode
    
        return node
    
    def _convert_link(self, type_, content):
        node = DocNode(NodeType.LINK)
    
        attr, inlines, target = content
        attr = self._unwrap_block_attr(attr)
    
        target, title = target
        node.attrs['title'] = title
        node.attrs['target'] = target
    
        i = target.find(':')
        if i >= 0 and i < len(target) - 1 and target[i + 1] != ':':
            scheme = target[:i]
            if scheme not in self.URI_SCHEMES:
                logger.warning(f'Unknown link scheme "{scheme}"')
            node.attrs['external'] = self.URI_SCHEMES.get(scheme, False)
        else:
            node.attrs['external'] = False
    
        node.inlines = self._convert_blocks(inlines)
    
        return node
    
    def _convert_list(self, type_, content):
        node = DocNode(NodeType.LIST)
    
        node.attrs['ordered'] = ordered = (type_ == 'OrderedList')
    
        if ordered:
            listattrs, items = content
            start, style, delim = listattrs
            node.attrs['start'] = start
            node.attrs['style'] = self._get_block_type(style)
            node.attrs['delim'] = self._get_block_type(delim)
        else:
            items = content
    
        for block_list in items:
            item = DocNode(NodeType.LIST_ITEM)
            item.inlines = self._convert_blocks(block_list)
            node.inlines.append(item)
    
        return node
    
    def _convert_rawblock(self, type_, content):
        fmt, text = content
    
        if fmt != 'org':
            logger.error(f'Unhandled raw block format: {fmt}')
            return DocNode(NodeType.DUMMY)
    
        matches = re.match(r'#\+(\w+):\s+(.+)', text)
        if matches is None or matches[1].upper() != 'PROPERTY':
            logger.error(f'Unhandled raw block: {text}')
            return DocNode(NodeType.DUMMY)
    
        tokens = matches[2].split()
        key = tokens[0]
        value = tokens[1] if len(tokens) == 2 else tokens[1:]
    
        node = DocNode(NodeType.META)
        node.attrs['key'] = key
        node.attrs['value'] = value
    
        return node
    
    def _convert_span(self, type_, content):
        attr, inlines = content
        attr = self._unwrap_block_attr(attr)
    
        if 'spurious-link' in attr['cls']:
            node = DocNode(NodeType.LINK)
            
            node.attrs['target'] = attr['kvs']['target']
            node.attrs['external'] = False
            
            if len(inlines) > 1:
                logger.warning(f'Spurious link with more than 1 inline')
            
            # Spurious links get wrapped in an undesired 'Emph' block
            node.inlines = self._convert_blocks(inlines)[0].inlines
            return node
    
        if 'tag' in attr['cls']:
            node = DocNode(NodeType.TAG)
            node.rawtext = attr['kvs']['tag-name']
            return node
    
        state = None
        for cls in attr['cls']:
            if cls in self.TASK_STATES:
                state = cls
                break
    
        if state is not None:
            node = DocNode(NodeType.TASK)
            node.attrs['state'] = state
            return node
    
        logger.error(f'Unhandled span: {content}')
        return DocNode(NodeType.DUMMY)
    
    def _convert_table(self, type_, content):
        def unwrap_cell(cell, is_header=False):
            attr, align, rowspan, colspan, children = cell
            attr = self._unwrap_block_attr(attr)
    
            node = DocNode(NodeType.TABLE_CELL)
            node.attrs['is_header'] = is_header
            node.attrs['rowspan'] = rowspan
            node.attrs['colspan'] = colspan
            node.inlines = self._convert_blocks(children)
    
            return node
    
        def unwrap_row(row, is_header=False):
            attr, cells = row
            attr = self._unwrap_block_attr(attr)
    
            node = DocNode(NodeType.TABLE_ROW)
            node.inlines = [unwrap_cell(cell, is_header) for cell in cells]
    
            return node
    
        def unwrap_head(head):
            attr, rows = head
            attr = self._unwrap_block_attr(attr)
    
            if len(rows) == 0:
                return None
    
            if len(rows) > 1:
                logger.warning(f'Table with multi-row header encountered')
    
            return unwrap_row(rows[0], is_header=True)
    
        def unwrap_body(body):
            if len(body) > 1:
                logger.warning(f'Table with multiple bodies encountered')
    
            attr, rowheadcols, head, rows = body[0]
            attr = self._unwrap_block_attr(attr)
    
            if len(head) > 0:
                logger.warning(f'Table body with non-empty head encountered')
    
            return [unwrap_row(row) for row in rows]
    
        node = DocNode(NodeType.TABLE)
    
        attr, caption, colspecs, tablehead, tablebody, tablefoot = content
        attr = self._unwrap_block_attr(attr)
        node.attrs['name'] = attr['id']
    
        header = unwrap_head(tablehead)
        if header is not None:
            node.inlines.append(header)
            node.attrs['cols'] = tuple(cell.inner_text() for cell in header.inlines)
    
        node.inlines += unwrap_body(tablebody)
    
        return node
    
    def _convert_styled_text(self, type_, content):
        node = DocNode(NodeType.TEXT)
        node.inlines = self._convert_blocks(content)
    
        node.attrs['strong'] = (type_ == 'Strong')
        node.attrs['emph'] = (type_ == 'Emph')
    
        return node
    
    def _convert_token(self, type_, content):
        node = DocNode(NodeType.TOKEN)
        node.rawtext = content if content is not None else ' '
        return node

    _conversion_map = {
        'Code':        _convert_code,
        'CodeBlock':   _convert_code,
        'BulletList':  _convert_list,
        'Emph':        _convert_styled_text,
        'Header':      _convert_head_or_para,
        'Link':        _convert_link,
        #'MetaString':  _convert_meta,
        'OrderedList': _convert_list,
        'Para':        _convert_head_or_para,
        'Plain':       _convert_styled_text,
        'RawBlock':    _convert_rawblock,
        'SoftBreak':   _convert_token,
        'Space':       _convert_token,
        'Span':        _convert_span,
        'Str':         _convert_token,
        'Strong':      _convert_styled_text,
        'Table':       _convert_table,
    }

def parse_input_file(fpath):
    pandoc_ast = _run_pandoc(fpath)

    converter = PandocConverter()
    metadata = converter.convert_metadata(pandoc_ast)
    ast = converter.convert_ast(pandoc_ast)

    logger.debug(f'Metadata: {metadata}')
    for node in ast.walk():
        logger.debug('>' * node.depth + str(node))

    return metadata, ast

def _run_pandoc(fpath):
    process = subprocess.run(
        ['pandoc', '-t', 'json', fpath],
        capture_output=True,
        check=True,
        encoding='utf-8')

    return json.loads(process.stdout)
