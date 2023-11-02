# DocSplice

> Docstring splicing for python functions 🧬

<!-- 
TODO
[![Build Status](https://travis-ci.com/astromancer/docsplice.svg?branch=master)](https://travis-ci.com/astromancer/docsplice)
[![Documentation Status](https://readthedocs.org/projects/docsplice/badge/?version=latest)](https://docsplice.readthedocs.io/en/latest/?badge=latest)
[![PyPI](https://img.shields.io/pypi/v/docsplice.svg)](https://pypi.org/project/docsplice)
[![GitHub](https://img.shields.io/github/license/astromancer/docsplice.svg?color=blue)](https://docsplice.readthedocs.io/en/latest/license.html)
 -->

This project allows you to splice docstrings for python functions in a
convenient way using a functional decorator. This enables you to more easily
create consistent documentation for your API without needing to duplicate
docstring sections for functions that have the same parameter descriptions or
other related content. This will ease the maintenance burden for your package
documentation since the content of your function or class documentation reside
in a single location in the source code, instead of being duplicated within each
function body.


# Install

  ```shell
  pip install docsplice
  ```

# Use

<!-- ### Duplicating Parameters from a single source function: -->



### Pulling parameters from multiple sources

```python
import docsplice as doc


def fun1(a):
    """
    Do something with a number.

    Parameters
    ----------
    a : int
        The number.
    """
    
def fun2(b=0):
    """
    Another function that does something with an integer.
    
    Parameters
    ----------
    b : int, optional
        Another number! By default 0.
    """

@doc.splice({'Parameters[a]': fun1,
             'Parameters[b] as n=7': fun2}) 
def combined(a, n=7):
    """
    Some profound computation. Parameter descriptions follow:
    """
```  

The `Parameters` section in the docstring for `combined` has been created by the
`splice` decorator. Inspecting the object in an interactive terminal reveals 
that the docstring has been filled:

```python
combined??
```
```
Signature: combined(a, n=7)
Docstring:
Some profound computation. Parameter descriptions follow:

Parameters
----------
a : int
    The number.
n : int, optional
    Another number! By default 7.
Source:   
@doc.splice({'Parameters[a]': fun1,
             'Parameters[b] as n=7': fun2}) 
def combined(a, n=7):
    """
    Some profound computation. Parameter descriptions follow:
    """
```

<!-- For more examples see [Documentation]() -->

<!-- # Documentation -->

# Test

The [`test suite`](./tests/test_splice.py) contains further examples of how
`DocSplice` can be used.  Testing is done with `pytest`:

```shell
pytest docsplice
```

# Contribute
Contributions are welcome!

1. [Fork it!](https://github.com/astromancer/docsplice/fork>)
2. Create your feature branch\
    ``git checkout -b feature/rad``
3. Commit your changes\
    ``git commit -am 'Add something rad'``
4. Push to the branch\
    ``git push origin feature/rad``
5. Create a new Pull Request

# Contact

* e-mail: hannes@saao.ac.za

<!-- ### Third party libraries
 * see [LIBRARIES](https://github.com/username/sw-name/blob/master/LIBRARIES.md) files -->

# License

* see [LICENSE](https://github.com/astromancer/docsplice/blob/master/LICENSE.txt)

<!-- 
# Version
This project uses a [semantic versioning](https://semver.org/) scheme. The 
latest version is
* 0.0.1
 -->
