# JSON2CSV

A converter to extract nested JSON data to CSV files.

Great tool for creating dataset files or intermediate constructs for importing to SQL databases.

Supports converting multi-line Mongo query results to a single CSV.



## Installation

```bash
git clone https://github.com/evidens/json2csv.git
cd json2csv
pip install -r requirements.txt
# for more functionnality, you may want to also install
pip install jsmin  # allows comments in the outline file. See below
pip install pyjq  # allows using JQ processing. You also need JQ on your system
```

## Usage



Basic (convert from a JSON file to a CSV file in same path):
```bash
python json2csv.py /path/to/json_file.json /path/to/outline_file.json
```

Specify CSV file
```bash
python json2csv.py /path/to/json_file.json /path/to/outline_file.json -o /some/other/file.csv
```

Output a CSV file without header
```bash
python json2csv.py /path/to/json_file.json /path/to/outline_file.json -o /some/other/file.csv --no-header
```

For custom CSV delimiter output:

```bash
python json2csv.py /path/to/json_file.json /path/to/outline_file.json --csv-delimiter ';'
# you can also output in *.tsv with '\t' as the delimiter
```

For MongoDB (multiple JSON objects per file, which is non-standard JSON):

```bash
python json2csv.py --each-line /path/to/json_file.json /path/to/outline_file.json
```

## Outline Format

For this JSON file:

```js
{
  "nodes": [
    {"source": {"author": "Someone"}, "message": {"original": "Hey!", "Revised": "Hey yo!"}},
    {"source": {"author": "Another"}, "message": {"original": "Howdy!", "Revised": "Howdy partner!"}},
    {"source": {"author": "Me too"}, "message": {"original": "Yo!", "Revised": "Yo, 'sup?"}}
  ]
}
```

Use this outline file:
```js
{
  "map": [
    ["author", "source.author"],
    ["message", "message.original"]
  ],
  "collection": "nodes"
}
```

If you have installed the extra dependancies, you will be able to use comments:

```js
{
  "map": [
    ["authorName", "source.author"],
    // this is a comment
    ["messageContent", "message.original"]
  ],
  //// "collection" is used when the JSON's root is a dictionary.
  //// You pass in the key that contains your data
  "collection": "nodes",

  //// When the root of the JSON is a dictionary but the root keys should be ignored.
  //// For instance in the following architecture
  //// {"12": {"productId": 12, "brand": "Apple"}, "13":{"productId": 13, "brand": Microsoft}}
  //// the root keys "12" and "13" are variable and you do not know them beforehand.
  //// To do that, you would drop them with the option
  // "dropRootKeys": true,

  // When using JQ processing, it is possible to run custom JQ scripts
  // Using pre-processing, you access the entire data collection as it was
  // after the collection key is applies
  "pre-processing": "map(. + {firstName: (.source.author|split(\" \")[0])})",
  // post-processing is performed after. You must NOT change the structure
  // unless you know what you are doing.
  "post-processing": "map(. + {description: \"Message has \(.messageContent|length) characters.\"})"
}
```

### JQ Processing

You can use JQ scripts to process the JSON while it is being converted, if you have all the requirements ([`jq`](https://stedolan.github.io/jq/manual) and `pyjq`).

There are 3 main places you can place your scripts:

- `"pre-processing"`: a jq script that will be given the array containing the input data as its input. It is executed before anything else in the outline. Executed only once.

- `"post-processing"`: a jq script that will be given the output rows of the outline as its input. It is executed after everything else in the outline. Executed only once.

- `"map-processing"`: **executed for each row**, being passed as `input` the current item and passed as jq arguments (`jq --arg varname value`) the fields generated up until now by the outline for this row.
  **[PERFORMANCE HIT]** Since a jq process is launched and executed for each row, it can make a huge difference in completion time.
  **Note**: Only use it if it is really impossible to achieve what you need with either pre-/post-processing.
  Remember that **most of the time**, you can use the combination of `pre-processing` to lay some variables with a `map` and then use `post-processing` to use these variables while ensuring you delete them with jq's `del(.foo)` so that they don't show up in the CSV file.
  The outline file would look like:

  ```json
  {
    "...": "...",
    "pre-processing": "map(. + {tempKey: value})",
    "post-processing": "map(. + { finalKey: (.tempKey | dosomething) } | del(.tempKey))",
    "map": [...]
  }
  ```



Note: You can pass `null` or `"."` as a JQ script to avoid launching a JQ process.



## Generating outline files

To automatically generate an outline file from a json file:

    python gen_outline.py --collection nodes /path/to/the.json

This will generate an outline file with the union of all keys in the json
collection at `/path/to/the.outline.json`.  You can specify the output file
with the `-o` option, as above.

## Unquoting strings

To remove quotation marks from strings in nested data types:

    python json2csv.py /path/to/json_file.json /path/to/outline_file.json --strings

This will modify field contents such that:

```js
{
  "sandwiches": ["ham", "turkey", "egg salad"],
  "toppings": {
    "cheese": ["cheddar", "swiss"],
    "spread": ["mustard", "mayonaise", "tapenade"]
    }
}
```

Is parsed into

|sandwiches            |toppings                                                       |
|:---------------------|:--------------------------------------------------------------|
|ham, turkey, egg salad|cheese: cheddar, swiss<br>spread: mustard, mayonaise, tapenade|

The class variables `SEP_CHAR`, `KEY_VAL_CHAR`, `DICT_SEP_CHAR`, `DICT_OPEN`, and `DICT_CLOSE` can be changed to modify the output formatting. For nested dictionaries, there are settings that have been commented out that work well. 


## Upcoming features

- [X] Ability to use JQ filters to further control the CSV output
  - [X] Example JQ filters using gen_outline.py
  - [ ] Document usage of JQ filters
