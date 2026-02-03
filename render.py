def render_page(template, *args, **kwargs):
    jinja_template = jinja_env.get_template(template)
    return jinja_template.render(*args, **kwargs)

def render_page_view(page, view):
    jinja_template = jinja_env.get_template(f'view_{view.id}.html')
    return jinja_template.render(page=page, view=view)
