def render_doc_tree(ast):
    views = []

    for view_renderer in _global_views:
        view = view_renderer(ast)
        views.append(view)

    page_type = ast['type']
    for view_renderer in _view_map[page_type]:
        view = view_renderer(ast)
        views.append(view)

    return views


def _render_view_doc(ast):
    ...

def _render_view_task(ast):
    ...


_global_views = [
    _render_view_doc,
    _render_view_task
]

_view_map = {}
