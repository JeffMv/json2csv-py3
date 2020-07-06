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
# Details about JQ: https://stedolan.github.io/jq/download/
```


## Usage



Basic (convert from a JSON file to a CSV file in same path):

```bash
python json2csv.py /path/to/json_file.json -k /path/to/outline_file.json
# simply add other input filepaths to convert multiple files at a time
```

Specify CSV file

```bash
python json2csv.py /path/to/json_file.json -k /path/to/outline_file.json -o /some/other/file.csv
```

Output without header

```bash
python json2csv.py /path/to/json_file.json -k /path/to/outline_file.json --no-header
```



For MongoDB (multiple JSON objects per file, which is non-standard JSON):

```bash
python json2csv.py --each-line /path/to/json_file.json -k /path/to/outline_file.json
```

Using a different CSV delimiter for the output.

```bash
python json2csv.py /path/to/json_file.json -k /path/to/outline_file.json --csv-delimiter ';'
# you can also output in *.tsv with '\t' as the delimiter
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

- `"pre-processing"`: a jq script that will be given the array containing the input data as its input. It must output the exact dictionary or array as what would be expected. It is executed right after the `"collection"` attribute (or `"dropRootKeys`) has been applied. Hence, you are expected to get as input an array of dictionaries, and should output an array of dictionaries.  Executed before the `"map"` elements else in the outline. 
  Executed only once.

- `"post-processing"`: a jq script that will be given the output rows of the `"map"` as its input. Must output an array of dictionary. It is executed after everything else in the outline. Executed only once.

- `"map-processing"`: **executed for each row**, being passed as `input` the current item and passed as jq arguments (`jq --arg varname value`) the fields generated up until now by the outline for this row.
  It is **only** responsible for outputting the key-value pairs you want **to add / update**. This means you do not have to worry about kipping the root element around or any other key-value pairs. You can even output only `{row: $__row__}` and this will add the row's number as a column in the output CSV.
  
  **[PERFORMANCE HIT]** Since a jq process is launched and executed for each row, it can make a huge difference in completion time, especially with >= 1000 elements.
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



#### Context while running JQ commands

You can provide a general context for constants by setting the following key in the root of the outline file:

```json
{
  ...,
  "context-constants": {"contextualVar1": "value"},
  ...
}
```


#### Handling `null`, `None` and empty strings

You can provide a mapping for special values. Those will be applied *after* the *post-processing* step.

For instance, in the following example, `None` (`null`) values will be replaced by the empty string, while empty strings will be replaced with `"-"`. The replacement of values is considered simultaneous, which is why `null` values won't be replaced with `"-"`.

```json
{
  ...,
  "special-values-mapping": {"null": "", "empty": "-"},
  ...
}
```


## Generating outline files

To automatically generate an outline file from a json file:

```bash
python gen_outline.py --collection nodes /path/to/the.json
```

This will generate an outline file with the union of all keys in the json
collection at `/path/to/the.outline.json`.  You can specify the output file
with the `-o` option, as above.

If your json file's root is a dictionary and you want to drop out the root keys and treat the values as an array, then you can use the option `--drop-root-keys` instead of `--collection`.

`--drop-root-keys` works just like the [JQ](https://stedolan.github.io/jq/) command `map(.)` on a dictionary.


## Unquoting strings

To remove quotation marks from strings in nested data types:

```bash
python json2csv.py /path/to/json_file.json /path/to/outline_file.json --strings
```

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
  - [x] Document usage of JQ filters
