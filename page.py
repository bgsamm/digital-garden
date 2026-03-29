from pathlib import Path
from typing import Iterator
import logging

logger = logging.getLogger(__name__)


class View:
    name = 'null'

    def __init__(self, page: Page):
        self.page = page
    
    def render(self, *args) -> str:
        ...
    
    @property
    def title(self):
        return self.name.capitalize()
    
    @property
    def url(self):
        return self.page.base_url / self.name / 'index.html'


class DocView(View):
    name = 'doc'
    
    def render(self, *args) -> str:
        return ''


class TaskView(View):
    name = 'task'
    
    def render(self, *args) -> str:
        return ''


class DexView(View):
    name = 'dex'
    
    def render(self, *args) -> str:
        return ''


class LogView(View):
    name = 'log'
    
    def render(self, *args) -> str:
        return ''


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
