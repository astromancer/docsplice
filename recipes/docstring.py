"""
Docstring helpers
"""

import re
from recipes.lists import index
import warnings
from numpydoc.docscrape import NumpyDocString
from recipes.string import iter_brackets, replace


TAB = ' ' * 4
LISTED_SECTIONS = ('Parameters',
                   'Returns',
                   'Yields',
                   'Receives',
                   'Other Parameters',
                   'Raises',
                   'Warns',
                   'Attributes',
                   'Methods')
FORMATTERS = {
    'Signature': NumpyDocString._str_signature,
    'Summary': NumpyDocString._str_summary,
    'Extended Summary': NumpyDocString._str_extended_summary,
    'Parameters': NumpyDocString._str_param_list,
    'Returns': NumpyDocString._str_param_list,
    'Yields': NumpyDocString._str_param_list,
    'Receives': NumpyDocString._str_param_list,
    'Other Parameters': NumpyDocString._str_param_list,
    'Raises': NumpyDocString._str_param_list,
    'Warns': NumpyDocString._str_param_list,
    'Warnings': NumpyDocString._str_section,
    'See Also': NumpyDocString._str_see_also,
    'Notes': NumpyDocString._str_section,
    'References': NumpyDocString._str_section,
    'Examples': NumpyDocString._str_section,
    'Attributes': NumpyDocString._str_param_list,
    'Methods': NumpyDocString._str_param_list,
    'index': NumpyDocString._str_index
}

PARSER = re.compile(
    r"""(?xmi)
    (^\s+)
    \{
        ([A-Z][a-z ]+)
        (?:\[(\w+)\])?
        (?:\.(\w+))?
    \}
    """)


class clone_doc:
    """docstring helper"""

    def __init__(self, from_func, *sections, **parameters):
        self.from_func = from_func
        self.sections = map(str.title, sections)
        self.parameters = parameters
        self.origin = NumpyDocString(self.from_func.__doc__)

    def __call__(self, func):
        doc = func.__doc__
        replacements = {}

        for match in PARSER.finditer(doc):
            indent, name, key, attr = match.groups()
            directive = match[0].lstrip()
            if name not in self.origin:
                warnings.warn(f'Invalid docstring section {name!r}')
                continue

            part = self.origin[name]
            formatter = FORMATTERS[name]
            args = (self.origin,  *(name, )[:(name in LISTED_SECTIONS)])

            if not key:
                replacements[directive] = indented(formatter(*args), indent)
                # nothing else to do
                continue

            has_items = (name in LISTED_SECTIONS)
            if not has_items:
                warnings.warn(f'{name} section has no items. Could not lookup '
                              f'item {key}')
                continue

            # check if item (parameter) available
            i = index(next(zip(*part)), key, default=None)
            if i is None:
                warnings.warn(f'Could not find {key} in section {name}')
                continue

            # get item
            item = part[i]  # parameter
            if not attr:
                replacements[directive] = prep_par(item, TAB + indent)
                continue

            if hasattr(item, attr):
                # get the attribute (decription or whatever)
                replacements[directive] = indented(
                    getattr(item, attr), indent)
                continue

            warnings.warn(f'{name}[{key}] has no attribute {attr}.')

        if replacements:
            func.__doc__ = replace(doc, replacements)
        else:
            warnings.warn(
                f'{self.__class__.__name__} did not make any substitutions in '
                f' docstring for {func}'
            )

        return func


def indented(lines, indent=TAB):
    return f'\n{indent}'.join(lines).rstrip()


def prep_par(par, indent=TAB):
    return indented([' : '.join((par.name, par.type))] + par.desc, indent)
