import render
import parse
from parse import NodeType, DocNode
import util

BUILD_DIR = 'build'
PAGES_DIR = 'pages'
STYLES_DIR = 'styles'
SCRIPTS_DIR = 'scripts'

def main():
    util.dir_make(BUILD_DIR)
    util.dir_empty(BUILD_DIR)

    pages = []
    for dirpath, fname, ext in util.dir_walk(PAGES_DIR):
        if fname[0] == '.' or fname[0] == '#' or ext != '.org':
            continue
    
        fpath = util.path_join(dirpath, fname + ext)
        ast = parse.parse_org_file(fpath)
        
        page_url = util.path_join(PAGES_DIR, fname)
        page = render.generate_page(ast, page_url)
        
        for view in page.views:
            view_html = render.render_page_view(page, view)
            outpath = util.path_join(BUILD_DIR, view.url, 'index.html')
            util.file_write(outpath, view_html)
    
        pages.append(page)

    homepage_html = render.render_page('index.html', title='Home', pages=pages)
    outpath = util.path_join(BUILD_DIR, 'index.html')
    util.file_write(outpath, homepage_html)

    outdir = util.path_join(BUILD_DIR, STYLES_DIR)
    util.dir_copy(STYLES_DIR, outdir)
    
    outdir = util.path_join(BUILD_DIR, SCRIPTS_DIR)
    util.dir_copy(SCRIPTS_DIR, outdir)

if __name__ == '__main__':
    main()
