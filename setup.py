from pip.req import parse_requirements
from setuptools import setup
import uuid

# What packages are optional?
EXTRAS = {
    'comments': ['jsmin'],
    'jq': ['pyjq'],
}

setup(
        name='json2csv-py3',
        version='0.2.1',
        modules=['json2csv'],
        scripts=['json2csv.py'],
        url='https://github.com/JeffMv/json2csv-py3',
        license='MIT License',
        author='evidens',
        author_email='',
        description='Converts JSON files to CSV (pulling data from nested structures). Useful for Mongo data. Original author: evidens (https://github.com/evidens/json2csv). New features by @JeffMv (GitHub) - @JMMvutu (Twitter)',
        install_requires= [str(ir.req) for ir in parse_requirements('requirements.txt', session=uuid.uuid1())],
        extras_require=EXTRAS,
)
