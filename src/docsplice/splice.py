"""
Docstring splicing and fstring-like substitutions.
"""

from collections import defaultdict
import re
import inspect
import warnings as wrn
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

# {name: getattr(NumpyDocString, f'_str_{name}'.lower().replace(' ', '_'))
#  for name in ('Signature',
#               'Summary',
#               'Extended Summary',
#               'See Also',
#               'index')
#  }

# ---------------------------------------------------------------------------- #
# cache


class DocStringCache(defaultdict):
    """Cache for parsed docs"""

    def __init__(self, *args, **kws):
        super().__init__(NumpyDocString, *args, **kws)

    def __missing__(self, func):
        # pylint: disable=not-callable
        new = self[func] = self.default_factory(func.__doc__)
        return new


# Module scoped cache
docStringCache = DocStringCache()

# ---------------------------------------------------------------------------- #
# helpers


def indented(lines, indent=TAB):
    return f'\n{indent}'.join(lines).rstrip()


def format_param(name, kind, descr, indent=TAB):
    return indented([' : '.join((name, kind))] + descr, indent)

def get_param_dict(doc):
    return {p.name: p for p in doc['Parameters']}

# def parse_examples # TODO


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
        ^(?P<indent>[%s\ ]*)
        (?P<directive>
            \{
                (?i:(?P<section>[a-z]+))
                (\[(?P<key>\w+)\])?
                (\.(?P<attr>\w+))?
                (\s+as\s+(?P<rename>\w+))?
                (\s*=\s*(?P<default>[^}]+))?
            \}
        )
        """ % '\t')

    # Attributes
    directive: str
    indent: str
    section: str
    key: str
    attr: str
    rename: str
    default: str

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
        if self.section not in NumpyDocString.sections:
            raise ValueError(f'{self.section} is not a valid section name.')

        if key and (section not in LISTED_SECTIONS):
            wrn.warn(
                f'{section!r} section is not a itemized section, yet item '
                f'{key!r} has been requested.')
            if attr:
                wrn.warn(
                    f'Attribute {attr!r} of item {key!r} in section '
                    f'{section!r} does not exist')

    def __str__(self):
        return self.directive

    def __iter__(self):
        yield from self.parts

    @property
    def parts(self):
        return (self.indent, self.section, self.key, self.attr, self.rename,
                self.default)

    def get_sub(self, func):
        # func arg only needed if we plan to update the default in the parameter
        # description, so we can look up the old default.
        directive = self.directive
        indent, section, key, attr, rename, default = self
        parsed_doc = docStringCache[func]
        if section not in parsed_doc:
            wrn.warn(f'Invalid docstring section {section!r}')
            return directive

        part = parsed_doc[section]
        takes_param = (section in LISTED_SECTIONS + STRING_SECTIONS)
        args = (parsed_doc, *(section, )[:takes_param])

        if not key:
            formatter = FORMATTERS[section]
            return indented(formatter(*args), indent)

        has_items = (section in LISTED_SECTIONS)
        if not has_items:
            wrn.warn(f'{section!r} section has no items. Could not lookup '
                     f'item {key!r}.')
            return directive

        # check if item (parameter) available
        names = next(zip(*part))
        if key not in names:
            wrn.warn(f'Could not find {key!r} in section {section!r}')
            return directive

        # get item from list of (Parameters/.../)
        i = names.index(key)
        item = part[i]  # parameter
        if not attr:
            if default:
                params = inspect.signature(func).parameters
                par = params[key]
                if par.default is par.empty:
                    wrn.warn(
                        f'Not replacing default value for {section}[{key}]: '
                        f'Function parameter {key!r} has no default value.'
                    )
                else:
                    # replace text for old default with new val passed by user
                    old_default = str(par.default)
                    for i, line in enumerate(item.desc):
                        item.desc[i] = line.replace(old_default, default)

            return format_param(rename or item.name,
                                item.type,
                                item.desc,
                                TAB + indent)

        if hasattr(item, attr):
            # get the attribute (decr)
            return indented(getattr(item, attr), indent)

        wrn.warn(f'{section}[{key}] has no attribute {attr!r}.')
        return directive


def get_subs(docstring, from_func):
    # if from_func is None, we are spliceing from multiple sources. This
    # will be handeled in the `insert` method
    subs = {}
    if from_func:
        # Find directives in the docstring of the decorated function
        # and, substitute the replacement texts
        for directive in Directive.iter(docstring):
            subs[str(directive)] = \
                directive.get_sub(from_func)
    return subs


# ---------------------------------------------------------------------------- #
# decorator


class splice:
    """
    Decorator for splicing numpydoc style docstrings.
    """

    def __init__(self, from_func, *sections, insert=None, replace=None,
                 omit=(), onfail=logger.exception, preserve_order=False):
        """
        Initialize splice function decorator.

        Parameters
        ----------
        from_func : callable or dict
            Function from which (parts of) the docstring will be copied.
        *sections : str or tuple of str
            Sections of the docstring that will be populated from `from_func`
        insert : dict, optional
            Mapping from directives to callables for inserting docstring
            sections from various other sources, by default None.
        replace : dict, optional
            Verbatim substitution mapping str -> str, by default None.
        onfail : callable, optional
            What to do when the decorator throws an exception. Since the
            function of this decorator is not mission critical, it's better to
            emit warnings when something goes wrong rather than raise
            exceptions. This is the default behaviour. However, you might want
            to set this to `logger.exception` when running your unit tests.
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
        insert = insert or {}
        if isinstance(from_func, dict):
            insert = from_func
            from_func = None
        elif not callable(from_func):
            raise ValueError(
                f'Parameter `from_func` must be a callable, or a dictionary '
                f'of callables, not {type(from_func)}'
            )

        if from_func is None and sections:
            raise ValueError(
                '`from_func` should be given when passing section names '
                'directly.'
            )
        if sections:
            maybe_dict, *sections = sections
            if isinstance(maybe_dict, dict):
                insert = maybe_dict
            else:
                sections = (maybe_dict, *sections)

        # sections passed as arguments are inserted
        insert.update({s.capitalize(): from_func for s in sections})

        self.from_func = from_func
        self.origin = None      # parsed docstring of decorated function if any
        self.to_sub = replace or {}
        self.to_omit = (omit, ) if isinstance(omit, str) else tuple(omit)
        self.directives = insert
        self.exception_hook = onfail

    def __call__(self, func):
        # Handle exceptions here
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
        # avoid circular import :|
        from recipes.string import sub

        # docstring of decorated function. The one to be adapted.
        self.origin = docstring = func.__doc__

        # make substitutions. verbatim substitutions happen
        if docstring is None:
            # if decorated function has no docstring carbon copy the
            # docstring from input source
            # sourcery skip: assign-if-exp, merge-else-if-into-elif
            if callable(self.from_func):
                docstring = self.from_func.__doc__
            else:
                # splicing from multiple sources.  Start from a blank slate
                docstring = ''
        else:
            # decorated function has a docstring. Look for directives and
            # substitute them
            if callable(self.from_func):
                # new = self.sub(docstring)
                self.to_sub.update(get_subs(docstring, self.from_func))
                if self.to_sub:
                    new = sub(docstring, self.to_sub)
                    # TODO: do things in the order in which arguments were passed
                    if new == docstring:
                        wrn.warn('Docstring for function {func} identical '
                                 'after substitution')
                    docstring = new
                # elif 'Parameters' in self.directives:
                #     # no directives found in docstring. Fill parameters automatically
                #     odoc = NumpyDocString(self.origin)
                #     odoc['Parameters']

            else:
                'multi-source without explicit mapping. might be ambiguous'

        # parse the update docstring
        doc = NumpyDocString(docstring)

        # Expand bare 'Parameters' directive to include parameters that are
        # missing in the destination docstring, but are present in the source
        # docstring. Below this will automatically populate the destination
        # parameter info from that available from parent docstring without
        # overwriting anything.
        if 'Parameters' in self.directives:
            from_func = self.directives['Parameters']
            parsed_doc = docStringCache[from_func]
            source = get_param_dict(parsed_doc)
            dest = get_param_dict(doc)
            for pname in func.__code__.co_varnames:
                if pname not in dest and pname in source:
                    self.directives[f'Parameters[{pname}]'] = from_func
            
            #print(self.directives)

        # parse directives and insert new text
        doc = self.insert(func, doc)

        # remove omitted sections / parameters
        self.get_remove(self.from_func)

        # write the new docstring
        if (self.to_sub or self.directives):
            # NOTE: the string computed be =low will not be indented as is the
            # case with docstrings that are directly defined in the source at
            # function / class definition.
            func.__doc__ = str(doc)
        else:
            wrn.warn(
                f'{self.__class__.__name__} did not alter docstring for {func}.'
            )

        return func

    # def sub(self, docstring):
    #     # avoid circular import :|
    #     from recipes.string import sub

    #     self.to_sub.update(get_subs(docstring, self.from_func))
    #     return sub(docstring, self.to_sub)

    def insert(self, func, doc):

        for directive, ifunc in self.directives.items():
            if isinstance(ifunc, type):
                ifunc = ifunc.__init__

            # get parsed docstring (NumpyDocString) from cache (or create it
            # if needed)
            if ifunc.__doc__ is None:
                wrn.warn(f'No docstring available for {ifunc}. Skipping.')
                continue

            directive = Directive.parse(directive)
            _, section, key, _, rename, _ = directive
            new = directive.get_sub(ifunc)
            if section in LISTED_SECTIONS:
                # read the incoming parameter(s) and edit the parameter list of
                # the decorated function docstring
                new = doc._parse_param_list(new)
                if section == 'Parameters':
                    # find position of new parameter and insert it in the list
                    par_names = func.__code__.co_varnames
                    part = doc[section]
                    # if rename or key not specified, populate automatically for
                    # parameters that are missing in the destination docstring
                    if not rename and not key:
                        continue

                    i = par_names.index(rename or key) - isinstance(func, type)
                    doc[section] = part[:i] + new + part[i:]
                else:
                    doc[section].extend(new)
            else:
                # warn if we are about to overwrite things. This is probably
                # unintentional
                for line in doc[section]:
                    if line:
                        wrn.warn(f'You are overwriting the {section} section.')
                        break
                doc[section] = new.splitlines()
        return doc

    def get_remove(self, from_func):
        for directive in self.to_omit:
            directive = Directive.parse(directive)
            to_omit = directive.get_sub(from_func)
            self.to_sub[to_omit] = ''
