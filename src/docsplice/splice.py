"""
Docstring splicing and fstring-like substitutions.
"""

from collections import defaultdict
import re
import warnings
from numpydoc.docscrape import NumpyDocString
import logging

# module level logger
logging.basicConfig()
logger = logging.getLogger(__file__)
logger.setLevel(logging.INFO)


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


# ---------------------------------------------------------------------------- #
# helpers

def indented(lines, indent=TAB):
    return f'\n{indent}'.join(lines).rstrip()


def format_param(name, kind, descr, indent=TAB):
    return indented([' : '.join((name, kind))] + descr, indent)

# def parse_examples # TODO


# ---------------------------------------------------------------------------- #
# cache

class DocStringCache(defaultdict):
    """Cache for parsed docs"""

    def __init__(self, *args, **kws):
        super().__init__(NumpyDocString, *args, **kws)

    def __missing__(self, key):
        # pylint: disable=not-callable
        new = self[key] = self.default_factory(key)
        return new


# Module scoped cache
docStringCache = DocStringCache()

# ---------------------------------------------------------------------------- #
# directives


class Directive:
    """
    A substitution directive in a style similar to fstrings.  These are bits of
    string in the docustring that specify which parts of the incoming docstring
    to substitute.

    For example:
        {Summary}
        {Parameters[name] as new_name}
        {Returns[result].desr}

    These will use be replaced by the corresponding values in the parsed 
    `NumpyDocString` of the `from_func`
    """

    regex = re.compile(
        r"""(?xm)
        (?P<indent>^\s*)
        (?P<directive>
            \{
                (?i:(?P<section>[a-z]+))
                (\[(?P<key>\w+)\])?
                (\.(?P<attr>\w+))?
                (\s+as\s+(?P<rename>\w+))?
            \}
        )
        """)

    # Attributes
    directive: str
    indent: str
    section: str
    key: str
    attr: str
    rename: str

    @classmethod
    def parse(cls, string):
        if (string[0] + string[-1]) != '{}':
            string = string.join('{}')

        match = cls.regex.match(string)
        if match is None:
            raise ValueError(f'Directive {string!r} could not be parsed!')

        return cls(**match.groupdict())

    @classmethod
    def iter(cls, docstring):
        for match in cls.regex.finditer(docstring):
            yield cls(**match.groupdict())

    def __init__(self, **parts):
        self.__dict__.update(**parts)
        section, key, attr = self.section, self.key, self.attr
        self.section = section.title()
        if not self.section in NumpyDocString.sections:

            raise ValueError(f'{self.section} is not a valid section name.')

        if section not in LISTED_SECTIONS:
            if key:
                warnings.warn(
                    f'{section!r} section is not a itemized section, yet item '
                    f'{key!r} has been requested.')
                if attr:
                    warnings.warn(
                        f'Attribute {attr!r} of item {key!r} in section '
                        f'{section!r} does not exist')

    def __str__(self):
        return self.directive

    def __iter__(self):
        yield from self.parts

    @property
    def parts(self):
        return (self.indent, self.section, self.key, self.attr, self.rename)

    def get_replacement(self, parsed_doc):
        directive = self.directive
        indent, section, key, attr, rename = self

        if section not in parsed_doc:
            warnings.warn(f'Invalid docstring section {section!r}')
            return directive

        part = parsed_doc[section]
        formatter = FORMATTERS[section]
        takes_param = (section in LISTED_SECTIONS + STRING_SECTIONS)
        args = (parsed_doc, *(section, )[:takes_param])

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

# ---------------------------------------------------------------------------- #
# decorator


class splice:
    """
    Decorator for splicing numpydoc style docstrings.
    """

    def __init__(self, from_func, *sections, insert=None, replace=None,
                 omit=(), onfail=logger.warning, preserve_order=False):
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
        onfail : callable, optional
            What to do when the decorator throws an exception
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
                See Also        
                Notes         
                References    
                Examples      
                Attributes    
                Methods       
                index         


        """
        self.from_func = from_func
        self.origin = NumpyDocString(from_func.__doc__)
        self.replacement = replace or {}
        self.removal = (omit, ) if isinstance(omit, str) else tuple(omit)
        self.insertion = insert or {}
        if len(sections) == 1 and isinstance(sections[0], dict):
            self.insertion.update(sections[0])
        else:
            self.insertion.update(
                {s.capitalize(): from_func for s in sections})

        self.exception_hook = onfail

    def __call__(self, func):
        # pylint: disable=broad-except
        try:
            return self.splice(func)
        except Exception as err:
            self.exception_hook(err)
            return func

    def splice(self, func):
        """
        Main work of creating or updating the function docstring happens here.
        This is a signature preserving decorator that only alters the `__doc__`
        attribute of the object.
        """

        # docstring of decorated function. The one to be adapted.
        docstring = func.__doc__

        # make substitutions
        docstring = self.replace(docstring)

        # parse the update docstring
        doc = NumpyDocString(docstring)

        # parse directives and insert
        doc = self.insert(func, doc)

        # remove omitted sections / parameters
        self.remove(doc)

        # write the new docstring
        if (self.replacement or self.insertion):
            func.__doc__ = str(doc)
        else:
            warnings.warn(
                f'{self.__class__.__name__} did not alter docstring for {func}.'
            )

        return func

    def replace(self, docstring):
        # avoid circular import :|
        from recipes.string import sub

        # First find directives in the docstring of the decorated function and,
        # # substitute the replacement texts
        if docstring is None:
            # if decorated function has no docstring carbon copy the docstring
            # from input source
            docstring = self.from_func.__doc__
        else:
            for directive in Directive.iter(docstring):
                self.replacement[str(directive)] = directive.get_replacement(
                    self.origin)

        docstring = sub(docstring, self.replacement)
        return docstring

    def insert(self, func, doc):
        # parse the altered docstring

        idocs = {}  # docs from which parts will be scraped

        for directive, ifunc in self.insertion.items():
            if isinstance(ifunc, type):
                ifunc = ifunc.__init__
            if ifunc in idocs:
                idoc = idocs[ifunc]
            else:
                idoc = NumpyDocString(ifunc.__doc__)

            directive = _, section, key, _, rename = Directive.parse(directive)
            new = directive.get_replacement(idoc)
            if section in LISTED_SECTIONS:
                # read the new parameter
                new = doc._parse_param_list(new)
                if section == 'Parameters':
                    # find position of new parameter and insert it in the list
                    par_names = func.__code__.co_varnames
                    i = par_names.index(rename or key) - isinstance(func, type)
                    part = doc[section]
                    doc[section] = part[:i] + new + part[i:]
                else:
                    doc[section].extend(new)
            else:
                doc[section] = new
        return doc

    def remove(self, doc):
        for directive in self.removal:
            _, section, key, attr, _ = Directive.parse(directive)
            part = doc[section]
            if key:
                if attr:
                    part[key]. attr = ''
                else:
                    part[key] = doc.sections[key]
