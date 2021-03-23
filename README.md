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
  // this is a comment. Install the extra dependencies to use them.

  // a map of accessors
  "map": [
    ["authorName", "source.author"], // takes the path '{"source": "author": ...}}' from the JSON and creates a column named "authorName" in the CSV

    ["messageContent", "message.original"],

    ["authorFirstName", "firstName"] // an accessor created dynamically using JQ and the 'pre-processing' field
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

  // When using JQ processing, it is possible to run custom JQ scripts.
  // Using pre-processing, you access the entire data collection as it was
  // after the collection key is applied.
  // Any key you create in the data will be made available for use with accessors, and the reverse applies for deleted keys.
  "pre-processing": "map(. + {firstName: (.source.author|split(\" \")[0])})",
  
  // post-processing is performed after the 'map' accessors are applied.
  // Make sure you preserve every previous data by using the "." in JQ.
  // You may still add/delete fields in this step, which will result in
  // columns being created/deleted in the resulting CSV
  "post-processing": "map(. + {description: \"Message has \(.messageContent|length) characters.\"})"
}
```

### JQ Processing

You can use JQ scripts to process the JSON while it is being converted, if you have all the requirements ([`jq`](https://stedolan.github.io/jq/manual) and `pyjq`).

There are 3 main places you can place your scripts:

- `"pre-processing"`: a jq script that will be given the array containing the input data as its input. It must output the exact dictionary or array as what would be expected. It is executed right after the `"collection"` attribute (or `"dropRootKeys`) has been applied. Hence, you are expected to get as input an array of dictionaries, and should output an array of dictionaries.  Executed before the `"map"` elements else in the outline. 
  Executed only once.

  Note: using pre-processing, you may want to *create new fields* that you want to also have in the output file. In that case, you would add entries with their path to the `map` array, in whichever position you intend to have the corresponding CSV column.

- `"post-processing"`: a jq script that will be given the output rows of the `"map"` as its input. Must output an array of dictionaries. It is executed after everything else in the outline. Executed only once.
  Note: any *key* you add/remove from the post-processing will be added/removed as a column in the CSV output. And any *row* you delete will not be written to the CSV. This allows you to have some row filtering conditions in place. Conversely, you may add rows in there (though this use case does not make sense generally).

- `"map-processing"`: **executed for each row**, being passed as `input` the current item and passed as jq arguments (`jq --arg varname value`) the fields generated up until now by the outline for this row.
  It is **only** responsible for outputting the key-value pairs you want **to add / update**. This means you do not have to worry about kipping the root element around or any other key-value pairs. You can even output only `{row: $__row__}` and this will add the row's number as a column in the output CSV.
  
  **[PERFORMANCE HIT]** Since a jq process is launched and executed for each row, it can make a huge difference in completion time, especially with >= 1000 elements.
  **Note**: Only use it if it is really impossible to achieve what you need with either pre-/post-processing.
Remember that **most of the time**, you can use the combination of `pre-processing` to lay some variables with a `map` and then use `post-processing` to use these variables. Then you can ensure you delete temporary columns with jq's `del(.foo)` so that they don't show up in the CSV file.
  The outline file would look like:
  
  ```json
  {
    "...": "...",
    "pre-processing": "map(. + {tempKey: value})",
    "post-processing": "map(. + { finalKey: (.tempKey | dosomething) } | del(.tempKey))",
    "map": [...]
  }
  ```


You may also use an array for readability when constructing the JQ scripts. The array will be joined as if it were only one single string. This behaviour allows for more flexibility and ease of conversion.

```json
  "pre-processing": [
    ".",
    "| map( . ",
      "  | + {contryCode: ($aux.countryCodes[.countryName | ascii_downcase])}",
    "| . )"
  ],
```

Note: You can pass `null` or `"."` as a JQ script to avoid launching a JQ process.



#### Context while running JQ commands

You can provide a general context for constants by setting the `context-constants` key in the root of the outline file and name the root of the context `aux` (*aux* as in auxiliary inputs):

```json
{
  ...,
  "context-constants": {"aux": {"constant1": "value", "CONSTANT2": 12}},
  ...
}
```

which you can use in JQ processing fields as the following example:

```json
{
  ...,
  "pre-processing": "map( . + {externalField: $aux.constant1} )",
  ...,
  "map":[
  	"anotherNameIfYouWant",
  	"externalField"
  ]
}
```

For a more elaborated example, you could use this context to pass in some useful constants that your data file is unaware of, for instance a country map to convert country names to country ISO codes and add that country ISO code as a column in your CSV file. (This example also makes use of the `ascii_downcase` JQ filter that converts *ascii* characters to lowercase).

```json
{
  ...,
  "context-constants": {"aux": {"countryCodes":{"united states":"us","france":"fr", "...":"..."}}},
  "pre-processing": "map( . + {contryCode: ($aux.countryCodes[.countryName | ascii_downcase])} )",
  "map": [
    ...
    [
      "country",
      "countryName"
    ],
    [
      "countryIso",
      "countryCode"
    ]
    ...
  ],
  ...
}
```



**Filepath in context**

Sometimes when processing multiple files with the same outline file, you might want to use the current JSON file's path in a JQ filter processing. To do that, there is an auxiliary value of `_file_` in the `context-constants` you can access as `$aux._file_` in your JQ filters.



#### Handling special values like `null`, `None`, `true`, `false` and empty strings

Some values do not have a unique representation accross languages and file types. You may want to provide your own mappings to make the CSV compatible with other tools/workflow you have.

Because mappings are made between JSON and Python, types are converted. Therefore, values such as `null`, `true` and `false` are by default converted to Python types, which then will be printed using `str(value)`. Therefore, in order to avoid having `None`, `True`/`False` (capitalized), a mapping has to be made. That's the purpose of the `"special-values-mapping": {...}` entry.

You can provide a mapping such special values. Those will be applied *after* the *post-processing* step.

For instance, in the following example, `null` JSON values (or rather `None` values generated during the processing) will be replaced by the empty string, while empty strings will be replaced with `"-"`. The replacement of values is considered *simultaneous*, which is why `null` values won't be replaced with `"-"`. 
This will also replace booleans `True` with the integer `1` and booleans `False` with the integer `0` (Note that it **won't** replace textual values `"true"` or `"True"`, so you're safe on that end). 

```json
{
  ...,
  "special-values-mapping": {"null": "", "empty": "-", "true": 1, "false": 0},
  ...
}
```

Note: even though the keys `null` and such are strings, they only indicate which special value to replace. You should not expect to add an unsupported value for it to be converted, neither should you expect `"null"` (string) and such to be replaced during the process. If you want such replacement, you may either pre-processs your JSON input through a `"pre-processing"` JQ script or through the use of another program of your choice (to replace any value before feeding it to this program). You can also aim to post-process the CSV output with a script or library like [`pandas`](https://pandas.pydata.org/) and its [`read_csv`](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.read_csv.html) / `write_csv`

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



## Roadmap

- [X] Ability to use JQ filters to further control the CSV output
  - [X] Example JQ filters using gen_outline.py
  - [x] Document usage of JQ filters
  - [x] Enable the use of constants external to the JSON file
  - [x] Add a way to get the filename of the JSON file in JQ filters
