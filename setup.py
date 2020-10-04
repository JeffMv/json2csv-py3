from pip.req import parse_requirements
from setuptools import setup
import uuid

# What packages are optional?
EXTRAS = {
    'comments': ['jsmin'],
    'jq': ['pyjq'],
}

setup(
        name='json2csv',
        version='0.2',
        modules=['json2csv'],
        scripts=['json2csv.py'],
        url='https://github.com/evidens/json2csv',
        license='MIT License',
        author='evidens',
        author_email='',
        description='Converts JSON files to CSV (pulling data from nested structures). Useful for Mongo data. Original author: evidens. New features by @JeffMv (GitHub). @JeffreyMvutu (Twitter)',
        install_requires= [str(ir.req) for ir in parse_requirements('requirements.txt', session=uuid.uuid1())],
        extras_require=EXTRAS,
)
