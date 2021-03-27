"""
Docstring splicing.  Currently only numpydoc style supported.
"""

import re
import warnings
from numpydoc.docscrape import NumpyDocString


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
STRING_SECTIONS = ('Warnings',
                   'Notes',
                   'References',
                   'Examples')
FORMATTERS = {
    **{sec:                     NumpyDocString._str_param_list
       for sec in LISTED_SECTIONS},
    **{sec:                     NumpyDocString._str_section
       for sec in STRING_SECTIONS},
    **{'Signature':             NumpyDocString._str_signature,
        'Summary':              NumpyDocString._str_summary,
        'Extended Summary':     NumpyDocString._str_extended_summary,
        'See Also':             NumpyDocString._str_see_also,
        'index':                NumpyDocString._str_index}
}

# FORMATTERS = {
#     'Signature':            NumpyDocString._str_signature,
#     'Summary':              NumpyDocString._str_summary,
#     'Extended Summary':     NumpyDocString._str_extended_summary,
#     'Parameters':           NumpyDocString._str_param_list,
#     'Returns':              NumpyDocString._str_param_list,
#     'Yields':               NumpyDocString._str_param_list,
#     'Receives':             NumpyDocString._str_param_list,
#     'Other Parameters':     NumpyDocString._str_param_list,
#     'Raises':               NumpyDocString._str_param_list,
#     'Warns':                NumpyDocString._str_param_list,
#     'Warnings':             NumpyDocString._str_section,
#     'See Also':             NumpyDocString._str_see_also,
#     'Notes':                NumpyDocString._str_section,
#     'References':           NumpyDocString._str_section,
#     'Examples':             NumpyDocString._str_section,
#     'Attributes':           NumpyDocString._str_param_list,
#     'Methods':              NumpyDocString._str_param_list,
#     'index':                NumpyDocString._str_index
# }

PARSER = re.compile(
    r"""(?xmi)
    (^\s*)
    \{
        ([A-Z][a-z ]+)
        (?:\[(\w+)\])?
        (?:\.(\w+))?
        (?:\s+as\s+(\w+))?
    \}
    """)


class splice:
    """
    Docstring splicing for callables following numpydoc convention.
    """

    def __init__(self, from_func, *sections, insert=None, replace=None,
                 omit=(), preserve_order=False):
        """
        Initialize splice function decorator.

        Parameters
        ----------
        from_func : callable
            Function from which (parts of) the docstring will be copied.
        insert : dict, optional
            Mapping from directives to callables for inserting docstring 
            sections from various other sources, by default None.
        replace : dict, optional
            Verbatim substitution mapping str -> str, by default None.
        preserve_order : bool, optional
            Whether the order of the sections should be preserved as they appear 
            in the original docstring. If False, the sections will be ordered as 
            follows:
                Signature       
                Summary       
                Extended Summary 
                Parameters    
                Returns       
                Yields        
                Receive       
                Other Parameters 
                Raises        
                Warns         
                Warnings      
                See Al        
                Notes         
                References    
                Examples      
                Attributes    
                Methods       
                index         


        """
        self.from_func = from_func
        self.origin = NumpyDocString(from_func.__doc__)
        self.replace = replace or {}
        self.omit = (omit, ) if isinstance(omit, str) else tuple(omit)
        self.insert = insert or {}
        if len(sections) == 1 and isinstance(sections[0], dict):
            self.insert.update(sections[0])
        else:
            self.insert.update({s.title(): from_func for s in sections})

    def __call__(self, func):
        """
        Main work of creating or updating the function docstring happens here.
        This is a signature preserving decorator that only alters the `__doc__`
        attribute of the object.
        """
        # avoid circular import :|
        from recipes.string import sub

        replacements = self.replace

        # docstring of decorated function. The one to be adapted
        docstring = func.__doc__
        if docstring is None:
            # carbon copy if decorated function has no docstring
            docstring = self.from_func.__doc__
        else:
            # find directives in the docstring of the decorated function and
            # get their replacement texts
            for match in PARSER.finditer(docstring):
                directive = match[0].lstrip()
                replacements[directive] = get_replacement(self.origin, match)

        # make substitutions
        docstring = sub(docstring, replacements)

        # parse the altered docstring
        doc = NumpyDocString(docstring)  # decoratee
        idocs = {}  # docs from which parts will be scraped
        # TODO: make this cache session scoped
        # parse insertion directives
        for directive, ifunc in self.insert.items():
            if isinstance(ifunc, type):
                ifunc = ifunc.__init__

            if ifunc in idocs:
                idoc = idocs[ifunc]
            else:
                idoc = NumpyDocString(ifunc.__doc__)

            parse(directive)
            new = get_replacement(idoc, match)

            if section in LISTED_SECTIONS:
                # read the new parameter
                new = doc._parse_param_list(new)
                if section == 'Parameters':
                    # find position of new parameter and insert it in the list
                    param_names = func.__code__.co_varnames
                    i = param_names.index(rename or key) - \
                        isinstance(func, type)
                    part = doc[section]
                    doc[section] = part[:i] + new + part[i:]
                else:
                    doc[section].append(new)
            else:
                doc[section] = new

        # remove requested sections
        if self.omit:
            match = PARSER.match(directive)
            indent, section, key, attr, rename = match[2], match[3], match[4]
            part = doc[section]
            if key:
                part.pop(key)

        if (replacements or self.insert):
            func.__doc__ = str(doc)
        else:
            warnings.warn(
                f'{self.__class__.__name__} did not make any substitutions in '
                f' docstring for {func}.'
            )

        return func


def parse(directive):
    if (directive[0] + directive[-1]) != '{}':
        directive = directive.join('{}')

    match = PARSER.match(directive)
    indent, section, key, attr, rename = match.groups()
    if section not in LISTED_SECTIONS:
        if key: 
            warnings.warn(
                f'{section!r} section is not a itemized section, yet item {key!r} has been requested.')
            if attr:
                warnings.warn(
                f'Attribute {attr!r} of item {key!r} in section {section!r} does not exist')
            
            
    return indent, section, key, attr, rename


def get_replacement(parsed, match):
    indent, section, key, attr, rename = match.groups()
    directive = match[0].lstrip()
    if section not in parsed:
        warnings.warn(f'Invalid docstring section {section!r}')
        return directive

    part = parsed[section]
    formatter = FORMATTERS[section]
    takes_param = (section in LISTED_SECTIONS + STRING_SECTIONS)
    args = (parsed, *(section, )[:takes_param])

    if not key:
        return indented(formatter(*args), indent)

    has_items = (section in LISTED_SECTIONS)
    if not has_items:
        warnings.warn(f'{section!r} section has no items. Could not lookup '
                      f'item {key!r}.')
        return directive

    # check if item (parameter) available
    names = next(zip(*part))
    if not key in names:
        warnings.warn(f'Could not find {key!r} in section {section!r}')
        return directive

    # get item
    i = names.index(key)
    item = part[i]  # parameter
    if not attr:
        return format_param(rename or item.name,
                            item.type,
                            item.desc,
                            TAB + indent)

    if hasattr(item, attr):
        # get the attribute (decription or whatever)
        return indented(getattr(item, attr), indent)

    warnings.warn(f'{section}[{key}] has no attribute {attr!r}.')
    return directive


def indented(lines, indent=TAB):
    return f'\n{indent}'.join(lines).rstrip()


def format_param(name, kind, descr, indent=TAB):
    return indented([' : '.join((name, kind))] + descr, indent)
