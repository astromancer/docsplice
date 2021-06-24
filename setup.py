from setuptools import setup, find_packages

setup(packages=find_packages(exclude=['tests', "tests.*"]),
    use_scm_version=True,
    include_package_data=True)
