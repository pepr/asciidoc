#---------------------------------------------------------------------------
# Utility functions and classes.
#---------------------------------------------------------------------------

import os
import re
import sys
import time
import unicodedata

import core.g

#---------------------------------------------------------------------------
# Program constants.
#---------------------------------------------------------------------------
OR, AND = ',', '+'              # Attribute list separators.
NAME_RE = r'(?u)[^\W\d][-\w]*'  # Valid section or attribute name.

class EAsciiDoc(Exception): pass

class AttrDict(dict):
    """
    Like a dictionary except values can be accessed as attributes i.e. obj.foo
    can be used in addition to obj['foo'].
    If an item is not present None is returned.
    """
    def __getattr__(self, key):
        try: return self[key]
        except KeyError: return None
    def __setattr__(self, key, value):
        self[key] = value
    def __delattr__(self, key):
        try: del self[key]
        except KeyError as k: raise AttributeError(k)
    def __repr__(self):
        return '<AttrDict ' + dict.__repr__(self) + '>'
    def __getstate__(self):
        return dict(self)
    def __setstate__(self,value):
        for k,v in value.items(): self[k]=v

class InsensitiveDict(dict):
    """
    Like a dictionary except key access is case insensitive.
    Keys are stored in lower case.
    """
    def __getitem__(self, key):
        return dict.__getitem__(self, key.lower())
    def __setitem__(self, key, value):
        dict.__setitem__(self, key.lower(), value)
    def has_key(self, key):
        return dict.has_key(self,key.lower())
    def get(self, key, default=None):
        return dict.get(self, key.lower(), default)
    def update(self, dict):
        for k, v in dict.items():
            self[k] = v
    def setdefault(self, key, default = None):
        return dict.setdefault(self, key.lower(), default)


class Trace:
    """
    Used in conjunction with the 'trace' attribute to generate diagnostic
    output. There is a single global instance of this class named core.g.trace.
    """
    SUBS_NAMES = ('specialcharacters', 'quotes', 'specialwords',
                  'replacements', 'attributes', 'macros', 'callouts',
                  'replacements2', 'replacements3')
    def __init__(self):
        self.name_re = ''        # Regexp pattern to match trace names.
        self.linenos = True
        self.offset = 0
    def __call__(self, name, before, after=None):
        """
        Print trace message if tracing is on and the trace 'name' matches the
        document 'trace' attribute (treated as a regexp).
        'before' is the source text before substitution; 'after' text is the
        source text after substitution.
        The 'before' and 'after' messages are only printed if they differ.
        """
        name_re = core.g.document.attributes.get('trace')
        if name_re == 'subs':    # Alias for all the inline substitutions.
            name_re = '|'.join(self.SUBS_NAMES)
        self.name_re = name_re
        if self.name_re is not None:
            msg = core.g.message.format(name, 'TRACE: ', self.linenos, offset=self.offset)
            if before != after and re.match(self.name_re,name):
                if is_array(before):
                    before = '\n'.join(before)
                if after is None:
                    msg += '\n%s\n' % before
                else:
                    if is_array(after):
                        after = '\n'.join(after)
                    msg += '\n<<<\n%s\n>>>\n%s\n' % (before,after)
                core.g.message.stderr(msg)


def userdir():
    """
    Return user's home directory or None if it is not defined.
    """
    result = os.path.expanduser('~')
    if result == '~':
        result = None
    return result

def localapp():
    """
    Return True if we are not executing the system wide version
    i.e. the configuration is in the executable's directory.
    """
    return os.path.isfile(os.path.join(core.g.app_dir, 'asciidoc.conf'))

def file_in(fname, directory):
    """Return True if file fname resides inside directory."""
    assert os.path.isfile(fname)
    # Empty directory (not to be confused with None) is the current directory.
    if directory == '':
        directory = os.getcwd()
    else:
        assert os.path.isdir(directory)
        directory = os.path.realpath(directory)
    fname = os.path.realpath(fname)
    return os.path.commonprefix((directory, fname)) == directory

def safe():
    return core.g.document.safe

def is_safe_file(fname, directory=None):
    # A safe file must reside in 'directory' (defaults to the source
    # file directory).
    if directory is None:
        if core.g.document.infile == '<stdin>':
           return not safe()
        directory = os.path.dirname(core.g.document.infile)
    elif directory == '':
        directory = '.'
    return (
        not safe()
        or file_in(fname, directory)
        or file_in(fname, core.g.app_dir)
        or file_in(fname, core.g.conf_dir)
    )

def safe_filename(fname, parentdir):
    """
    Return file name which must reside in the parent file directory.
    Return None if file is not safe.
    """
    if not os.path.isabs(fname):
        # Include files are relative to parent document
        # directory.
        fname = os.path.normpath(os.path.join(parentdir,fname))
    if not is_safe_file(fname, parentdir):
        core.g.message.unsafe('include file: %s' % fname)
        return None
    return fname

def assign(dst,src):
    """Assign all attributes from 'src' object to 'dst' object."""
    for a,v in src.__dict__.items():
        setattr(dst,a,v)

def strip_quotes(s):
    """Trim white space and, if necessary, quote characters from s."""
    s = s.strip()
    # Strip quotation mark characters from quoted strings.
    if len(s) >= 3 and s[0] == '"' and s[-1] == '"':
        s = s[1:-1]
    return s

def is_re(s):
    """Return True if s is a valid regular expression else return False."""
    try:
        re.compile(s)
        return True
    except:
        return False

def re_join(relist):
    """Join list of regular expressions re1,re2,... to single regular
    expression (re1)|(re2)|..."""
    if len(relist) == 0:
        return None
    result = []
    # Delete named groups to avoid ambiguity.
    for s in relist:
        result.append(re.sub(r'\?P<\S+?>','',s))
    result = ')|('.join(result)
    result = '('+result+')'
    return result

def lstrip_list(s):
    """
    Return list with empty items from start of list removed.
    """
    for i in range(len(s)):
        if s[i]: break
    else:
        return []
    return s[i:]

def rstrip_list(s):
    """
    Return list with empty items from end of list removed.
    """
    for i in range(len(s)-1,-1,-1):
        if s[i]: break
    else:
        return []
    return s[:i+1]

def strip_list(s):
    """
    Return list with empty items from start and end of list removed.
    """
    s = lstrip_list(s)
    s = rstrip_list(s)
    return s

def is_array(obj):
    """
    Return True if object is list or tuple type.
    """
    return isinstance(obj,list) or isinstance(obj,tuple)

def dovetail(lines1, lines2):
    """
    Append list or tuple of strings 'lines2' to list 'lines1'.  Join the last
    non-blank item in 'lines1' with the first non-blank item in 'lines2' into a
    single string.
    """
    assert is_array(lines1)
    assert is_array(lines2)
    lines1 = strip_list(lines1)
    lines2 = strip_list(lines2)
    if not lines1 or not lines2:
        return list(lines1) + list(lines2)
    result = list(lines1[:-1])
    result.append(lines1[-1] + lines2[0])
    result += list(lines2[1:])
    return result

def dovetail_tags(stag,content,etag):
    """Merge the end tag with the first content line and the last
    content line with the end tag. This ensures verbatim elements don't
    include extraneous opening and closing line breaks."""
    return dovetail(dovetail(stag,content), etag)

# The following functions are so we don't have to use the dangerous
# built-in eval() function.
if float(sys.version[:3]) >= 2.6 or sys.platform[:4] == 'java':
    # Use AST module if CPython >= 2.6 or Jython.
    import ast
    from ast import literal_eval

    def get_args(val):
        d = {}
        args = ast.parse("d(" + val + ")", mode='eval').body.args
        i = 1
        for arg in args:
            if isinstance(arg, ast.Name):
                d[str(i)] = literal_eval(arg.id)
            else:
                d[str(i)] = literal_eval(arg)
            i += 1
        return d

    def get_kwargs(val):
        d = {}
        args = ast.parse("d(" + val + ")", mode='eval').body.keywords
        for arg in args:
            d[arg.arg] = literal_eval(arg.value)
        return d

    def parse_to_list(val):
        values = ast.parse("[" + val + "]", mode='eval').body.elts
        return [literal_eval(v) for v in values]

else:   # Use deprecated CPython compiler module.
    import compiler
    from compiler.ast import Const, Dict, Expression, Name, Tuple, UnarySub, Keyword

    # Code from:
    # http://mail.python.org/pipermail/python-list/2009-September/1219992.html
    # Modified to use compiler.ast.List as this module has a List
    def literal_eval(node_or_string):
        """
        Safely evaluate an expression node or a string containing a Python
        expression.  The string or node provided may only consist of the
        following Python literal structures: strings, numbers, tuples,
        lists, dicts, booleans, and None.
        """
        _safe_names = {'None': None, 'True': True, 'False': False}
        if isinstance(node_or_string, str):
            node_or_string = compiler.parse(node_or_string, mode='eval')
        if isinstance(node_or_string, Expression):
            node_or_string = node_or_string.node
        def _convert(node):
            if isinstance(node, Const) and isinstance(node.value,
                    (str, int, float, complex)):
                 return node.value
            elif isinstance(node, Tuple):
                return tuple(map(_convert, node.nodes))
            elif isinstance(node, compiler.ast.List):
                return list(map(_convert, node.nodes))
            elif isinstance(node, Dict):
                return dict((_convert(k), _convert(v)) for k, v
                            in node.items)
            elif isinstance(node, Name):
                if node.name in _safe_names:
                    return _safe_names[node.name]
            elif isinstance(node, UnarySub):
                return -_convert(node.expr)
            raise ValueError('malformed string')
        return _convert(node_or_string)

    def get_args(val):
        d = {}
        args = compiler.parse("d(" + val + ")", mode='eval').node.args
        i = 1
        for arg in args:
            if isinstance(arg, Keyword):
                break
            d[str(i)] = literal_eval(arg)
            i = i + 1
        return d

    def get_kwargs(val):
        d = {}
        args = compiler.parse("d(" + val + ")", mode='eval').node.args
        i = 0
        for arg in args:
            if isinstance(arg, Keyword):
                break
            i += 1
        args = args[i:]
        for arg in args:
            d[str(arg.name)] = literal_eval(arg.expr)
        return d

    def parse_to_list(val):
        values = compiler.parse("[" + val + "]", mode='eval').node.asList()
        return [literal_eval(v) for v in values]

def parse_attributes(attrs,dict):
    """Update a dictionary with name/value attributes from the attrs string.
    The attrs string is a comma separated list of values and keyword name=value
    pairs. Values must preceed keywords and are named '1','2'... The entire
    attributes list is named '0'. If keywords are specified string values must
    be quoted. Examples:

    attrs: ''
    dict: {}

    attrs: 'hello,world'
    dict: {'2': 'world', '0': 'hello,world', '1': 'hello'}

    attrs: '"hello", planet="earth"'
    dict: {'planet': 'earth', '0': '"hello",planet="earth"', '1': 'hello'}
    """
    def f(*args,**keywords):
        # Name and add aguments '1','2'... to keywords.
        for i in range(len(args)):
            if not str(i+1) in keywords:
                keywords[str(i+1)] = args[i]
        return keywords

    if not attrs:
        return
    dict['0'] = attrs
    # Replace line separators with spaces so line spanning works.
    s = re.sub(r'\s', ' ', attrs)
    d = {}
    try:
        d.update(get_args(s))
        d.update(get_kwargs(s))
        for v in d.values():
            if not (isinstance(v,str) or isinstance(v,int) or isinstance(v,float) or v is None):
                raise Exception
    except Exception:
        s = s.replace('"','\\"')
        s = s.split(',')
        s = ['"' + x.strip() + '"' for x in s]
        s = ','.join(s)
        try:
            d = {}
            d.update(get_args(s))
            d.update(get_kwargs(s))
        except Exception:
            return  # If there's a syntax error leave with {0}=attrs.
        for k in list(d.keys()):  # Drop any empty positional arguments.
            if d[k] == '': del d[k]
    dict.update(d)
    assert len(d) > 0

def parse_named_attributes(s,attrs):
    """Update a attrs dictionary with name="value" attributes from the s string.
    Returns False if invalid syntax.
    Example:
    attrs: 'star="sun",planet="earth"'
    dict: {'planet': 'earth', 'star': 'sun'}
    """
    def f(**keywords): return keywords

    try:
        d = {}
        d = get_kwargs(s)
        attrs.update(d)
        return True
    except Exception:
        return False

def parse_list(s):
    """Parse comma separated string of Python literals. Return a tuple of of
    parsed values."""
    try:
        result = tuple(parse_to_list(s))
    except Exception:
        raise EAsciiDoc('malformed list: '+s)
    return result

def parse_options(options,allowed,errmsg):
    """Parse comma separated string of unquoted option names and return as a
    tuple of valid options. 'allowed' is a list of allowed option values.
    If allowed=() then all legitimate names are allowed.
    'errmsg' is an error message prefix if an illegal option error is thrown."""
    result = []
    if options:
        for s in re.split(r'\s*,\s*',options):
            if (allowed and s not in allowed) or not is_name(s):
                raise EAsciiDoc('%s: %s' % (errmsg,s))
            result.append(s)
    return tuple(result)

def symbolize(s):
    """Drop non-symbol characters and convert to lowercase."""
    return re.sub(r'(?u)[^\w\-_]', '', s).lower()

def is_name(s):
    """Return True if s is valid attribute, macro or tag name
    (starts with alpha containing alphanumeric and dashes only)."""
    return re.match(r'^'+NAME_RE+r'$',s) is not None

def subs_quotes(text):
    """Quoted text is marked up and the resulting text is
    returned."""
    keys = list(core.g.config.quotes.keys())
    for q in keys:
        i = q.find('|')
        if i != -1 and q != '|' and q != '||':
            lq = q[:i]      # Left quote.
            rq = q[i+1:]    # Right quote.
        else:
            lq = rq = q
        tag = core.g.config.quotes[q]
        if not tag: continue
        # Unconstrained quotes prefix the tag name with a hash.
        if tag[0] == '#':
            tag = tag[1:]
            # Unconstrained quotes can appear anywhere.
            reo = re.compile(r'(?msu)(^|.)(\[(?P<attrlist>[^[\]]+?)\])?' \
                    + r'(?:' + re.escape(lq) + r')' \
                    + r'(?P<content>.+?)(?:'+re.escape(rq)+r')')
        else:
            # The text within constrained quotes must be bounded by white space.
            # Non-word (\W) characters are allowed at boundaries to accomodate
            # enveloping quotes and punctuation e.g. a='x', ('x'), 'x', ['x'].
            reo = re.compile(r'(?msu)(^|[^\w;:}])(\[(?P<attrlist>[^[\]]+?)\])?' \
                + r'(?:' + re.escape(lq) + r')' \
                + r'(?P<content>\S|\S.*?\S)(?:'+re.escape(rq)+r')(?=\W|$)')
        pos = 0
        while True:
            mo = reo.search(text,pos)
            if not mo: break
            if text[mo.start()] == '\\':
                # Delete leading backslash.
                text = text[:mo.start()] + text[mo.start()+1:]
                # Skip past start of match.
                pos = mo.start() + 1
            else:
                attrlist = {}
                parse_attributes(mo.group('attrlist'), attrlist)
                stag,etag = core.g.config.tag(tag, attrlist)
                s = mo.group(1) + stag + mo.group('content') + etag
                text = text[:mo.start()] + s + text[mo.end():]
                pos = mo.start() + len(s)
    return text

def subs_tag(tag,dict={}):
    """Perform attribute substitution and split tag string returning start, end
    tag tuple (c.f. Config.tag())."""
    if not tag:
        return [None,None]
    s = subs_attrs(tag,dict)
    if not s:
        core.g.message.warning('tag \'%s\' dropped: contains undefined attribute' % tag)
        return [None,None]
    result = s.split('|')
    if len(result) == 1:
        return result+[None]
    elif len(result) == 2:
        return result
    else:
        raise EAsciiDoc('malformed tag: %s' % tag)

def parse_entry(entry, dict=None, unquote=False, unique_values=False,
        allow_name_only=False, escape_delimiter=True):
    """Parse name=value entry to dictionary 'dict'. Return tuple (name,value)
    or None if illegal entry.
    If name= then value is set to ''.
    If name and allow_name_only=True then value is set to ''.
    If name! and allow_name_only=True then value is set to None.
    Leading and trailing white space is striped from 'name' and 'value'.
    'name' can contain any printable characters.
    If the '=' delimiter character is allowed in  the 'name' then
    it must be escaped with a backslash and escape_delimiter must be True.
    If 'unquote' is True leading and trailing double-quotes are stripped from
    'name' and 'value'.
    If unique_values' is True then dictionary entries with the same value are
    removed before the parsed entry is added."""
    if escape_delimiter:
        mo = re.search(r'(?:[^\\](=))',entry)
    else:
        mo = re.search(r'(=)',entry)
    if mo:  # name=value entry.
        if mo.group(1):
            name = entry[:mo.start(1)]
            if escape_delimiter:
                name = name.replace(r'\=','=')  # Unescape \= in name.
            value = entry[mo.end(1):]
    elif allow_name_only and entry:         # name or name! entry.
        name = entry
        if name[-1] == '!':
            name = name[:-1]
            value = None
        else:
            value = ''
    else:
        return None
    if unquote:
        name = strip_quotes(name)
        if value is not None:
            value = strip_quotes(value)
    else:
        name = name.strip()
        if value is not None:
            value = value.strip()
    if not name:
        return None
    if dict is not None:
        if unique_values:
            for k,v in list(dict.items()):
                if v == value: del dict[k]
        dict[name] = value
    return name,value

def parse_entries(entries, dict, unquote=False, unique_values=False,
        allow_name_only=False,escape_delimiter=True):
    """Parse name=value entries from  from lines of text in 'entries' into
    dictionary 'dict'. Blank lines are skipped."""
    entries = core.g.config.expand_templates(entries)
    for entry in entries:
        if entry and not parse_entry(entry, dict, unquote, unique_values,
                allow_name_only, escape_delimiter):
            raise EAsciiDoc('malformed section entry: %s' % entry)

def dump_section(name,dict,f=sys.stdout):
    """Write parameters in 'dict' as in configuration file section format with
    section 'name'."""
    f.write('[%s]%s' % (name,writer.newline))
    for k,v in dict.items():
        k = str(k)
        k = k.replace('=',r'\=')    # Escape = in name.
        # Quote if necessary.
        if len(k) != len(k.strip()):
            k = '"'+k+'"'
        if v and len(v) != len(v.strip()):
            v = '"'+v+'"'
        if v is None:
            # Don't dump undefined attributes.
            continue
        else:
            s = k+'='+v
        if s[0] == '#':
            s = '\\' + s    # Escape so not treated as comment lines.
        f.write('%s%s' % (s,writer.newline))
    f.write(core.g.writer.newline)

def update_attrs(attrs,dict):
    """Update 'attrs' dictionary with parsed attributes in dictionary 'dict'."""
    for k,v in dict.items():
        if not is_name(k):
            raise EAsciiDoc('illegal attribute name: %s' % k)
        attrs[k] = v

def is_attr_defined(attrs,dic):
    """
    Check if the sequence of attributes is defined in dictionary 'dic'.
    Valid 'attrs' sequence syntax:
    <attr> Return True if single attribute is defined.
    <attr1>,<attr2>,... Return True if one or more attributes are defined.
    <attr1>+<attr2>+... Return True if all the attributes are defined.
    """
    if OR in attrs:
        for a in attrs.split(OR):
            if dic.get(a.strip()) is not None:
                return True
        else: return False
    elif AND in attrs:
        for a in attrs.split(AND):
            if dic.get(a.strip()) is None:
                return False
        else: return True
    else:
        return dic.get(attrs.strip()) is not None

def filter_lines(filter_cmd, lines, attrs={}):
    """
    Run 'lines' through the 'filter_cmd' shell command and return the result.
    The 'attrs' dictionary contains additional filter attributes.
    """
    def findfilter(name,dir,filter):
        """Find filter file 'fname' with style name 'name' in directory
        'dir'. Return found file path or None if not found."""
        if name:
            result = os.path.join(dir,'filters',name,filter)
            if os.path.isfile(result):
                return result
        result = os.path.join(dir,'filters',filter)
        if os.path.isfile(result):
            return result
        return None

    # Return input lines if there's not filter.
    if not filter_cmd or not filter_cmd.strip():
        return lines
    # Perform attributes substitution on the filter command.
    s = subs_attrs(filter_cmd, attrs)
    if not s:
        core.g.message.error('undefined filter attribute in command: %s' % filter_cmd)
        return []
    filter_cmd = s.strip()
    # Parse for quoted and unquoted command and command tail.
    # Double quoted.
    mo = re.match(r'^"(?P<cmd>[^"]+)"(?P<tail>.*)$', filter_cmd)
    if not mo:
        # Single quoted.
        mo = re.match(r"^'(?P<cmd>[^']+)'(?P<tail>.*)$", filter_cmd)
        if not mo:
            # Unquoted catch all.
            mo = re.match(r'^(?P<cmd>\S+)(?P<tail>.*)$', filter_cmd)
    cmd = mo.group('cmd').strip()
    found = None
    if not os.path.dirname(cmd):
        # Filter command has no directory path so search filter directories.
        filtername = attrs.get('style')
        d = core.g.document.attributes.get('docdir')
        if d:
            found = findfilter(filtername, d, cmd)
        if not found:
            if core.g.user_dir:
                found = findfilter(filtername, core.g.user_dir, cmd)
            if not found:
                if localapp():
                    found = findfilter(filtername, core.g.app_dir, cmd)
                else:
                    found = findfilter(filtername, core.g.conf_dir, cmd)
    else:
        if os.path.isfile(cmd):
            found = cmd
        else:
            core.g.message.warning('filter not found: %s' % cmd)
    if found:
        filter_cmd = '"' + found + '"' + mo.group('tail')
    if found:
        if cmd.endswith('.py'):
            filter_cmd = '"%s" %s' % (core.g.document.attributes['python'],
                filter_cmd)
        elif cmd.endswith('.rb'):
            filter_cmd = 'ruby ' + filter_cmd

    core.g.message.verbose('filtering: ' + filter_cmd)
    if os.name == 'nt':
        # Remove redundant quoting -- this is not just
        # cosmetic, unnecessary quoting appears to cause
        # command line truncation.
        filter_cmd = re.sub(r'"([^ ]+?)"', r'\1', filter_cmd)
    try:
        p = subprocess.Popen(filter_cmd, shell=True,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        output = p.communicate('\n'.join(lines).encode('utf-8'))[0]
    except Exception:
        raise EAsciiDoc('filter error: %s: %s' % (filter_cmd, sys.exc_info()[1]))
    if output:
        result = [s.rstrip() for s in output.decode('utf-8').split('\n')]
    else:
        result = []
    filter_status = p.wait()
    if filter_status:
        core.g.message.warning('filter non-zero exit code: %s: returned %d' %
               (filter_cmd, filter_status))
    if lines and not result:
        core.g.message.warning('no output from filter: %s' % filter_cmd)
    return result

def system(name, args, is_macro=False, attrs=None):
    """
    Evaluate a system attribute ({name:args}) or system block macro
    (name::[args]).
    If is_macro is True then we are processing a system block macro otherwise
    it's a system attribute.
    The attrs dictionary is updated by the counter and set system attributes.
    NOTE: The include1 attribute is used internally by the include1::[] macro
    and is not for public use.
    """
    if is_macro:
        syntax = '%s::[%s]' % (name,args)
        separator = '\n'
    else:
        syntax = '{%s:%s}' % (name,args)
        separator = core.g.writer.newline
    if name not in ('eval','eval3','sys','sys2','sys3','include','include1','counter','counter2','set','set2','template'):
        if is_macro:
            msg = 'illegal system macro name: %s' % name
        else:
            msg = 'illegal system attribute name: %s' % name
        core.g.message.warning(msg)
        return None
    if is_macro:
        s = subs_attrs(args)
        if s is None:
            core.g.message.warning('skipped %s: undefined attribute in: %s' % (name,args))
            return None
        args = s
    if name != 'include1':
        core.g.message.verbose('evaluating: %s' % syntax)
    if safe() and name not in ('include','include1'):
        core.g.message.unsafe(syntax)
        return None
    result = None
    if name in ('eval','eval3'):
        try:
            result = eval(args)
            if result is True:
                result = ''
            elif result is False:
                result = None
            elif result is not None:
                result = str(result)
        except Exception:
            core.g.message.warning('%s: evaluation error' % syntax)
    elif name in ('sys','sys2','sys3'):
        result = ''
        fd,tmp = tempfile.mkstemp()
        os.close(fd)
        try:
            cmd = args
            cmd = cmd + (' > "%s"' % tmp)
            if name == 'sys2':
                cmd = cmd + ' 2>&1'
            if os.name == 'nt':
                # Remove redundant quoting -- this is not just
                # cosmetic, unnecessary quoting appears to cause
                # command line truncation.
                cmd = re.sub(r'"([^ ]+?)"', r'\1', cmd)
            core.g.message.verbose('shelling: %s' % cmd)
            if os.system(cmd):
                core.g.message.warning('%s: non-zero exit status' % syntax)
            try:
                if os.path.isfile(tmp):
                    f = open(tmp, 'r', encoding=core.g.document.attributes['encoding'])
                    try:
                        lines = [s.rstrip() for s in f]
                    finally:
                        f.close()
                else:
                    lines = []
            except Exception:
                raise EAsciiDoc('%s: temp file read error' % syntax)
            result = separator.join(lines)
        finally:
            if os.path.isfile(tmp):
                os.remove(tmp)
    elif name in ('counter','counter2'):
        mo = re.match(r'^(?P<attr>[^:]*?)(:(?P<seed>.*))?$', args)
        attr = mo.group('attr')
        seed = mo.group('seed')
        if seed and (not re.match(r'^\d+$', seed) and len(seed) > 1):
            core.g.message.warning('%s: illegal counter seed: %s' % (syntax,seed))
            return None
        if not is_name(attr):
            core.g.message.warning('%s: illegal attribute name' % syntax)
            return None
        value = core.g.document.attributes.get(attr)
        if value:
            if not re.match(r'^\d+$', value) and len(value) > 1:
                core.g.message.warning('%s: illegal counter value: %s'
                                % (syntax,value))
                return None
            if re.match(r'^\d+$', value):
                expr = value + '+1'
            else:
                expr = 'chr(ord("%s")+1)' % value
            try:
                result = str(eval(expr))
            except Exception:
                core.g.message.warning('%s: evaluation error: %s' % (syntax, expr))
        else:
            if seed:
                result = seed
            else:
                result = '1'
        core.g.document.attributes[attr] = result
        if attrs is not None:
            attrs[attr] = result
        if name == 'counter2':
            result = ''
    elif name in ('set','set2'):
        mo = re.match(r'^(?P<attr>[^:]*?)(:(?P<value>.*))?$', args)
        attr = mo.group('attr')
        value = mo.group('value')
        if value is None:
            value = ''
        if attr.endswith('!'):
            attr = attr[:-1]
            value = None
        if not is_name(attr):
            core.g.message.warning('%s: illegal attribute name' % syntax)
        else:
            if attrs is not None:
                attrs[attr] = value
            if name != 'set2':  # set2 only updates local attributes.
                core.g.document.attributes[attr] = value
        if value is None:
            result = None
        else:
            result = ''
    elif name == 'include':
        if not os.path.exists(args):
            core.g.message.warning('%s: file does not exist' % syntax)
        elif not is_safe_file(args):
            core.g.message.unsafe(syntax)
        else:
            f = open(args, 'r', encoding=core.g.document.attributes['encoding'])
            try:
                result = [s.rstrip() for s in f]
            finally:
                f.close()
            if result:
                result = subs_attrs(result)
                result = separator.join(result)
                result = result.expandtabs(core.g.reader.tabsize)
            else:
                result = ''
    elif name == 'include1':
        result = separator.join(core.g.config.include1[args])
    elif name == 'template':
        if not args in core.g.config.sections:
            core.g.message.warning('%s: template does not exist' % syntax)
        else:
            result = []
            for line in  core.g.config.sections[args]:
                line = subs_attrs(line)
                if line is not None:
                    result.append(line)
            result = '\n'.join(result)
    else:
        assert False
    if result and name in ('eval3','sys3'):
        core.g.macros.passthroughs.append(result)
        result = '\x07' + str(len(core.g.macros.passthroughs)-1) + '\x07'
    return result

def subs_attrs(lines, dictionary=None):
    """Substitute 'lines' of text with attributes from the global
    core.g.document.attributes dictionary and from 'dictionary' ('dictionary'
    entries take precedence). Return a tuple of the substituted lines.  'lines'
    containing undefined attributes are deleted. If 'lines' is a string then
    return a string.

    - Attribute references are substituted in the following order: simple,
      conditional, system.
    - Attribute references inside 'dictionary' entry values are substituted.
    """

    def end_brace(text,start):
        """Return index following end brace that matches brace at start in
        text."""
        assert text[start] == '{'
        n = 0
        result = start
        for c in text[start:]:
            # Skip braces that are followed by a backslash.
            if result == len(text)-1 or text[result+1] != '\\':
                if c == '{': n = n + 1
                elif c == '}': n = n - 1
            result = result + 1
            if n == 0: break
        return result

    if type(lines) == str:
        string_result = True
        lines = [lines]
    else:
        string_result = False
    if dictionary is None:
        attrs = core.g.document.attributes
    else:
        # Remove numbered document attributes so they don't clash with
        # attribute list positional attributes.
        attrs = {}
        for k,v in core.g.document.attributes.items():
            if not re.match(r'^\d+$', k):
                attrs[k] = v
        # Substitute attribute references inside dictionary values.
        for k,v in list(dictionary.items()):
            if v is None:
                del dictionary[k]
            else:
                v = subs_attrs(str(v))
                if v is None:
                    del dictionary[k]
                else:
                    dictionary[k] = v
        attrs.update(dictionary)
    # Substitute all attributes in all lines.
    result = []
    for line in lines:
        # Make it easier for regular expressions.
        line = line.replace('\\{','{\\')
        line = line.replace('\\}','}\\')
        # Expand simple attributes ({name}).
        # Nested attributes not allowed.
        reo = re.compile(r'(?su)\{(?P<name>[^\\\W][-\w]*?)\}(?!\\)')
        pos = 0
        while True:
            mo = reo.search(line,pos)
            if not mo: break
            s =  attrs.get(mo.group('name'))
            if s is None:
                pos = mo.end()
            else:
                s = str(s)
                line = line[:mo.start()] + s + line[mo.end():]
                pos = mo.start() + len(s)
        # Expand conditional attributes.
        # Single name -- higher precedence.
        reo1 = re.compile(r'(?su)\{(?P<name>[^\\\W][-\w]*?)' \
                          r'(?P<op>\=|\?|!|#|%|@|\$)' \
                          r'(?P<value>.*?)\}(?!\\)')
        # Multiple names (n1,n2,... or n1+n2+...) -- lower precedence.
        reo2 = re.compile(r'(?su)\{(?P<name>[^\\\W][-\w'+OR+AND+r']*?)' \
                          r'(?P<op>\=|\?|!|#|%|@|\$)' \
                          r'(?P<value>.*?)\}(?!\\)')
        for reo in [reo1,reo2]:
            pos = 0
            while True:
                mo = reo.search(line,pos)
                if not mo: break
                attr = mo.group()
                name =  mo.group('name')
                if reo == reo2:
                    if OR in name:
                        sep = OR
                    else:
                        sep = AND
                    names = [s.strip() for s in name.split(sep) if s.strip() ]
                    for n in names:
                        if not re.match(r'^[^\\\W][-\w]*$',n):
                            core.g.message.error('illegal attribute syntax: %s' % attr)
                    if sep == OR:
                        # Process OR name expression: n1,n2,...
                        for n in names:
                            if attrs.get(n) is not None:
                                lval = ''
                                break
                        else:
                            lval = None
                    else:
                        # Process AND name expression: n1+n2+...
                        for n in names:
                            if attrs.get(n) is None:
                                lval = None
                                break
                        else:
                            lval = ''
                else:
                    lval =  attrs.get(name)
                op = mo.group('op')
                # mo.end() not good enough because '{x={y}}' matches '{x={y}'.
                end = end_brace(line,mo.start())
                rval = line[mo.start('value'):end-1]
                UNDEFINED = '{zzzzz}'
                if lval is None:
                    if op == '=': s = rval
                    elif op == '?': s = ''
                    elif op == '!': s = rval
                    elif op == '#': s = UNDEFINED   # So the line is dropped.
                    elif op == '%': s = rval
                    elif op in ('@','$'):
                        s = UNDEFINED               # So the line is dropped.
                    else:
                        assert False, 'illegal attribute: %s' % attr
                else:
                    if op == '=': s = lval
                    elif op == '?': s = rval
                    elif op == '!': s = ''
                    elif op == '#': s = rval
                    elif op == '%': s = UNDEFINED   # So the line is dropped.
                    elif op in ('@','$'):
                        v = re.split(r'(?<!\\):',rval)
                        if len(v) not in (2,3):
                            core.g.message.error('illegal attribute syntax: %s' % attr)
                            s = ''
                        elif not is_re('^'+v[0]+'$'):
                            core.g.message.error('illegal attribute regexp: %s' % attr)
                            s = ''
                        else:
                            v = [s.replace('\\:',':') for s in v]
                            re_mo = re.match('^'+v[0]+'$',lval)
                            if op == '@':
                                if re_mo:
                                    s = v[1]         # {<name>@<re>:<v1>[:<v2>]}
                                else:
                                    if len(v) == 3:   # {<name>@<re>:<v1>:<v2>}
                                        s = v[2]
                                    else:             # {<name>@<re>:<v1>}
                                        s = ''
                            else:
                                if re_mo:
                                    if len(v) == 2:   # {<name>$<re>:<v1>}
                                        s = v[1]
                                    elif v[1] == '':  # {<name>$<re>::<v2>}
                                        s = UNDEFINED # So the line is dropped.
                                    else:             # {<name>$<re>:<v1>:<v2>}
                                        s = v[1]
                                else:
                                    if len(v) == 2:   # {<name>$<re>:<v1>}
                                        s = UNDEFINED # So the line is dropped.
                                    else:             # {<name>$<re>:<v1>:<v2>}
                                        s = v[2]
                    else:
                        assert False, 'illegal attribute: %s' % attr
                s = str(s)
                line = line[:mo.start()] + s + line[end:]
                pos = mo.start() + len(s)
        # Drop line if it contains  unsubstituted {name} references.
        skipped = re.search(r'(?su)\{[^\\\W][-\w]*?\}(?!\\)', line)
        if skipped:
            core.g.trace('dropped line', line)
            continue;
        # Expand system attributes (eval has precedence).
        reos = [
            re.compile(r'(?su)\{(?P<action>eval):(?P<expr>.*?)\}(?!\\)'),
            re.compile(r'(?su)\{(?P<action>[^\\\W][-\w]*?):(?P<expr>.*?)\}(?!\\)'),
        ]
        skipped = False
        for reo in reos:
            pos = 0
            while True:
                mo = reo.search(line,pos)
                if not mo: break
                expr = mo.group('expr')
                action = mo.group('action')
                expr = expr.replace('{\\','{')
                expr = expr.replace('}\\','}')
                s = system(action, expr, attrs=dictionary)
                if dictionary is not None and action in ('counter','counter2','set','set2'):
                    # These actions create and update attributes.
                    attrs.update(dictionary)
                if s is None:
                    # Drop line if the action returns None.
                    skipped = True
                    break
                line = line[:mo.start()] + s + line[mo.end():]
                pos = mo.start() + len(s)
            if skipped:
                break
        if not skipped:
            # Remove backslash from escaped entries.
            line = line.replace('{\\','{')
            line = line.replace('}\\','}')
            result.append(line)
    if string_result:
        if result:
            return '\n'.join(result)
        else:
            return None
    else:
        return tuple(result)

east_asian_widths = {'W': 2,   # Wide
                     'F': 2,   # Full-width (wide)
                     'Na': 1,  # Narrow
                     'H': 1,   # Half-width (narrow)
                     'N': 1,   # Neutral (not East Asian, treated as narrow)
                     'A': 1}   # Ambiguous (s/b wide in East Asian context,
                               # narrow otherwise, but that doesn't work)
"""Mapping of result codes from `unicodedata.east_asian_width()` to character
column widths."""

def column_width(text):
    if isinstance(text, str):
        width = 0
        for c in text:
            width += east_asian_widths[unicodedata.east_asian_width(c)]
        return width
    else:
        return len(text)

def time_str(t):
    """Convert seconds since the Epoch to formatted local time string.

    The earlier approach that uses time.tzname[x] cannot be used because
    of the issue with Windows + Python 3.3+ (http://bugs.python.org/issue16322).
    """
    import locale
    locale.setlocale(locale.LC_CTYPE, '')
    return time.strftime('%H:%M:%S %Z', time.localtime(t))

def date_str(t):
    """Convert seconds since the Epoch to formatted local date string."""
    t = time.localtime(t)
    return time.strftime('%Y-%m-%d', t)


class Lex:
    """Lexical analysis routines.

    Static methods and attributes only.
    """
    prev_element = None
    prev_cursor = None

    def __init__(self):
        raise AssertionError('no class instances allowed')

    @staticmethod
    def next():
        """Returns class of next element on the input (None if EOF).

        The reader is assumed to be at the first line following a previous element,
        end of file or line one.  Exits with the reader pointing to the first
        line of the next element or EOF (leading blank lines are skipped)."""
        core.g.reader.skip_blank_lines()
        if core.g.reader.eof(): return None
        # Optimization: If we've already checked for an element at this
        # position return the element.
        if Lex.prev_element and Lex.prev_cursor == core.g.reader.cursor:
            return Lex.prev_element
        if AttributeEntry.isnext():
            result = AttributeEntry
        elif AttributeList.isnext():
            result = AttributeList
        elif BlockTitle.isnext() and not core.g.tables_OLD.isnext():
            result = BlockTitle
        elif Title.isnext():
            if AttributeList.style() == 'float':
                result = FloatingTitle
            else:
                result = Title
        elif core.g.macros.isnext():
            result = core.g.macros.current
        elif core.g.lists.isnext():
            result = core.g.lists.current
        elif core.g.blocks.isnext():
            result = core.g.blocks.current
        elif core.g.tables_OLD.isnext():
            result = core.g.tables_OLD.current
        elif core.g.tables.isnext():
            result = core.g.tables.current
        else:
            if not core.g.paragraphs.isnext():
                raise EAsciiDoc('paragraph expected')
            result = core.g.paragraphs.current
        # Optimization: Cache answer.
        Lex.prev_cursor = core.g.reader.cursor
        Lex.prev_element = result
        return result

    @staticmethod
    def canonical_subs(options):
        """Translate composite subs values."""
        if len(options) == 1:
            if options[0] == 'none':
                options = ()
            elif options[0] == 'normal':
                options = core.g.config.subsnormal
            elif options[0] == 'verbatim':
                options = core.g.config.subsverbatim
        return options

    @staticmethod
    def subs_1(s,options):
        """Perform substitution specified in 'options' (in 'options' order)."""
        if not s:
            return s
        if core.g.document.attributes.get('plaintext') is not None:
            options = ('specialcharacters',)
        result = s
        options = Lex.canonical_subs(options)
        for o in options:
            if o == 'specialcharacters':
                result = core.g.config.subs_specialchars(result)
            elif o == 'attributes':
                result = subs_attrs(result)
            elif o == 'quotes':
                result = subs_quotes(result)
            elif o == 'specialwords':
                result = core.g.config.subs_specialwords(result)
            elif o in ('replacements','replacements2','replacements3'):
                result = core.g.config.subs_replacements(result,o)
            elif o == 'macros':
                result = core.g.macros.subs(result)
            elif o == 'callouts':
                result = core.g.macros.subs(result,callouts=True)
            else:
                raise EAsciiDoc('illegal substitution option: %s' % o)
            core.g.trace(o, s, result)
            if not result:
                break
        return result

    @staticmethod
    def subs(lines, options):
        """Inline processing of `lines` by `options`.

        Perform inline processing specified by `options`
        (in `options` order) on sequence of `lines`.
        """
        if not lines or not options:
            return lines
        options = Lex.canonical_subs(options)
        # Join lines so quoting can span multiple lines.
        para = '\n'.join(lines)
        if 'macros' in options:
            para = core.g.macros.extract_passthroughs(para)
        for o in options:
            if o == 'attributes':
                # If we don't substitute attributes line-by-line then a single
                # undefined attribute will drop the entire paragraph.
                lines = subs_attrs(para.split('\n'))
                para = '\n'.join(lines)
            else:
                para = Lex.subs_1(para,(o,))
        if 'macros' in options:
            para = core.g.macros.restore_passthroughs(para)
        return para.splitlines()

    @staticmethod
    def set_margin(lines, margin=0):
        """Sets the left margin in a block of non-blank lines.

        Utility routine that sets the left margin to `margin` space
        in a block of non-blank lines."""
        # Calculate width of block margin.
        lines = list(lines)
        width = len(lines[0])
        rex = re.compile(r'\S')
        for s in lines:
            i = rex.search(s).start()
            if i < width:
                width = i
        # Strip margin width from all lines.
        for i in range(len(lines)):
            lines[i] = ' '*margin + lines[i][width:]
        return lines

# Blind move: Probably because of some cyclic references, the following import
# must be at the end. Don't ask me :)
from core.document import *
