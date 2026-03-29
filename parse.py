from pathlib import Path
from typing import Any, Iterator
import enum
import json
import logging
import re

logger = logging.getLogger(__name__)


TASK_STATES = {'todo', 'done'}
TASK_DIFFS  = {'easy', 'med', 'hard'}
TASK_PRIOS  = {'low', 'mid', 'high'}
URI_SCHEMES = {'http': True, 'https': True, 'file': False}


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
        self.metadata = {}
        self.root = DocNode(NodeType.ROOT)

    def walk(self, filter_type=None):
        stack = [self.root]
        while len(stack) > 0:
            node = stack.pop()
            if filter_type is None or node.type == filter_type:
                yield node
            for child in reversed(node.children):
                stack.append(child)


class DocNode:
    def __init__(self, type: NodeType):
        self.type = type
        self.parent: DocNode | None = None
        self.children: list[DocNode] = []
        
        self.rawtext = None
        self.inlines = []
        self.attrs = {}
    
    @property
    def depth(self) -> int:
        if self.parent is None:
            return 0
        return self.parent.depth + 1
    
    def add_child(self, child: DocNode):
        self.children.append(child)
        child.parent = self
    
    def add_children(self, children: list[DocNode]):
        for child in children:
            self.add_child(child)

    def iter_parents(self, bottom_up=False) -> Iterator[DocNode]:
        if self.parent is not None:
            if bottom_up: yield self.parent
            yield from self.parent.iter_parents(bottom_up)
            if not bottom_up: yield self.parent

    def inner_text(self) -> str:
        if self.rawtext is not None:
            return self.rawtext
        return ''.join([inline.inner_text() for inline in self.inlines])

    def __str__(self):
        return f'{self.type.name} {self.attrs} {repr(self.inner_text())}'


def get_block_type(block: dict) -> str:
    return block.get('t')


def get_block_content(block: dict) -> Any:
    return block.get('c')


def unwrap_block_attr(attr: list) -> dict:
    return {
        'id': attr[0],
        'cls': attr[1],
        'kvs': dict(attr[2])
    }


def convert_code(type: str, content: list) -> DocNode:
    node = DocNode(NodeType.CODE)

    attr, text = content
    attr = unwrap_block_attr(attr)

    node.rawtext = text
    node.attrs['name'] = attr['id']
    node.attrs['inline'] = (type == 'Code')

    classes = attr['cls']
    if len(classes) > 0:
        assert len(classes) == 1
        node.attrs['language'] = classes[0]

    return node


def convert_head_or_para(type: str, content: list) -> DocNode:
    if type == 'Header':
        node = DocNode(NodeType.HEADING)

        level, attr, inlines = content
        attr = unwrap_block_attr(attr)

        node.attrs['level'] = level
    else:
        node = DocNode(NodeType.PARAGRAPH)
        inlines = content

    node.inlines = inlines = convert_blocks(inlines)

    if len(inlines) > 0 and inlines[0].type == NodeType.TASK:
        # TODO Extract to subfunction
        tnode = inlines[0]

        tags = [inline for inline in inlines
                if inline.type == NodeType.TAG]
        
        for node in tags:
            tag = node.rawtext
            if tag in TASK_DIFFS:
                if 'diff' not in tnode.attrs:
                    tnode.attrs['diff'] = tag
                else:
                    logger.warning(f'Multiple difficult tags')
            elif tag in TASK_PRIOS:
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


def convert_link(type: str, content: list) -> DocNode:
    node = DocNode(NodeType.LINK)

    attr, inlines, target = content
    attr = unwrap_block_attr(attr)

    target, title = target
    node.attrs['title'] = title
    node.attrs['target'] = target

    i = target.find(':')
    if i >= 0 and i < len(target) - 1 and target[i + 1] != ':':
        scheme = target[:i]
        if scheme not in URI_SCHEMES:
            logger.warning(f'Unknown link scheme "{scheme}"')
        node.attrs['external'] = URI_SCHEMES.get(scheme, False)
    else:
        node.attrs['external'] = False

    node.inlines = convert_blocks(inlines)

    return node


def convert_list(type: str, content: list) -> DocNode:
    node = DocNode(NodeType.LIST)

    node.attrs['ordered'] = ordered = (type == 'OrderedList')

    if ordered:
        listattrs, items = content
        start, style, delim = listattrs
        node.attrs['start'] = start
        node.attrs['style'] = get_block_type(style)
        node.attrs['delim'] = get_block_type(delim)
    else:
        items = content

    for block_list in items:
        item = DocNode(NodeType.LIST_ITEM)
        item.add_children(convert_blocks(block_list))
        node.add_child(item)

    return node


def convert_rawblock(type: str, content: list) -> DocNode:
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


def convert_span(type: str, content: list) -> DocNode:
    attr, inlines = content
    attr = unwrap_block_attr(attr)

    if 'spurious-link' in attr['cls']:
        # TODO Extract to subfunction
        node = DocNode(NodeType.LINK)
        
        node.attrs['target'] = attr['kvs']['target']
        node.attrs['external'] = False
        
        if len(inlines) > 1:
            logger.warning(f'Spurious link with more than 1 inline')
        
        # Spurious links get wrapped in an undesired 'Emph' block
        assert len(inlines) == 1 and get_block_type(inlines[0]) == 'Emph'
        node.inlines = convert_blocks(get_block_content(inlines[0]))

        return node

    if 'tag' in attr['cls']:
        node = DocNode(NodeType.TAG)
        node.rawtext = attr['kvs']['tag-name']
        return node

    state = None
    for cls in attr['cls']:
        if cls in TASK_STATES:
            state = cls
            break

    if state is not None:
        node = DocNode(NodeType.TASK)
        node.attrs['state'] = state
        return node

    logger.error(f'Unhandled span: {content}')
    return DocNode(NodeType.DUMMY)


def convert_table(type: str, content: list) -> DocNode:
    def unwrap_cell(cell, is_header=False):
        attr, align, rowspan, colspan, children = cell
        attr = unwrap_block_attr(attr)

        node = DocNode(NodeType.TABLE_CELL)
        node.attrs['is_header'] = is_header
        node.attrs['rowspan'] = rowspan
        node.attrs['colspan'] = colspan

        node.add_children(convert_blocks(children))

        return node

    def unwrap_row(row, is_header=False):
        attr, cells = row
        attr = unwrap_block_attr(attr)

        node = DocNode(NodeType.TABLE_ROW)
        node.add_children([unwrap_cell(cell, is_header) for cell in cells])

        return node

    def unwrap_head(head):
        attr, rows = head
        attr = unwrap_block_attr(attr)

        if len(rows) == 0:
            return None

        if len(rows) > 1:
            logger.warning(f'Table with multi-row header encountered')

        return unwrap_row(rows[0], is_header=True)

    def unwrap_body(body):
        if len(body) > 1:
            logger.warning(f'Table with multiple bodies encountered')

        attr, rowheadcols, head, rows = body[0]
        attr = unwrap_block_attr(attr)

        if len(head) > 0:
            logger.warning(f'Table body with non-empty head encountered')

        return [unwrap_row(row) for row in rows]

    node = DocNode(NodeType.TABLE)

    attr, caption, colspecs, tablehead, tablebody, tablefoot = content
    attr = unwrap_block_attr(attr)
    node.attrs['name'] = attr['id']

    header = unwrap_head(tablehead)
    if header is not None:
        node.add_child(header)
        node.attrs['cols'] = tuple(cell.inner_text() for cell in header.children)

    node.add_children(unwrap_body(tablebody))

    return node


def convert_styled_text(type: str, content: list) -> DocNode:
    node = DocNode(NodeType.TEXT)
    node.inlines = convert_blocks(content)

    node.attrs['strong'] = (type == 'Strong')
    node.attrs['emph'] = (type == 'Emph')

    return node


def convert_token(type: str, content: str | None) -> DocNode:
        node = DocNode(NodeType.TOKEN)
        node.rawtext = content if content is not None else ' '
        return node


conversion_map = {
    'Code':        convert_code,
    'CodeBlock':   convert_code,
    'BulletList':  convert_list,
    'Emph':        convert_styled_text,
    'Header':      convert_head_or_para,
    'Link':        convert_link,
    'OrderedList': convert_list,
    'Para':        convert_head_or_para,
    'Plain':       convert_styled_text,
    'RawBlock':    convert_rawblock,
    'SoftBreak':   convert_token,
    'Space':       convert_token,
    'Span':        convert_span,
    'Str':         convert_token,
    'Strong':      convert_styled_text,
    'Table':       convert_table,
}


def convert_blocks(blocks: list[dict]) -> list[DocNode]:
    return [convert_block(block) for block in blocks]


def convert_block(block: dict) -> DocNode:
    t = get_block_type(block)
    c = get_block_content(block)

    converter = conversion_map.get(t)

    if converter is None:
        logger.warning(f'Unhandled block type: {t}')
        logger.debug(f'Block content: {c}')
        node = DocNode(NodeType.DUMMY)
    else:
        node = converter(t, c)

    return node


def convert_metadata(pandoc_ast: dict) -> dict:
    metadata = {}

    for key, block in pandoc_ast['meta'].items():
        t = get_block_type(block)
        c = get_block_content(block)

        if t != 'MetaString':
            logger.warning(f'Unexpected type "{t}" encountered while parsing metadata')

        metadata[key] = c

    return metadata


def convert_ast(pandoc_ast: dict) -> DocTree:
    ast = DocTree()

    ast.metadata = convert_metadata(pandoc_ast)

    sections = [ast.root]
    for block in pandoc_ast['blocks']:
        node = convert_block(block)

        if node.type == NodeType.HEADING:
            # TODO Extract to subfunction
            name = node.inner_text()
            level = node.attrs['level']
            
            if level < len(sections):
                sections = sections[:level]
            elif level > len(sections):
                logger.warning(f'Inconsistent heading level at "{name}"')
            
            section = DocNode(NodeType.SECTION)
            section.rawtext = name
            
            sections[-1].add_child(section)
            sections.append(section)

        sections[-1].add_child(node)

    return ast


def run_pandoc(path: Path) -> dict:
    import subprocess

    process = subprocess.run(
        ['pandoc', '-t', 'json', path],
        capture_output=True,
        check=True,
        encoding='utf-8'
    )

    return json.loads(process.stdout)


def parse(path: Path) -> DocTree:
    pandoc_ast = run_pandoc(path)

    ast = convert_ast(pandoc_ast)

    logger.debug(f'Metadata: {ast.metadata}')
    for node in ast.walk():
        logger.debug('>' * node.depth + str(node))

    return ast
