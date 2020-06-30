#!/usr/bin/env python

import json
import os, os.path

def key_paths(d):
    def helper(path, x):
        if isinstance(x, dict):
            for k, v in x.items():
                for ret in helper(path + [k], v):
                    yield ret
        elif isinstance(x, list):
            for i, item in enumerate(x):
                for ret in helper(path + [i], item):
                    yield ret
        else:
            yield path
    return helper([], d)

def line_iter(f):
    for line in f:
        yield json.loads(line)

def coll_iter(f, coll_key):
    data = json.load(f)
    for obj in data[coll_key]:
        yield obj

def dropkey_iter(f):
    data = json.load(f)
    for obj in (data.values() if isinstance(data, dict) else data):
        yield obj

def gather_key_map(iterator):
    key_map = {}
    for d in iterator:
        for path in key_paths(d):
            key_map[tuple(path)] = True
    return key_map

def path_join(path, sep='.'):
    return sep.join(str(k) for k in path)

def key_map_to_list(key_map, dummy_jq=False, no_duplicate_accessors=False):
    # We convert to strings *after* sorting so that array indices come out
    # in the correct order.
    def make_jq_selector(k):
        components = [("[{}]".format(c) if str(c).isdigit() else c) for c in k]
        sel = {"jq": ("." + path_join(components)), "args": {}}
        return sel
    
    if dummy_jq:
        make_keypath = (lambda k: path_join(k)) if not dummy_jq or not no_duplicate_accessors else lambda _: None
        return [(path_join(k, '_'), make_keypath(k), make_jq_selector(k)) for k in sorted(key_map.keys())]
    else:
        return [(path_join(k, '_'), path_join(k)) for k in sorted(key_map.keys())]

def make_outline(json_file, each_line, collection_key, drop_root_keys=False, dummy_jq=False, no_duplicate_accessors=False):
    if each_line:
        iterator = line_iter(json_file)
    elif collection_key:
        iterator = coll_iter(json_file, collection_key)
    else:
        iterator = dropkey_iter(json_file)

    key_map = gather_key_map(iterator)
    outline = {'map': key_map_to_list(key_map, dummy_jq, no_duplicate_accessors)}
    if collection_key:
        outline['collection'] = collection_key
    if drop_root_keys:
        outline['dropRootKeys'] = True
    if dummy_jq:
        outline["pre-processing"] = "."
        outline["post-processing"] = "."
    return outline

def init_parser():
    import argparse
    parser = argparse.ArgumentParser(description="Generate an outline file for json2csv.py")
    parser.add_argument('json_file', type=argparse.FileType('r'),
                        help="Path to JSON data file to analyze")
    parser.add_argument('-o', '--output-file', type=str, default=None,
                        help="Path to outline file to output")
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-e', '--each-line', action="store_true",
                       help="Process each line of JSON file separately")
    group.add_argument('-c', '--collection', type=str, default=None,
                       help="Key in JSON of array to process", metavar="KEY")
    group.add_argument('-d', '--dropRootKeys', action="store_true",
                       help="Process only values of a JSON file that has a dictionary as the root")
    
    parser.add_argument('-p', '--jq-processing', '--processing', '--jq', action="store_true",
                       help="Include JQ processing fields for accessors. Remember that using JQ commands instead of accessors significantly decreases performance")
    parser.add_argument('--no-duplicate-accessors', '--no-duplicates', action="store_true",
                       help="When used with JQ processing fields, it will remove accessors that jq covers")
    return parser

def main():
    parser = init_parser()
    args = parser.parse_args()
    outline = make_outline(args.json_file, args.each_line, args.collection, args.dropRootKeys, args.jq_processing, args.no_duplicate_accessors)
    outfile = args.output_file
    if outfile is None:
        fileName, fileExtension = os.path.splitext(args.json_file.name)
        outfile = fileName + '.outline.json'

    with open(outfile, 'w') as f:
        json.dump(outline, f, indent=2, sort_keys=True)
    if args.jq_processing:
        print("NOTE: You chose to enable jq-processing. Remember you have to nullify default accessors "
            "when you want JQ selectors to be applied. If you do not set "
            "default accessors to null, the JQ selector will not be applied, "
            "due to performance issue when repeatedly calling JQ.")
        if args.no_duplicate_accessors:
            print("...\nWARNING: are you sure you want to remove all default accessors ? "
                "(It will dramatically reduce the processing speed of the conversion. "
                "It should only be used for debug purpose or to learn how to create an outline file.)")

if __name__ == '__main__':
    main()
