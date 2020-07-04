#!/usr/bin/env python

try:
    import unicodecsv as csv
except ImportError:
    import csv

import json
import operator
import os
import logging
import datetime

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


__version__ = "0.2.2.0"

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
        self.mapprocessing = outline.get('map-processing', None)
        self.mapprocessing = self._optimized_jq_selector(self.mapprocessing)
        self.postprocessing = outline.get('post-processing', None)
        self.postprocessing = self._optimized_jq_selector(self.postprocessing)
        self.context_constants = outline.get('context-constants', {})
        self.special_values_mapping = outline.get('special-values-mapping', {})
        
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
        self.header_keys = OrderedDict(self.key_map)
        self.key_processing_map = key_processing_map
        if 'collection' in outline:
            self.collection = outline['collection']
        elif 'dropRootKeys' in outline:
            self.root_array = True
    
    def _optimized_jq_selector(self, selector):
        """nullifies if the command is the identity. Against performance issue.
        """
        ### allow multiline JQ commands (for readability) through the use of
        ### arrays
        if isinstance(selector, list):
            selector = "".join(selector)
        
        cmd = (selector if selector else ".").strip()
        cmd = cmd if cmd != "." else None
        return cmd

    def load(self, json_file):
        data = json.load(json_file)
        
        data = self._target_data(data)
        
        # performance: avoid calling jq if identity
        data = jqp.one(self.preprocessing, data, vars=self.context_constants) if jqp and self.preprocessing else data
        
        self.process_each(data)
        
        # performance: avoid calling jq if identity
        if jqp and self.postprocessing:
            self.rows = jqp.one(self.postprocessing, self.rows, vars=self.context_constants)
        
        self._update_header_keys(self.rows)
        # special values
        vnone = self.special_values_mapping.get("null", "")
        vempty = self.special_values_mapping.get("empty", "")
        self.rows = self._replace_nulls(self.rows, vnone, vempty)
    
    
    def _update_header_keys(self, data_rows):
        ## making sure all the keys that were generated dynamically are
        ## actually added to the CSV
        ## Ensure the keys that were removed by a dynamic processing step like
        ## JQ are also removed. This can allow the user to have temporary
        ## helper fields and clean them in post-processing
        every_keys = OrderedDict()
        on_single_row = lambda acc, row_dict: every_keys.update({key:None for key in row_dict.keys()}) or every_keys
        _ = reduce(on_single_row, data_rows, every_keys)
        
        initial_keys = set(self.header_keys.keys())
        found_keys = set(every_keys.keys())  # keys found in rows. we will see those
        
        # keys_to_add = set(found_keys) - set(initial_keys)
        keys_to_remove = set(initial_keys) - set(found_keys)
        # difference_symmetrique = keys_to_add.union(keys_to_remove)
        
        # only adds new keys at the end without messing the existing order
        self.header_keys.update(every_keys)
        
        _ = [self.header_keys.pop(key) for key in keys_to_remove]
        pass
    
    def _replace_nulls(self, data, value_for_none=None, value_for_empty=None):
        value_for_none = value_for_none if value_for_none is not None else ""
        value_for_empty = value_for_empty if value_for_empty is not None else ""
        
        replace = lambda x: x if (x is not None and x != "") else (value_for_none if x is None else value_for_empty)
        transformed = list(map(lambda row: {key: replace(value) for key, value in row.items()}, data))
        return transformed
    
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
        
        for i, d in enumerate(data):
            logging.info(d)
            self.rows.append(self.process_row(d, i))

    def process_row(self, item, index):
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

        
        ######   Map-processing   row-wise   ######
        ### Preferred way to process using JQ (much much more efficient
        ### than field-wise selectors).
        
        # to make custom generated fields available in JQ as $myvar
        jq_params = row.copy()
        jq_params.update(self.context_constants)
        jq_params.update({'__row__': index})
        if self.mapprocessing:
            try:
                computed = jqp.one(self.mapprocessing, item, vars=jq_params)
                row.update(computed)
                self.header_keys.update({key: None for key in computed.keys()})
            except Exception as err:
                logging.warning(" JQ Error with map-processing JQ script '{}'. Error text: {}".format(self.mapprocessing, err))
        
        
        ######   Individual field-wise JQ selectors   ######
        ### Note: The user should rely mostly on row-wise map-processing
        ###       instead of this field-wise calls. This is left here for
        ###       historical reason since the code was still working.
        ###
        ### Design choice: jq scripts DO NOT override default accessors
        ### because accessing using JQ *dramatically* decreases performance
        ### for every call. It also means it is far better to group every JQ
        ### calls unless there is no other choice
        
        for header, data in self.key_processing_map.items():
            if jqp and row[header] is None and data is not None:  # row[header] is None:
                try:
                    selector = data.get('jq')
                    args = data.get('args', {})
                    ## NOTE: this causes more variables to be available than
                    ## should be. However it's fine we let user be smart about
                    ## their selector scripts. Internals should not be abused.
                    ## Avoid performance hits
                    jq_params.update(args)
                    
                    selector = self._optimized_jq_selector(selector)
                    if selector:
                        try:
                            tmp = jqp.one(selector, item, vars=jq_params)
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
            header_columns = list(self.header_keys.keys())
            writer = csv.DictWriter(f, header_columns, delimiter=delimiter)
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
        for i, line in enumerate(data):
            d = json.loads(line)
            if self.collection in d:
                d = d[self.collection]
            self.rows.append(self.process_row(d, i))


def get_filepath_formatted_from_filepath(template, filepath):
    folder = os.path.dirname(filepath)
    basename = os.path.basename(filepath)
    base, ext = os.path.splitext(basename)
    ext = ext[1:]
    fp = filepath
    output = template.format(basename=basename, path=filepath,
                             base=base, ext=ext,
                             directory=folder, folder=folder, dirname=folder)
    return output


def init_parser():
    import argparse
    parser = argparse.ArgumentParser(description="Converts JSON to CSV")
    
    mandatory_group = parser.add_argument_group("Mandatory arguments")
    mandatory_group.add_argument('input_json_files', nargs="+", default=[],
                        help="Path to other JSON data file to load")
    mandatory_group.add_argument('-k', '--key-map', type=argparse.FileType('r'),
                        dest="key_map", required=True,
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


def convert_json_to_csv(json_file, key_map, output_csv, no_header, make_strings, each_line, delimiter):
    """
    :param dict key_map:
    """
    special_inputs_map = {"\\t":"\t", "\\n":"\n"}
    csv_delimiter = special_inputs_map.get(delimiter, delimiter)
    
    try:
        loader = None
        if each_line:
            loader = MultiLineJson2Csv(key_map)
        else:
            loader = Json2Csv(key_map)

        loader.load(json_file)

        outfile = output_csv
        if outfile is None:
            fileName, fileExtension = os.path.splitext(json_file.name)
            outfile = fileName + '.csv'
        
        os.makedirs(os.path.dirname(outfile), exist_ok=True)

        loader.write_csv(filename=outfile, make_strings=make_strings, write_header=not no_header, delimiter=csv_delimiter)
    except Exception as err:
        print("Error while processing file {}: [{}] {}".format(json_file.name, type(err), err))
        raise err
    pass


if __name__ == '__main__':
    parser = init_parser()
    args = parser.parse_args()
    
    # levels_of_log = {0:logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    # print("verbose: {}, level: ...".format(args.verbose))
    # logging.basicConfig(level=levels_of_log[args.verbose])  # not working if alreary made earlier
        
    key_map_content = json.loads(jsmin(args.key_map.read()))
    
    output_paths = [get_filepath_formatted_from_filepath(args.output_csv, fp) for fp in args.input_json_files]
    assert len(set(output_paths)) == len(set(args.input_json_files)), "Mismatched number of input-output filepaths. Number of generated output paths must match number of input files to convert"
    
    for i, filepath in enumerate(args.input_json_files):
        output_filepath = output_paths[i]
        
        with open(filepath, "r") as fileobject:
            dt = datetime.datetime.today()
            s_time = "{:02}:{:02}:{:02}".format(dt.hour, dt.minute, dt.second)
            print("  {} / {} : {}  {}|  {}".format(i+1, len(args.input_json_files), fileobject.name, (("-> %s  "%output_filepath) if output_filepath else ""), s_time))
            convert_json_to_csv(fileobject, key_map_content, output_filepath, args.no_header, args.strings, args.each_line, args.delimiter)
    