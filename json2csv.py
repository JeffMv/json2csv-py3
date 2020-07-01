#!/usr/bin/env python

try:
    import unicodecsv as csv
except ImportError:
    import csv

import json
import operator
import os
import logging

from collections import OrderedDict
from functools import reduce

try:
    from jsmin import jsmin
except ModuleNotFoundError:
    print('jsmin is not installed. Hence comments in outline file are disabled. Run "pip install jsmin" to install it')
    jsmin = lambda x: x

try:
    import pyjq as jqp  # jq-processor
except ModuleNotFoundError:
    jqp = None


__version__ = "0.2.1.2"

logging.basicConfig(level=logging.WARNING)

class Json2Csv(object):
    """Process a JSON object to a CSV file"""
    collection = None
    root_array = False

    # Better for single-nested dictionaries
    SEP_CHAR = ', '
    KEY_VAL_CHAR = ': '
    DICT_SEP_CHAR = '\r'
    DICT_OPEN = ''
    DICT_CLOSE = ''

    # Better for deep-nested dictionaries
    # SEP_CHAR = ', '
    # KEY_VAL_CHAR = ': '
    # DICT_SEP_CHAR = '; '
    # DICT_OPEN = '{ '
    # DICT_CLOSE = '} '

    def __init__(self, outline):
        self.rows = []

        if not isinstance(outline, dict):
            raise ValueError('You must pass in an outline for JSON2CSV to follow')
        elif 'map' not in outline or len(outline['map']) < 1:
            raise ValueError('You must specify at least one value for "map"')

        self.preprocessing = outline.get('pre-processing', None)
        self.preprocessing = self._optimized_jq_selector(self.preprocessing)
        self.postprocessing = outline.get('post-processing', None)
        self.postprocessing = self._optimized_jq_selector(self.postprocessing)
        
        key_map = OrderedDict()
        key_processing_map = OrderedDict()
        for header, key, *others in outline['map']:
            assert key or (others is not None and len(others) > 0), "Should either use keypaths or use JQ processing to get a value"
            splits = key.split('.') if key else []
            splits = [int(s) if s.isdigit() else s for s in splits]
            key_map[header] = splits
            ## expecting outline["map"]: [ ..., ["key", "keypath.to.value", {"jq": ".", "args": {"a": "abc", "b": 456}}], ... ]
            custom_processing = others[0] if len(others) > 0 else None
            key_processing_map[header] = custom_processing

        self.key_map = key_map
        self.key_processing_map = key_processing_map
        if 'collection' in outline:
            self.collection = outline['collection']
        elif 'dropRootKeys' in outline:
            self.root_array = True
    
    def _optimized_jq_selector(self, selector):
        """nullifies if the command is the identity. Against performance issue.
        """
        cmd = (selector if selector else ".").strip()
        cmd = cmd if cmd != "." else None
        return cmd

    def load(self, json_file):
        data = json.load(json_file)
        data = self._target_data(data)
        # performance: avoid calling jq if identity
        data = jqp.one(self.preprocessing, data) if jqp and self.preprocessing else data
        
        self.process_each(data)
        
        # performance: avoid calling jq if identity
        self.rows = jqp.one(self.postprocessing, self.rows) if jqp and self.postprocessing else self.rows
    
    def _target_data(self, data):
        if self.collection and self.collection in data:
            data = data[self.collection]
        elif self.root_array:
            data = list(data.values()) if isinstance(data, dict) else data
        return data

    def process_each(self, data):
        """Process each item of a json-loaded dict
        """
        # data = self._target_data(data)  # already done in self.load(..)
        
        for d in data:
            logging.info(d)
            self.rows.append(self.process_row(d))

    def process_row(self, item):
        """Process a row of json data against the key map
        """
        row = {}

        for header, keys in self.key_map.items():
            try:
                if keys:
                    row[header] = reduce(operator.getitem, keys, item)
                else:
                    row[header] = None
            except (KeyError, IndexError, TypeError):
                row[header] = None

        ### Design choice: jq scripts DO NOT override default accessors
        ### because accessing using JQ dramatically decreases performance
        for header, data in self.key_processing_map.items():
            if jqp and row[header] is None and data is not None:  # row[header] is None:
                try:
                    selector, args = data.get('jq'), data.get('args', {})
                    selector = self._optimized_jq_selector(selector)
                    if selector:
                        try:
                            tmp = jqp.one(selector, item, vars=args)
                        except Exception as err:
                            logging.warning("Error on key '{}' with JQ '{}'. Error text: {}".format(header, selector, err))
                            tmp = None
                        
                        row[header] = tmp
                except (KeyError, IndexError, TypeError, ValueError):
                    pass

        return row

    def make_strings(self):
        str_rows = []
        for row in self.rows:
            str_rows.append({k: self.make_string(val)
                             for k, val in list(row.items())})
        return str_rows

    def make_string(self, item):
        if isinstance(item, list) or isinstance(item, set) or isinstance(item, tuple):
            return self.SEP_CHAR.join([self.make_string(subitem) for subitem in item])
        elif isinstance(item, dict):
            return self.DICT_OPEN + self.DICT_SEP_CHAR.join([self.KEY_VAL_CHAR.join([k, self.make_string(val)]) for k, val in list(item.items())]) + self.DICT_CLOSE
        else:
            return str(item)

    def write_csv(self, filename='output.csv', make_strings=False, write_header=True, delimiter=","):
        """Write the processed rows to the given filename
        """
        if (len(self.rows) <= 0):
            raise AttributeError('No rows were loaded')
        if make_strings:
            out = self.make_strings()
        else:
            out = self.rows
        with open(filename, 'wb+') as f:
            writer = csv.DictWriter(f, list(self.key_map.keys()), delimiter=delimiter)
            if write_header:
                writer.writeheader()
            writer.writerows(out)


class MultiLineJson2Csv(Json2Csv):
    """
    Note: No pre-processing or post-processing
    Conceptually, multiline JSON cannot use the notion of preprocessing a whole
    input file since each line is treated one after the other in sequence,
    without ever seeing the full file.
    """
    def load(self, json_file):
        self.process_each(json_file)

    def process_each(self, data, collection=None):
        """Load each line of an iterable collection (ie. file)"""
        for line in data:
            d = json.loads(line)
            if self.collection in d:
                d = d[self.collection]
            self.rows.append(self.process_row(d))


def init_parser():
    import argparse
    parser = argparse.ArgumentParser(description="Converts JSON to CSV")
    parser.add_argument('json_file', type=argparse.FileType('r'),
                        help="Path to JSON data file to load")
    parser.add_argument('key_map', type=argparse.FileType('r'),
                        help="File containing JSON key-mapping file to load")
    parser.add_argument('-e', '--each-line', action="store_true", default=False,
                        help="Process each line of JSON file separately")
    parser.add_argument('-o', '--output-csv', type=str, default=None,
                        help="Path to csv file to output")
    parser.add_argument('--delimiter', '-d', '--csv-delimiter', type=str, default=",",
                        help="1 character CSV delimiter. Default is comma ','. You may also output in tsv with '\\t'")
    parser.add_argument(
        '--strings', help="Convert lists, sets, and dictionaries fully to comma-separated strings.", action="store_true", default=True)
    parser.add_argument('--no-header', action="store_true",
                        help="Process each line of JSON file separately")
    parser.add_argument('--verbose', type=int, default=0, help="Level of logs")
    
    return parser

if __name__ == '__main__':
    parser = init_parser()
    args = parser.parse_args()
    
    # levels_of_log = {0:logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    # print(f"verbose: {args.verbose}, level: ...")
    # logging.basicConfig(level=levels_of_log[args.verbose])  # not working if alreary made earlier
    
    special_inputs_map = {"\\t":"\t", "\\n":"\n"}
    csv_delimiter = special_inputs_map.get(args.delimiter, args.delimiter)
    
    key_map = json.loads(jsmin(args.key_map.read()))
    loader = None
    if args.each_line:
        loader = MultiLineJson2Csv(key_map)
    else:
        loader = Json2Csv(key_map)

    loader.load(args.json_file)

    outfile = args.output_csv
    if outfile is None:
        fileName, fileExtension = os.path.splitext(args.json_file.name)
        outfile = fileName + '.csv'

    loader.write_csv(filename=outfile, make_strings=args.strings, write_header=not args.no_header, delimiter=csv_delimiter)
