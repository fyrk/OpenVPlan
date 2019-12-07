import os
import string

import htmlmin

os.chdir(os.path.abspath(os.path.dirname(__file__)))


SOURCE_PATH = "website/snippets_source/"
DST_PATH = "website/snippets/"

minifier = htmlmin.Minifier(remove_comments=True, remove_empty_space=True, remove_all_empty_space=True,
                            remove_optional_attribute_quotes=False, reduce_boolean_attributes=True)

snippets = {}
for filename in sorted(filename[:-5] for filename in list(os.walk(SOURCE_PATH))[0][2]
                       if filename.endswith(".html") and not filename.startswith(".")):
    with open(SOURCE_PATH + filename + ".html", "r") as f:
        snippet = f.read()
    do_minify = True
    if snippet.startswith("<!-- extends "):
        first_line, snippet_from_first_line = snippet.split("\n", 1)
        if first_line.endswith(" -->"):
            snippet = snippet_from_first_line
            parent_snippet = first_line[13:-4]
            parent_snippet = snippets[parent_snippet]
            snippet_lines = iter(snippet.split("\n"))
            line = next(snippet_lines)
            if line.startswith("<!-- save to ") and line.endswith(" -->"):
                save_to = line[13:-4]
                line = next(snippet_lines)
            else:
                save_to = None
            assert line.startswith("<!-- SET ") and line.endswith(" -->")
            current_key = line[9:-4]
            current_content = []
            formatting = {}
            while True:
                try:
                    while True:
                        line = next(snippet_lines)
                        if line.startswith("<!-- SET ") and line.endswith(" -->"):
                            break
                        current_content.append(line)
                except StopIteration:
                    formatting[current_key] = minifier.minify("\n".join(current_content))
                    break
                formatting[current_key] = minifier.minify("\n".join(current_content))
                current_key = line[9:-4]
                current_content = []
            snippet = string.Template(parent_snippet)
            snippet = snippet.safe_substitute(formatting)
            do_minify = False
    snippets[filename] = minifier.minify(snippet) if do_minify else snippet
    if "${" not in snippets[filename]:
        with open(os.path.join(DST_PATH + filename + ".html"), "w") as f:
            f.write(snippets[filename])
