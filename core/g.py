"""g stands for Globals.

This is a temporary module that plays the role of a singleton -- to implement
global variables used by the original AsciiDoc design. The globals should
disappear after finishing the refactoring."""

def init_globals(CONF_DIR, HELP_FILE, prog, asciidoc_ver):
    global app_file, app_dir, user_dir
    app_file = None             # This file's full path.
    app_dir = None              # This file's directory.
    user_dir = None             # ~/.asciidoc3

    global conf_dir, help_file
    conf_dir = CONF_DIR
    help_file = HELP_FILE

    global progname
    progname = prog             # asciidoc script basename without extension

    global asciidoc_version
    asciidoc_version = asciidoc_ver

    # Globals
    # -------
    from .document import Document
    global document
    document = Document()       # The document being processed.

    ##global document #, config, reader, writer, message
    ##config = Config()           # Configuration file reader.
    ##reader = Reader()           # Input stream line reader.
    ##writer = Writer()           # Output stream line writer.

    from .message import Message
    global message
    message = Message()         # Message functions.

    from .document import Paragraphs, Lists, DelimitedBlocks, Tables_OLD, Tables

    global paragraphs
    paragraphs = Paragraphs()   # Paragraph definitions.

    global lists
    lists = Lists()             # List definitions.

    global blocks
    blocks = DelimitedBlocks()  # DelimitedBlock definitions.

    global tables_OLD
    tables_OLD = Tables_OLD()   # Table_OLD definitions.

    global tables
    tables = Tables()           # Table definitions.

    from .document import Macros, CalloutMap
    global macros
    macros = Macros()           # Macro definitions.

    global calloutmap
    calloutmap = CalloutMap()   # Coordinates callouts and callout list.

    from .util import Trace
    global trace
    trace = Trace()             # Implements trace attribute processing.
