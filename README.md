# Anno-Class
A tool for combining multiple image processing and classification method and algorithms image collection classification problem.

## Setup
### Prerequisites:
- Python 3.10
### Install:
1. Download the source code
    - As zip and unzip
    - Use git close

In terminal:

2. Navigate to directory where the source is saved
3. (Recommended) Create venv
4. Install required libraries: `pip install -r requirements.txt`
5. Launch app: `python anno-class.py`

For additional commands use help: `python anno-class.py -h`

## Usage
There are example agents provided in `Plugins` folder. It is encouraged to create more and added them to our growing list of annotation and classification agents.

### Creating an Agent
Each annotation agent has to implement `AnnotationPluginCore` interface as seen in example agents. This provides a bridge between created agent and application. 
Each classification agent has to implement `FilterPluginCore` interface as seen in the example agents.

Yaml file must be filled as in the examples providing with required information. 

```yaml
runtime:
  main: "FilterA.py"
```
Section denotes what is the entrypoint of the agent.
```yaml
annotation_agent: true
```
If **annotation agent** is being created this should be set as ***true***, if **classification agent** - ***false***.

For classification agents:
```yaml
configurations:
  - name: "evaluation"
    vtype: "string"
```
Shows what configurations can classification agent expect to be passed into it.

```yaml
required-agents:
  - alias: "agent-alias"
```
List of required annotation agents for classifier to work.

For annotation agents:
```yaml
variables:
  - name: "red_perc"
    vtype: "double"
```
Sets variable names and types that will be saved into database. 

### Using built in explorer
First, images should be added to the database by using `open folder` button which scans a selected directory for images.

`Annotate` - annotates selected images or all images if none are selected by selected agents.

`Filter/Classify` - see installed filters. By clicking `Upload filter config` you can select json with desired filter configuration as seen in `blue_perc.json` example filter configuration.

### Using command lines
It is possible to use this tool with command lines providing it with configuration json.