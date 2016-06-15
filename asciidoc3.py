#!/usr/bin/env python3
"""
asciidoc - converts an AsciiDoc text file to HTML or DocBook

Copyright (C) 2002-2010 Stuart Rackham. Free use of this software is granted
under the terms of the GNU General Public License (GPL).
"""

import collections
import copy
import sys
import os
import re
import time
import traceback
import tempfile
import subprocess
import unicodedata

from core.util import *
from core.document import Title, AttributeList

### Used by asciidocapi.py ###
VERSION = '8.6.9 python3 alpha1'           # See CHANGELOG file for version history.

MIN_PYTHON_VERSION = (3, 4, 0)  # Require this version of Python or better.

#---------------------------------------------------------------------------
# Program constants.
#---------------------------------------------------------------------------

# Default value for unspecified subs and presubs configuration file entries.
SUBS_NORMAL = ('specialcharacters', 'quotes', 'attributes',
    'specialwords', 'replacements', 'macros', 'replacements2')
SUBS_VERBATIM = ('specialcharacters', 'callouts')




#---------------------------------------------------------------------------
# Input stream Reader and output stream writer classes.
#---------------------------------------------------------------------------

UTF8_BOM = b'\xef\xbb\xbf'

class Reader1:
    """Line oriented AsciiDoc input file core.g.reader.

    The reader processes include and conditional inclusion system core.g.macros.
    Tabs are expanded and lines are right trimmed.

    Attention: This class is not to be used directly. Use the Reader class instead.
    """
    READ_BUFFER_MIN = 10        # Read buffer low level.

    def __init__(self, forced_encoding=None):
        self.f = None           # Input file object.
        self.fname = None       # Input file name.
        self.linebuffer = []    # Read ahead buffer containing
                                # (filename, linenumber, linetext) tuples.
        self.cursor = None      # Last read() (filename, linenumber, linetext).
        self.tabsize = 8        # Tab expansion number of spaces.
        self.parent = None      # Included reader's parent core.g.reader.
        self._lineno = 0        # The last line read from file object f.
        self.current_depth = 0  # Current include depth.
        self.max_depth = 10     # Initial maximum allowed include depth.
        self.infile = None      # Saved document 'infile' attribute.
        self.indir = None       # Saved document 'indir' attribute.
        self.forced_encoding = forced_encoding

    def open(self, fname):
        self.fname = fname
        core.g.message.verbose('reading: ' + fname)
        if fname == '<stdin>':
            self.f = sys.stdin
            self.infile = None
            self.indir = None
        else:
            # The file must be open in binary mode, because the content
            # is read to buffer ahead of processing. If the file were open
            # in the text mode, the buffer would be decoded using some encoding.
            # It means that lines (as strings) would be decoded before they
            # are iterated. However, the input file may prescribe the encoding
            # that cannot be anticipated -- using the `:encoding: ...`.
            self.f = open(fname, 'rb')
            self.infile = fname
            self.indir = os.path.dirname(fname)
        core.g.document.attributes['infile'] = self.infile
        core.g.document.attributes['indir'] = self.indir
        self._lineno = 0            # The last line read from file object f.
        self.linebuffer = []

    def closefile(self):
        """Used by class methods to close nested include files."""
        self.f.close()
        self.linebuffer = []

    def close(self):
        self.closefile()
        self.__init__()

    def read(self, skip=False):
        """Read and proces the next line.

        Return None if EOF. Expand tabs. Strip trailing white space.

        Maintain self.linebuffer read ahead buffer. If skip=True then
        conditional exclusion is active (ifdef and ifndef macros).
        """
        # Top up buffer.
        if len(self.linebuffer) <= self.READ_BUFFER_MIN:
            linebytes = self.f.readline()     # line as bytes type
            if self.forced_encoding:
                encoding = self.forced_encoding
            elif self._lineno == 0 and isinstance(linebytes, bytes) and linebytes.startswith(UTF8_BOM):
                encoding = 'utf-8-sig'
            else:
                encoding = core.g.document.attributes.get('encoding', 'utf-8')

            while linebytes:                  # while not EOF
                self._lineno = self._lineno + 1
                if isinstance(linebytes, bytes):
                    s = linebytes.decode(encoding) # line as (unicode) string
                else:
                    s = linebytes #???PP should always be bytes, or not?
                s = s.rstrip()  # strip trailing spaces and line-end sequences
                # If the line itself defines encoding for the next lines,
                # capture the encoding. ???PP this is quick hack and should be improved.
                if s.startswith(':encoding:'):
                    encoding = s.split(':')[2].strip()
                    core.g.document.attributes['encoding'] = encoding
                if self.tabsize != 0:
                    s = s.expandtabs(self.tabsize)
                self.linebuffer.append((self.fname, self._lineno, s))
                if len(self.linebuffer) > self.READ_BUFFER_MIN:
                    break
                linebytes = self.f.readline() # get ready for the next loop

        # Return first (oldest) buffer entry.
        if len(self.linebuffer) > 0:
            self.cursor = list(self.linebuffer.pop(0)) #???PP check for the necessity of the list() wrap
            line = self.cursor[2]
            # Check for include macro.
            mo = core.g.macros.match('+', r'^include[1]?$', line)
            if mo and not skip:
                # Parse include macro attributes.
                attrs = {}
                parse_attributes(mo.group('attrlist'), attrs)
                warnings = attrs.get('warnings', True)
                # Don't process include macro once the maximum depth is reached.
                if self.current_depth >= self.max_depth:
                    core.g.message.warning('maximum include depth exceeded')
                    return line
                # Perform attribute substitution on include macro file name.
                fname = subs_attrs(mo.group('target'))
                if not fname:
                    return Reader1.read(self)   # Return next input line.
                if self.fname != '<stdin>':
                    fname = os.path.expandvars(os.path.expanduser(fname))
                    fname = safe_filename(fname, os.path.dirname(self.fname))
                    if not fname:
                        return Reader1.read(self)   # Return next input line.
                    if not os.path.isfile(fname):
                        if warnings:
                            core.g.message.warning('include file not found: %s' % fname)
                        return Reader1.read(self)   # Return next input line.
                    if mo.group('name') == 'include1':
                        if not core.g.config.dumping:
                            if fname not in core.g.config.include1:
                                core.g.message.verbose('include1: ' + fname, linenos=False)
                                # Store the include file in memory for later
                                # retrieval by the {include1:} system attribute.
                                f = open(fname, 'r', encoding=core.g.document.attributes['encoding'])
                                try:
                                    core.g.config.include1[fname] = [
                                        s.rstrip() for s in f]
                                finally:
                                    f.close()
                            return '{include1:%s}' % fname
                        else:
                            # This is a configuration dump, just pass the macro
                            # call through.
                            return line
                # Clone self and set as parent (self assumes the role of child).
                parent = Reader1()
                assign(parent, self)
                self.parent = parent
                # Set attributes in child.
                if 'tabsize' in attrs:
                    try:
                        val = int(attrs['tabsize'])
                        if not val >= 0:
                            raise ValueError('not >= 0')
                        self.tabsize = val
                    except ValueError:
                        raise EAsciiDoc('illegal include macro tabsize argument')
                else:
                    self.tabsize = core.g.config.tabsize
                if 'depth' in attrs:
                    try:
                        val = int(attrs['depth'])
                        if not val >= 1:
                            raise ValueError('not >= 1')
                        self.max_depth = self.current_depth + val
                    except ValueError:
                        raise EAsciiDoc("include macro: illegal 'depth' argument")
                # Process included file.
                core.g.message.verbose('include: ' + fname, linenos=False)
                self.open(fname)
                self.current_depth = self.current_depth + 1
                line = Reader1.read(self)
        else:
            if not Reader1.eof(self):
                line = Reader1.read(self)
            else:
                line = None
        return line

    def eof(self):
        """Returns True if all lines have been read."""
        if len(self.linebuffer) == 0:
            # End of current file.
            if self.parent:
                self.closefile()
                assign(self, self.parent)    # Restore parent core.g.reader.
                core.g.document.attributes['infile'] = self.infile
                core.g.document.attributes['indir'] = self.indir
                return Reader1.eof(self)
            else:
                return True
        else:
            return False

    def read_next(self):
        """Like read() but does not advance file pointer."""
        if Reader1.eof(self):
            return None
        else:
            return self.linebuffer[0][2]

    def unread(self, cursor):
        """Push the line (filename, linenumber, linetext) tuple back into the read
        buffer. Note that it's up to the caller to restore the previous cursor."""
        assert cursor
        self.linebuffer.insert(0, cursor)

class Reader(Reader1):
    """ Wraps (well, sought of) Reader1 class and implements conditional text
    inclusion.
    """

    def __init__(self, forced_encoding=None):
        Reader1.__init__(self, forced_encoding)
        self.depth = 0          # if nesting depth.
        self.skip = False       # true if we're skipping ifdef...endif.
        self.skipname = ''      # Name of current endif macro target.
        self.skipto = -1        # The depth at which skipping is reenabled.

    def read_super(self):
        result = Reader1.read(self, self.skip)
        if result is None and self.skip:
            raise EAsciiDoc('missing endif::%s[]' % self.skipname)
        return result

    def read(self):
        result = self.read_super()
        if result is None:
            return None
        while self.skip:
            mo = core.g.macros.match('+', r'ifdef|ifndef|ifeval|endif', result)
            if mo:
                name = mo.group('name')
                target = mo.group('target')
                attrlist = mo.group('attrlist')
                if name == 'endif':
                    self.depth -= 1
                    if self.depth < 0:
                        raise EAsciiDoc('mismatched macro: %s' % result)
                    if self.depth == self.skipto:
                        self.skip = False
                        if target and self.skipname != target:
                            raise EAsciiDoc('mismatched macro: %s' % result)
                else:
                    if name in ('ifdef', 'ifndef'):
                        if not target:
                            raise EAsciiDoc('missing macro target: %s' % result)
                        if not attrlist:
                            self.depth += 1
                    elif name == 'ifeval':
                        if not attrlist:
                            raise EAsciiDoc('missing ifeval condition: %s' % result)
                        self.depth += 1
            result = self.read_super()
            if result is None:
                return None
        mo = core.g.macros.match('+', r'ifdef|ifndef|ifeval|endif', result)
        if mo:
            name = mo.group('name')
            target = mo.group('target')
            attrlist = mo.group('attrlist')
            if name == 'endif':
                self.depth = self.depth-1
            else:
                if not target and name in ('ifdef', 'ifndef'):
                    raise EAsciiDoc('missing macro target: %s' % result)
                defined = is_attr_defined(target, core.g.document.attributes)
                if name == 'ifdef':
                    if attrlist:
                        if defined: return attrlist
                    else:
                        self.skip = not defined
                elif name == 'ifndef':
                    if attrlist:
                        if not defined: return attrlist
                    else:
                        self.skip = defined
                elif name == 'ifeval':
                    if safe():
                        core.g.message.unsafe('ifeval invalid')
                        raise EAsciiDoc('ifeval invalid safe document')
                    if not attrlist:
                        raise EAsciiDoc('missing ifeval condition: %s' % result)
                    cond = False
                    attrlist = subs_attrs(attrlist)
                    if attrlist:
                        try:
                            cond = eval(attrlist)
                        except Exception as e:
                            raise EAsciiDoc('error evaluating ifeval condition: %s: %s' % (result, str(e)))
                        core.g.message.verbose('ifeval: %s: %r' % (attrlist, cond))
                    self.skip = not cond
                if not attrlist or name == 'ifeval':
                    if self.skip:
                        self.skipto = self.depth
                        self.skipname = target
                    self.depth = self.depth+1
            result = self.read()
        if result:
            # Expand executable block core.g.macros.
            mo = core.g.macros.match('+', r'eval|sys|sys2', result)
            if mo:
                action = mo.group('name')
                cmd = mo.group('attrlist')
                result = system(action, cmd, is_macro=True)
                self.cursor[2] = result  # So we don't re-evaluate.
        if result:
            # Unescape escaped system core.g.macros.
            if core.g.macros.match('+', r'\\eval|\\sys|\\sys2|\\ifdef|\\ifndef|\\endif|\\include|\\include1', result):
                result = result[1:]
        return result

    def eof(self):
        return self.read_next() is None

    def read_next(self):
        save_cursor = self.cursor
        result = self.read()
        if result is not None:
            self.unread(self.cursor)
            self.cursor = save_cursor
        return result

    def read_lines(self, count=1):
        """Return tuple containing count lines."""
        result = []
        i = 0
        while i < count and not self.eof():
            result.append(self.read())
        return tuple(result)

    def read_ahead(self, count=1):
        """Same as read_lines() but does not advance the file pointer."""
        result = []
        putback = []
        save_cursor = self.cursor
        try:
            i = 0
            while i < count and not self.eof():
                result.append(self.read())
                putback.append(self.cursor)
                i = i+1
            while putback:
                self.unread(putback.pop())
        finally:
            self.cursor = save_cursor
        return tuple(result)

    def skip_blank_lines(self):
        core.g.reader.read_until(r'\s*\S+')

    def read_until(self, terminators, same_file=False):
        """Like read() but reads lines up to (but not including) the first line
        that matches the terminator regular expression, regular expression
        object or list of regular expression objects. If same_file is True then
        the terminating pattern must occur in the file the was being read when
        the routine was called."""
        if same_file:
            fname = self.cursor[0]
        result = []
        if not isinstance(terminators,list):
            if isinstance(terminators,str):
                terminators = [re.compile(terminators)]
            else:
                terminators = [terminators]
        while not self.eof():
            save_cursor = self.cursor
            s = self.read()
            if not same_file or fname == self.cursor[0]:
                for reo in terminators:
                    if reo.match(s):
                        self.unread(self.cursor)
                        self.cursor = save_cursor
                        return tuple(result)
            result.append(s)
        return tuple(result)

class Writer:
    """Writes lines to output file."""
    def __init__(self):
        self.f = None                    # Output file object.
        self.fname = None                # Output file name.
        self.lines_out = 0               # Number of lines written.
        self.skip_blank_lines = False    # If True don't output blank lines.

    def open(self, fname):
        self.fname = fname
        if fname == '<stdout>':
            self.f = sys.stdout
        else:
            encoding = core.g.document.attributes['encoding']

            # The utf-8-sig encoder writes also BOM to the beginning. For
            # concatenating resulting files or for some tools, the presence
            # of BOM may cause problems. Therefore, if the utf-8-sig encoding
            # is prescribed, it is changed to plain utf-8 (that is without BOM).
            if encoding == 'utf-8-sig':
                encoding = 'utf-8'
            self.f = open(fname, 'w', encoding=encoding)
        core.g.message.verbose('writing: ' + core.g.writer.fname, False)
        self.lines_out = 0

    def close(self):
        if self.fname != '<stdout>':
            self.f.close()

    def write_line(self, line=None):
        if not (self.skip_blank_lines and (not line or not line.strip())):
            self.f.write((line or '') + '\n')
            self.lines_out = self.lines_out + 1

    def write(self, *args, **kwargs):
        """Iterates arguments, writes tuple and list arguments one line per
        element, else writes argument as single line. If no arguments writes
        blank line. If argument is None nothing is written. '\n' is
        appended to each line."""
        if 'trace' in kwargs and len(args) > 0:
            core.g.trace(kwargs['trace'],args[0])
        if len(args) == 0:
            self.write_line()
            self.lines_out = self.lines_out + 1
        else:
            for arg in args:
                if is_array(arg):
                    for s in arg:
                        self.write_line(s)
                elif arg is not None:
                    self.write_line(arg)

    def write_tag(self, tag, content, subs=None, d=None, **kwargs):
        """Write content enveloped by tag.
        Substitutions specified in the 'subs' list are perform on the
        'content'."""
        if subs is None:
            subs = core.g.config.subsnormal
        stag,etag = subs_tag(tag,d)
        content = Lex.subs(content,subs)
        if 'trace' in kwargs:
            core.g.trace(kwargs['trace'], [stag] + content + [etag])
        if stag:
            self.write(stag)
        if content:
            self.write(content)
        if etag:
            self.write(etag)

#---------------------------------------------------------------------------
# Configuration file processing.
#---------------------------------------------------------------------------

def _subs_specialwords(mo):
    """Special word substitution function called by
    Config.subs_specialwords()."""
    word = mo.re.pattern                    # The special word.
    template = core.g.config.specialwords[word]    # The corresponding markup template.
    if not template in core.g.config.sections:
        raise EAsciiDoc('missing special word template [%s]' % template)
    if mo.group()[0] == '\\':
        return mo.group()[1:]   # Return escaped word.
    args = {}
    args['words'] = mo.group()  # The full match string is argument 'words'.
    args.update(mo.groupdict()) # Add other named match groups to the arguments.
    # Delete groups that didn't participate in match.
    for k,v in list(args.items()):
        if v is None: del args[k]
    lines = subs_attrs(core.g.config.sections[template],args)
    if len(lines) == 0:
        result = ''
    elif len(lines) == 1:
        result = lines[0]
    else:
        result = core.g.writer.newline.join(lines)
    return result

class Config:
    """Methods to process configuration files."""
    # Non-template section name regexp's.
    ENTRIES_SECTIONS= ('tags','miscellaneous','attributes','specialcharacters',
            'specialwords','macros','replacements','quotes','titles',
            r'paradef-.+',r'listdef-.+',r'blockdef-.+',r'tabledef-.+',
            r'tabletags-.+',r'listtags-.+','replacements[23]',
            r'old_tabledef-.+')

    def __init__(self):
        self.sections = collections.OrderedDict()   # Keyed by section name containing
                                        # lists of section lines.
        # Command-line options.
        self.verbose = False
        self.header_footer = True       # -s, --no-header-footer option.
        # [miscellaneous] section.
        self.tabsize = 8
        self.textwidth = 70             # DEPRECATED: Old tables only.
        self.newline = '\n'
        self.pagewidth = None
        self.pageunits = None
        self.outfilesuffix = ''
        self.subsnormal = SUBS_NORMAL
        self.subsverbatim = SUBS_VERBATIM

        self.tags = {}          # Values contain (stag,etag) tuples.
        self.specialchars = {}  # Values of special character substitutions.
        self.specialwords = {}  # Name is special word pattern, value is macro.
        self.replacements = collections.OrderedDict()   # Key is find pattern, value is
                                                        # replace pattern.
        self.replacements2 = collections.OrderedDict()
        self.replacements3 = collections.OrderedDict()
        self.specialsections = {} # Name is special section name pattern, value
                                  # is corresponding section name.
        self.quotes = collections.OrderedDict() # Values contain corresponding tag name.
        self.fname = ''         # Most recently loaded configuration file name.
        self.conf_attrs = {}    # Attributes entries from conf files.
        self.cmd_attrs = {}     # Attributes from command-line -a options.
        self.loaded = []        # Loaded conf files.
        self.include1 = {}      # Holds include1::[] files for {include1:}.
        self.dumping = False    # True if asciidoc -c option specified.
        self.filters = []       # Filter names specified by --filter option.

    def init(self, cmd):
        """
        Check Python version and locate the executable and configuration files
        directory.
        cmd is the asciidoc command or asciidoc.py path.
        """
        if sys.version_info[:3] < MIN_PYTHON_VERSION:
            core.g.message.stderr('FAILED: Python %s or better. required' %
                    MIN_PYTHON_VERSION)
            sys.exit(1)
        if not os.path.exists(cmd):
            core.g.message.stderr('FAILED: Missing asciidoc command: %s' % cmd)
            sys.exit(1)
        core.g.app_file = os.path.realpath(cmd)
        core.g.app_dir = os.path.dirname(core.g.app_file)
        core.g.user_dir = userdir()
        if core.g.user_dir is not None:
            core.g.user_dir = os.path.join(core.g.user_dir,'.asciidoc3')
            if not os.path.isdir(core.g.user_dir):
                core.g.user_dir = None

    def load_file(self, fname, dir=None, include=[], exclude=[]):
        """
        Loads sections dictionary with sections from file fname.
        Existing sections are overlaid.
        The 'include' list contains the section names to be loaded.
        The 'exclude' list contains section names not to be loaded.
        Return False if no file was found in any of the locations.
        """
        def update_section(section):
            """ Update section in sections with contents. """
            if section and contents:
                if section in sections and self.entries_section(section):
                    if ''.join(contents):
                        # Merge entries.
                        sections[section] += contents
                    else:
                        del sections[section]
                else:
                    if section.startswith('+'):
                        # Append section.
                        if section in sections:
                            sections[section] += contents
                        else:
                            sections[section] = contents
                    else:
                        # Replace section.
                        sections[section] = contents
        if dir:
            fname = os.path.join(dir, fname)
        # Sliently skip missing configuration file.
        if not os.path.isfile(fname):
            return False
        # Don't load conf files twice (local and application conf files are the
        # same if the source file is in the application directory).
        if os.path.realpath(fname) in self.loaded:
            return True
        rdr = Reader('utf-8')  # Reader processes system core.g.macros.
        core.g.message.linenos = False         # Disable document line numbers.
        rdr.open(fname)
        core.g.message.linenos = None
        self.fname = fname
        reo = re.compile(r'(?u)^\[(?P<section>\+?[^\W\d][\w-]*)\]\s*$')
        sections = collections.OrderedDict()
        section,contents = '',[]
        while not rdr.eof():
            s = rdr.read()
            if s and s[0] == '#':       # Skip comment lines.
                continue
            if s[:2] == '\\#':          # Unescape lines starting with '#'.
                s = s[1:]
            s = s.rstrip()
            found = reo.findall(s)
            if found:
                update_section(section) # Store previous section.
                section = found[0].lower()
                contents = []
            else:
                contents.append(s)
        update_section(section)         # Store last section.
        rdr.close()
        if include:
            for s in set(sections) - set(include):
                del sections[s]
        if exclude:
            for s in set(sections) & set(exclude):
                del sections[s]
        attrs = {}
        self.load_sections(sections,attrs)
        if not include:
            # If all sections are loaded mark this file as loaded.
            self.loaded.append(os.path.realpath(fname))
        core.g.document.update_attributes(attrs) # So they are available immediately.
        return True

    def load_sections(self,sections,attrs=None):
        """
        Loads sections dictionary. Each dictionary entry contains a
        list of lines.
        Updates 'attrs' with parsed [attributes] section entries.
        """
        # Delete trailing blank lines from sections.
        for k in sections:
            for i in range(len(sections[k])-1,-1,-1):
                if not sections[k][i]:
                    del sections[k][i]
                elif not self.entries_section(k):
                    break
        # Update new sections.
        for k,v in sections.items():
            if k.startswith('+'):
                # Append section.
                k = k[1:]
                if k in self.sections:
                    self.sections[k] += v
                else:
                    self.sections[k] = v
            else:
                # Replace section.
                self.sections[k] = v
        self.parse_tags()
        # Internally [miscellaneous] section entries are just attributes.
        d = {}
        parse_entries(sections.get('miscellaneous',()), d, unquote=True,
                allow_name_only=True)
        parse_entries(sections.get('attributes',()), d, unquote=True,
                allow_name_only=True)
        update_attrs(self.conf_attrs,d)
        if attrs is not None:
            attrs.update(d)
        d = {}
        parse_entries(sections.get('titles',()),d)
        Title.load(d)
        parse_entries(sections.get('specialcharacters',()),self.specialchars,escape_delimiter=False)
        parse_entries(sections.get('quotes',()),self.quotes)
        self.parse_specialwords()
        self.parse_replacements()
        self.parse_replacements('replacements2')
        self.parse_replacements('replacements3')
        self.parse_specialsections()
        core.g.paragraphs.load(sections)
        core.g.lists.load(sections)
        core.g.blocks.load(sections)
        core.g.tables_OLD.load(sections)
        core.g.tables.load(sections)
        core.g.macros.load(sections.get('macros',()))

    def get_load_dirs(self):
        """
        Return list of well known paths with conf files.
        """
        result = []
        if localapp():
            # Load from folders in asciidoc executable directory.
            result.append(core.g.app_dir)
        else:
            # Load from global configuration directory.
            result.append(core.g.conf_dir)
        # Load configuration files from ~/.asciidoc3 if it exists.
        if core.g.user_dir is not None:
            result.append(core.g.user_dir)
        return result

    def find_in_dirs(self, filename, dirs=None):
        """
        Find conf files from dirs list.
        Return list of found file paths.
        Return empty list if not found in any of the locations.
        """
        result = []
        if dirs is None:
            dirs = self.get_load_dirs()
        for d in dirs:
            f = os.path.join(d,filename)
            if os.path.isfile(f):
                result.append(f)
        return result

    def load_from_dirs(self, filename, dirs=None, include=[]):
        """
        Load conf file from dirs list.
        If dirs not specified try all the well known locations.
        Return False if no file was sucessfully loaded.
        """
        count = 0
        for f in self.find_in_dirs(filename,dirs):
            if self.load_file(f, include=include):
                count += 1
        return count != 0

    def load_backend(self, dirs=None):
        """
        Load the backend configuration files from dirs list.
        If dirs not specified try all the well known locations.
        If a <backend>.conf file was found return it's full path name,
        if not found return None.
        """
        result = None
        if dirs is None:
            dirs = self.get_load_dirs()
        conf = core.g.document.backend + '.conf'
        conf2 = core.g.document.backend + '-' + core.g.document.doctype + '.conf'
        # First search for filter backends.
        for d in [os.path.join(d, 'backends', core.g.document.backend) for d in dirs]:
            if self.load_file(conf,d):
                result = os.path.join(d, conf)
            self.load_file(conf2,d)
        if not result:
            # Search in the normal locations.
            for d in dirs:
                if self.load_file(conf,d):
                    result = os.path.join(d, conf)
                self.load_file(conf2,d)
        return result

    def load_filters(self, dirs=None):
        """
        Load filter configuration files from 'filters' directory in dirs list.
        If dirs not specified try all the well known locations.  Suppress
        loading if a file named __noautoload__ is in same directory as the conf
        file unless the filter has been specified with the --filter
        command-line option (in which case it is loaded unconditionally).
        """
        if dirs is None:
            dirs = self.get_load_dirs()
        for d in dirs:
            # Load filter .conf files.
            filtersdir = os.path.join(d,'filters')
            for dirpath,dirnames,filenames in os.walk(filtersdir):
                subdirs = dirpath[len(filtersdir):].split(os.path.sep)
                # True if processing a filter specified by a --filter option.
                filter_opt = len(subdirs) > 1 and subdirs[1] in self.filters
                if '__noautoload__' not in filenames or filter_opt:
                    for f in filenames:
                        if re.match(r'^.+\.conf$',f):
                            self.load_file(f,dirpath)

    def find_config_dir(self, *dirnames):
        """
        Return path of configuration directory.
        Try all the well known locations.
        Return None if directory not found.
        """
        for d in [os.path.join(d, *dirnames) for d in self.get_load_dirs()]:
            if os.path.isdir(d):
                return d
        return None

    def set_theme_attributes(self):
        theme = core.g.document.attributes.get('theme')
        if theme and 'themedir' not in core.g.document.attributes:
            themedir = self.find_config_dir('themes', theme)
            if themedir:
                core.g.document.attributes['themedir'] = themedir
                iconsdir = os.path.join(themedir, 'icons')
                if 'data-uri' in core.g.document.attributes and os.path.isdir(iconsdir):
                    core.g.document.attributes['iconsdir'] = iconsdir
            else:
                core.g.message.warning('missing theme: %s' % theme, linenos=False)

    def load_miscellaneous(self,d):
        """Set miscellaneous configuration entries from dictionary 'd'."""
        def set_if_int_ge(name, d, min_value):
            if name in d:
                try:
                    val = int(d[name])
                    if not val >= min_value:
                        raise ValueError("not >= " + str(min_value))
                    setattr(self, name, val)
                except ValueError:
                    raise EAsciiDoc('illegal [miscellaneous] %s entry' % name)
        set_if_int_ge('tabsize', d, 0)
        set_if_int_ge('textwidth', d, 1) # DEPRECATED: Old tables only.

        if 'pagewidth' in d:
            try:
                val = float(d['pagewidth'])
                self.pagewidth = val
            except ValueError:
                raise EAsciiDoc('illegal [miscellaneous] pagewidth entry')

        if 'pageunits' in d:
            self.pageunits = d['pageunits']
        if 'outfilesuffix' in d:
            self.outfilesuffix = d['outfilesuffix']
        if 'newline' in d:
            # Convert escape sequences to their character values.
            self.newline = literal_eval('"'+d['newline']+'"')
        if 'subsnormal' in d:
            self.subsnormal = parse_options(d['subsnormal'],SUBS_OPTIONS,
                    'illegal [%s] %s: %s' %
                    ('miscellaneous','subsnormal',d['subsnormal']))
        if 'subsverbatim' in d:
            self.subsverbatim = parse_options(d['subsverbatim'],SUBS_OPTIONS,
                    'illegal [%s] %s: %s' %
                    ('miscellaneous','subsverbatim',d['subsverbatim']))

    def validate(self):
        """Check the configuration for internal consistancy. Called after all
        configuration files have been loaded."""
        core.g.message.linenos = False     # Disable document line numbers.
        # Heuristic to validate that at least one configuration file was loaded.
        if not self.specialchars or not self.tags or not core.g.lists:
            raise EAsciiDoc('incomplete configuration files')
        # Check special characters are only one character long.
        for k in self.specialchars.keys():
            if len(k) != 1:
                raise EAsciiDoc('[specialcharacters] ' \
                                'must be a single character: %s' % k)
        # Check all special words have a corresponding inline macro body.
        for macro in self.specialwords.values():
            if not is_name(macro):
                raise EAsciiDoc('illegal special word name: %s' % macro)
            if not macro in self.sections:
                core.g.message.warning('missing special word macro: [%s]' % macro)
        # Check all text quotes have a corresponding tag.
        for q in list(self.quotes.keys())[:]:
            tag = self.quotes[q]
            if not tag:
                del self.quotes[q]  # Undefine quote.
            else:
                if tag[0] == '#':
                    tag = tag[1:]
                if not tag in self.tags:
                    core.g.message.warning('[quotes] %s missing tag definition: %s' % (q,tag))
        # Check all specialsections section names exist.
        for k,v in list(self.specialsections.items()):
            if not v:
                del self.specialsections[k]
            elif not v in self.sections:
                core.g.message.warning('missing specialsections section: [%s]' % v)
        core.g.paragraphs.validate()
        core.g.lists.validate()
        core.g.blocks.validate()
        core.g.tables_OLD.validate()
        core.g.tables.validate()
        core.g.macros.validate()
        core.g.message.linenos = None

    def entries_section(self,section_name):
        """
        Return True if conf file section contains entries, not a markup
        template.
        """
        for name in self.ENTRIES_SECTIONS:
            if re.match(name,section_name):
                return True
        return False

    def dump(self):
        """Dump configuration to stdout."""
        # Header.
        hdr = ''
        hdr = hdr + '#' + core.g.writer.newline
        hdr = hdr + '# Generated by AsciiDoc %s for %s %s.%s' % \
            (VERSION,core.g.document.backend,core.g.document.doctype,writer.newline)
        t = time.asctime(time.localtime(time.time()))
        hdr = hdr + '# %s%s' % (t,writer.newline)
        hdr = hdr + '#' + core.g.writer.newline
        sys.stdout.write(hdr)
        # Dump special sections.
        # Dump only the configuration file and command-line attributes.
        # [miscellanous] entries are dumped as part of the [attributes].
        d = {}
        d.update(self.conf_attrs)
        d.update(self.cmd_attrs)
        dump_section('attributes',d)
        Title.dump()
        dump_section('quotes',self.quotes)
        dump_section('specialcharacters',self.specialchars)
        d = {}
        for k,v in self.specialwords.items():
            if v in d:
                d[v] = '%s "%s"' % (d[v],k)   # Append word list.
            else:
                d[v] = '"%s"' % k
        dump_section('specialwords',d)
        dump_section('replacements',self.replacements)
        dump_section('replacements2',self.replacements2)
        dump_section('replacements3',self.replacements3)
        dump_section('specialsections',self.specialsections)
        d = {}
        for k,v in self.tags.items():
            d[k] = '%s|%s' % v
        dump_section('tags',d)
        core.g.paragraphs.dump()
        core.g.lists.dump()
        core.g.blocks.dump()
        core.g.tables_OLD.dump()
        core.g.tables.dump()
        core.g.macros.dump()
        # Dump remaining sections.
        for k in self.sections.keys():
            if not self.entries_section(k):
                sys.stdout.write('[%s]%s' % (k,writer.newline))
                for line in self.sections[k]:
                    sys.stdout.write('%s%s' % (line,writer.newline))
                sys.stdout.write(core.g.writer.newline)

    def subs_section(self,section,d):
        """Section attribute substitution using attributes from
        core.g.document.attributes and 'd'.  Lines containing undefinded
        attributes are deleted."""
        if section in self.sections:
            return subs_attrs(self.sections[section],d)
        else:
            core.g.message.warning('missing section: [%s]' % section)
            return ()

    def parse_tags(self):
        """Parse [tags] section entries into self.tags dictionary."""
        d = {}
        parse_entries(self.sections.get('tags',()),d)
        for k,v in list(d.items()):
            if v is None:
                if k in self.tags:
                    del self.tags[k]
            elif v == '':
                self.tags[k] = (None,None)
            else:
                mo = re.match(r'(?P<stag>.*)\|(?P<etag>.*)',v)
                if mo:
                    self.tags[k] = (mo.group('stag'), mo.group('etag'))
                else:
                    raise EAsciiDoc('[tag] %s value malformed' % k)

    def tag(self, name, d=None):
        """Returns (starttag,endtag) tuple named name from configuration file
        [tags] section. Raise error if not found. If a dictionary 'd' is
        passed then merge with document attributes and perform attribute
        substitution on tags."""
        if not name in self.tags:
            raise EAsciiDoc('missing tag: %s' % name)
        stag,etag = self.tags[name]
        if d is not None:
            # TODO: Should we warn if substitution drops a tag?
            if stag:
                stag = subs_attrs(stag,d)
            if etag:
                etag = subs_attrs(etag,d)
        if stag is None: stag = ''
        if etag is None: etag = ''
        return (stag,etag)

    def parse_specialsections(self):
        """Parse specialsections section to self.specialsections dictionary."""
        # TODO: This is virtually the same as parse_replacements() and should
        # be factored to single routine.
        d = {}
        parse_entries(self.sections.get('specialsections',()),d,unquote=True)
        for pat,sectname in list(d.items()):
            pat = strip_quotes(pat)
            if not is_re(pat):
                raise EAsciiDoc('[specialsections] entry ' \
                                'is not a valid regular expression: %s' % pat)
            if sectname is None:
                if pat in self.specialsections:
                    del self.specialsections[pat]
            else:
                self.specialsections[pat] = sectname

    def parse_replacements(self,sect='replacements'):
        """Parse replacements section into self.replacements dictionary."""
        d = collections.OrderedDict()
        parse_entries(self.sections.get(sect,()), d, unquote=True)
        for pat,rep in d.items():
            if not self.set_replacement(pat, rep, getattr(self,sect)):
                raise EAsciiDoc('[%s] entry in %s is not a valid' \
                    ' regular expression: %s' % (sect,self.fname,pat))

    @staticmethod
    def set_replacement(pat, rep, replacements):
        """Add pattern and replacement to replacements dictionary."""
        pat = strip_quotes(pat)
        if not is_re(pat):
            return False
        if rep is None:
            if pat in replacements:
                del replacements[pat]
        else:
            replacements[pat] = strip_quotes(rep)
        return True

    def subs_replacements(self,s,sect='replacements'):
        """Substitute patterns from self.replacements in 's'."""
        result = s
        for pat,rep in getattr(self,sect).items():
            result = re.sub(pat, rep, result)
        return result

    def parse_specialwords(self):
        """Parse special words section into self.specialwords dictionary."""
        reo = re.compile(r'(?:\s|^)(".+?"|[^"\s]+)(?=\s|$)')
        for line in self.sections.get('specialwords',()):
            e = parse_entry(line)
            if not e:
                raise EAsciiDoc('[specialwords] entry in %s is malformed: %s' \
                    % (self.fname,line))
            name,wordlist = e
            if not is_name(name):
                raise EAsciiDoc('[specialwords] name in %s is illegal: %s' \
                    % (self.fname,name))
            if wordlist is None:
                # Undefine all words associated with 'name'.
                for k,v in list(self.specialwords.items()):
                    if v == name:
                        del self.specialwords[k]
            else:
                words = reo.findall(wordlist)
                for word in words:
                    word = strip_quotes(word)
                    if not is_re(word):
                        raise EAsciiDoc('[specialwords] entry in %s ' \
                            'is not a valid regular expression: %s' \
                            % (self.fname,word))
                    self.specialwords[word] = name

    def subs_specialchars(self,s):
        """Perform special character substitution on string 's'."""
        """It may seem like a good idea to escape special characters with a '\'
        character, the reason we don't is because the escape character itself
        then has to be escaped and this makes including code listings
        problematic. Use the predefined {amp},{lt},{gt} attributes instead."""
        result = ''
        for ch in s:
            result = result + self.specialchars.get(ch,ch)
        return result

    def subs_specialchars_reverse(self,s):
        """Perform reverse special character substitution on string 's'."""
        result = s
        for k,v in self.specialchars.items():
            result = result.replace(v, k)
        return result

    def subs_specialwords(self,s):
        """Search for word patterns from self.specialwords in 's' and
        substitute using corresponding macro."""
        result = s
        for word in self.specialwords.keys():
            result = re.sub(word, _subs_specialwords, result)
        return result

    def expand_templates(self,entries):
        """Expand any template::[] macros in a list of section entries."""
        result = []
        for line in entries:
            mo = core.g.macros.match('+',r'template',line)
            if mo:
                s = mo.group('attrlist')
                if s in self.sections:
                    result += self.expand_templates(self.sections[s])
                else:
                    core.g.message.warning('missing section: [%s]' % s)
                    result.append(line)
            else:
                result.append(line)
        return result

    def expand_all_templates(self):
        for k,v in self.sections.items():
            self.sections[k] = self.expand_templates(v)

    def section2tags(self, section, d={}, skipstart=False, skipend=False):
        """Perform attribute substitution on 'section' using document
        attributes plus 'd' attributes. Return tuple (stag,etag) containing
        pre and post | placeholder tags. 'skipstart' and 'skipend' are
        used to suppress substitution."""
        assert section is not None
        if section in self.sections:
            body = self.sections[section]
        else:
            core.g.message.warning('missing section: [%s]' % section)
            body = ()
        # Split macro body into start and end tag core.g.lists.
        stag = []
        etag = []
        in_stag = True
        for s in body:
            if in_stag:
                mo = re.match(r'(?P<stag>.*)\|(?P<etag>.*)',s)
                if mo:
                    if mo.group('stag'):
                        stag.append(mo.group('stag'))
                    if mo.group('etag'):
                        etag.append(mo.group('etag'))
                    in_stag = False
                else:
                    stag.append(s)
            else:
                etag.append(s)
        # Do attribute substitution last so {brkbar} can be used to escape |.
        # But don't do attribute substitution on title -- we've already done it.
        title = d.get('title')
        if title:
            d['title'] = chr(0)  # Replace with unused character.
        if not skipstart:
            stag = subs_attrs(stag, d)
        if not skipend:
            etag = subs_attrs(etag, d)
        # Put the {title} back.
        if title:
            stag = [x.replace(chr(0), title) for x in stag]
            etag = [x.replace(chr(0), title) for x in etag]
            d['title'] = title
        return (stag,etag)



#---------------------------------------------------------------------------
# filter and theme plugin commands.
#---------------------------------------------------------------------------
import shutil, zipfile

def die(msg):
    core.g.message.stderr(msg)
    sys.exit(1)

def extract_zip(zip_file, destdir):
    """
    Unzip Zip file to destination directory.
    Throws exception if error occurs.
    """
    zipo = zipfile.ZipFile(zip_file, 'r')
    try:
        for zi in zipo.infolist():
            outfile = zi.filename
            if not outfile.endswith('/'):
                d, outfile = os.path.split(outfile)
                directory = os.path.normpath(os.path.join(destdir, d))
                if not os.path.isdir(directory):
                    os.makedirs(directory)
                outfile = os.path.join(directory, outfile)
                perms = (zi.external_attr >> 16) & 0o777
                core.g.message.verbose('extracting: %s' % outfile)
                flags = os.O_CREAT | os.O_WRONLY
                if sys.platform == 'win32':
                    flags |= os.O_BINARY
                if perms == 0:
                    # Zip files created under Windows do not include permissions.
                    fh = os.open(outfile, flags)
                else:
                    fh = os.open(outfile, flags, perms)
                try:
                    os.write(fh, zipo.read(zi.filename))
                finally:
                    os.close(fh)
    finally:
        zipo.close()

def create_zip(zip_file, src, skip_hidden=False):
    """
    Create Zip file. If src is a directory archive all contained files and
    subdirectories, if src is a file archive the src file.
    Files and directories names starting with . are skipped
    if skip_hidden is True.
    Throws exception if error occurs.
    """
    zipo = zipfile.ZipFile(zip_file, 'w')
    try:
        if os.path.isfile(src):
            arcname = os.path.basename(src)
            core.g.message.verbose('archiving: %s' % arcname)
            zipo.write(src, arcname, zipfile.ZIP_DEFLATED)
        elif os.path.isdir(src):
            srcdir = os.path.abspath(src)
            if srcdir[-1] != os.path.sep:
                srcdir += os.path.sep
            for root, dirs, files in os.walk(srcdir):
                arcroot = os.path.abspath(root)[len(srcdir):]
                if skip_hidden:
                    for d in dirs[:]:
                        if d.startswith('.'):
                            core.g.message.verbose('skipping: %s' % os.path.join(arcroot, d))
                            del dirs[dirs.index(d)]
                for f in files:
                    filename = os.path.join(root,f)
                    arcname = os.path.join(arcroot, f)
                    if skip_hidden and f.startswith('.'):
                        core.g.message.verbose('skipping: %s' % arcname)
                        continue
                    core.g.message.verbose('archiving: %s' % arcname)
                    zipo.write(filename, arcname, zipfile.ZIP_DEFLATED)
        else:
            raise ValueError('src must specify directory or file: %s' % src)
    finally:
        zipo.close()

class Plugin:
    """
    --filter and --theme option commands.
    """
    CMDS = ('install','remove','list','build')

    type = None     # 'backend', 'filter' or 'theme'.

    @staticmethod
    def get_dir():
        """
        Return plugins path (.asciidoc3/filters or .asciidoc3/themes) in user's
        home direcory or None if user home not defined.
        """
        result = userdir()
        if result:
            result = os.path.join(result, '.asciidoc3', Plugin.type+'s')
        return result

    @staticmethod
    def install(args):
        """
        Install plugin Zip file.
        args[0] is plugin zip file path.
        args[1] is optional destination plugins directory.
        """
        if len(args) not in (1,2):
            die('invalid number of arguments: --%s install %s'
                    % (Plugin.type, ' '.join(args)))
        zip_file = args[0]
        if not os.path.isfile(zip_file):
            die('file not found: %s' % zip_file)
        reo = re.match(r'^\w+',os.path.split(zip_file)[1])
        if not reo:
            die('file name does not start with legal %s name: %s'
                    % (Plugin.type, zip_file))
        plugin_name = reo.group()
        if len(args) == 2:
            plugins_dir = args[1]
            if not os.path.isdir(plugins_dir):
                die('directory not found: %s' % plugins_dir)
        else:
            plugins_dir = Plugin.get_dir()
            if not plugins_dir:
                die('user home directory is not defined')
        plugin_dir = os.path.join(plugins_dir, plugin_name)
        if os.path.exists(plugin_dir):
            die('%s is already installed: %s' % (Plugin.type, plugin_dir))
        try:
            os.makedirs(plugin_dir)
        except Exception as e:
            die('failed to create %s directory: %s' % (Plugin.type, str(e)))
        try:
            extract_zip(zip_file, plugin_dir)
        except Exception as e:
            if os.path.isdir(plugin_dir):
                shutil.rmtree(plugin_dir)
            die('failed to extract %s: %s' % (Plugin.type, str(e)))

    @staticmethod
    def remove(args):
        """
        Delete plugin directory.
        args[0] is plugin name.
        args[1] is optional plugin directory (defaults to ~/.asciidoc3/<plugin_name>).
        """
        if len(args) not in (1,2):
            die('invalid number of arguments: --%s remove %s'
                    % (Plugin.type, ' '.join(args)))
        plugin_name = args[0]
        if not re.match(r'^\w+$',plugin_name):
            die('illegal %s name: %s' % (Plugin.type, plugin_name))
        if len(args) == 2:
            d = args[1]
            if not os.path.isdir(d):
                die('directory not found: %s' % d)
        else:
            d = Plugin.get_dir()
            if not d:
                die('user directory is not defined')
        plugin_dir = os.path.join(d, plugin_name)
        if not os.path.isdir(plugin_dir):
            die('cannot find %s: %s' % (Plugin.type, plugin_dir))
        try:
            core.g.message.verbose('removing: %s' % plugin_dir)
            shutil.rmtree(plugin_dir)
        except Exception as e:
            die('failed to delete %s: %s' % (Plugin.type, str(e)))

    @staticmethod
    def list(args):
        """
        List all plugin directories (global and local).
        """
        for d in [os.path.join(d, Plugin.type+'s') for d in core.g.config.get_load_dirs()]:
            if os.path.isdir(d):
                for f in os.walk(d).next()[1]:
                    core.g.message.stdout(os.path.join(d,f))

    @staticmethod
    def build(args):
        """
        Create plugin Zip file.
        args[0] is Zip file name.
        args[1] is plugin directory.
        """
        if len(args) != 2:
            die('invalid number of arguments: --%s build %s'
                    % (Plugin.type, ' '.join(args)))
        zip_file = args[0]
        plugin_source = args[1]
        if not (os.path.isdir(plugin_source) or os.path.isfile(plugin_source)):
            die('plugin source not found: %s' % plugin_source)
        try:
            create_zip(zip_file, plugin_source, skip_hidden=True)
        except Exception as e:
            die('failed to create %s: %s' % (zip_file, str(e)))


#---------------------------------------------------------------------------
# Application code.
#---------------------------------------------------------------------------
# Constants
# ---------
import core.g

# Global configuration files directory (set by Makefile build target).
CONF_DIR = '/etc/asciidoc3'
HELP_FILE = 'help.conf'     # Default (English) help file.

core.g.init_globals(CONF_DIR, HELP_FILE,
                    os.path.splitext(os.path.basename(__file__))[0],    # progname
                    VERSION)    # asciidoc version

# Globals
# -------
##core.g.document = Document()        # The document being processed.
core.g.config = Config()            # Configuration file reader.
core.g.reader = Reader()            # Input stream line reader.
core.g.writer = Writer()            # Output stream line writer.

core.g.init_globals_phase2()

##core.g.paragraphs = Paragraphs()    # Paragraph definitions.
##core.g.lists = Lists()              # List definitions.
##core.g.blocks = DelimitedBlocks()   # DelimitedBlock definitions.
##core.g.tables_OLD = Tables_OLD()    # Table_OLD definitions.
##core.g.tables = Tables()            # Table definitions.
##core.g.macros = Macros()            # Macro definitions.
##core.g.calloutmap = CalloutMap()    # Coordinates callouts and callout list.
##core.g.trace = Trace()              # Implements trace attribute processing.



### Used by asciidocapi.py ###
# List of message strings written to stderr.
messages = core.g.message.messages


def asciidoc(backend, doctype, confiles, infile, outfile, options):
    """Convert AsciiDoc document to `backend` document of type `doctype`.

    The AsciiDoc document is read from the `infile` file object,
    the translated `backend` content is written to the `outfile` file object.
    """

    def load_conffiles(include=[], exclude=[]):
        """Loads configuration files.

        The configuration files are specified by the `'conf-files'`
        document attribute and on the command-line (closure for `confiles`).
        """
        files = core.g.document.attributes.get('conf-files', '')
        files = [f.strip() for f in files.split('|') if f.strip()]
        files += confiles
        if files:
            for f in files:
                if os.path.isfile(f):
                    core.g.config.load_file(f, include=include, exclude=exclude)
                else:
                    raise EAsciiDoc('missing configuration file: %s' % f)
    try:
        core.g.document.attributes['python'] = sys.executable
        for f in core.g.config.filters:
            if not core.g.config.find_config_dir('filters', f):
                raise EAsciiDoc('missing filter: %s' % f)
        if doctype not in (None, 'article', 'manpage', 'book'):
            raise EAsciiDoc('illegal document type')
        # Set processing options.
        for o in options:
            if o == '-c': core.g.config.dumping = True
            if o == '-s': core.g.config.header_footer = False
            if o == '-v': core.g.config.verbose = True
        core.g.document.update_attributes()
        if '-e' not in options:
            # Load asciidoc.conf files in two passes: the first for attributes
            # the second for everything. This is so that locally set attributes
            # available are in the global asciidoc.conf
            if not core.g.config.load_from_dirs('asciidoc.conf',include=['attributes']):
                raise EAsciiDoc('configuration file asciidoc.conf missing')
            load_conffiles(include=['attributes'])
            core.g.config.load_from_dirs('asciidoc.conf')
            if infile != '<stdin>':
                indir = os.path.dirname(infile)
                core.g.config.load_file('asciidoc.conf', indir,
                                include=['attributes','titles','specialchars'])
        else:
            load_conffiles(include=['attributes','titles','specialchars'])
        core.g.document.update_attributes()
        # Check the infile exists.
        if infile != '<stdin>':
            if not os.path.isfile(infile):
                raise EAsciiDoc('input file %s missing' % infile)
        core.g.document.infile = infile
        AttributeList.initialize()
        # Open input file and parse document header.
        core.g.reader.tabsize = core.g.config.tabsize
        core.g.reader.open(infile)
        has_header = core.g.document.parse_header(doctype,backend)
        # doctype is now finalized.
        core.g.document.attributes['doctype-'+core.g.document.doctype] = ''
        core.g.config.set_theme_attributes()
        # Load backend configuration files.
        if '-e' not in options:
            f = core.g.document.backend + '.conf'
            conffile = core.g.config.load_backend()
            if not conffile:
                raise EAsciiDoc('missing backend conf file: %s' % f)
            core.g.document.attributes['backend-confdir'] = os.path.dirname(conffile)
        # backend is now known.
        core.g.document.attributes['backend-'+core.g.document.backend] = ''
        core.g.document.attributes[core.g.document.backend+'-'+core.g.document.doctype] = ''
        doc_conffiles = []
        if '-e' not in options:
            # Load filters and language file.
            core.g.config.load_filters()
            core.g.document.load_lang()
            if infile != '<stdin>':
                # Load local conf files (files in the source file directory).
                core.g.config.load_file('asciidoc.conf', indir)
                core.g.config.load_backend([indir])
                core.g.config.load_filters([indir])
                # Load document specific configuration files.
                f = os.path.splitext(infile)[0]
                doc_conffiles = [
                        f for f in (f+'.conf', f+'-'+core.g.document.backend+'.conf')
                        if os.path.isfile(f) ]
                for f in doc_conffiles:
                    core.g.config.load_file(f)
        load_conffiles()
        # Build asciidoc-args attribute.
        args = ''
        # Add custom conf file arguments.
        for f in doc_conffiles + confiles:
            args += ' --conf-file "%s"' % f
        # Add command-line and header attributes.
        attrs = {}
        attrs.update(AttributeEntry.attributes)
        attrs.update(core.g.config.cmd_attrs)
        if 'title' in attrs:    # Don't pass the header title.
            del attrs['title']
        for k,v in attrs.items():
            if v:
                args += ' --attribute "%s=%s"' % (k,v)
            else:
                args += ' --attribute "%s"' % k
        core.g.document.attributes['asciidoc-args'] = args
        # Build outfile name.
        if outfile is None:
            outfile = os.path.splitext(infile)[0] + '.' + core.g.document.backend
            if core.g.config.outfilesuffix:
                # Change file extension.
                outfile = os.path.splitext(outfile)[0] + core.g.config.outfilesuffix
        core.g.document.outfile = outfile
        # Document header attributes override conf file attributes.
        core.g.document.attributes.update(AttributeEntry.attributes)
        core.g.document.update_attributes()
        # Set the default embedded icons directory.
        if 'data-uri' in  core.g.document.attributes and not os.path.isdir(core.g.document.attributes['iconsdir']):
            core.g.document.attributes['iconsdir'] = os.path.join(
                     core.g.document.attributes['asciidoc-confdir'], 'images/icons')
        # Configuration is fully loaded.
        core.g.config.expand_all_templates()
        # Check configuration for consistency.
        core.g.config.validate()
        # Initialize top level block name.
        if core.g.document.attributes.get('blockname'):
            AbstractBlock.blocknames.append(core.g.document.attributes['blockname'])
        core.g.paragraphs.initialize()
        core.g.lists.initialize()
        if core.g.config.dumping:
            core.g.config.dump()
        else:
            core.g.writer.newline = core.g.config.newline
            try:
                core.g.writer.open(outfile)
                try:
                    core.g.document.translate(has_header) # Generate the output.
                except Exception as e:
                    print('??? e exception', e)
                finally:
                    core.g.writer.close()
            finally:
                core.g.reader.closefile()
    except KeyboardInterrupt:
        raise
    except Exception as e:
        # Cleanup.
        if outfile and outfile != '<stdout>' and os.path.isfile(outfile):
            os.unlink(outfile)
        # Build and print error description.
        msg = 'FAILED: '
        if core.g.reader.cursor:
            msg = core.g.message.format('', msg)
        if isinstance(e, EAsciiDoc):
            core.g.message.stderr('%s%s' % (msg,str(e)))
        else:
            if __name__ == '__main__':
                core.g.message.stderr(msg+'unexpected error:')
                core.g.message.stderr('-'*60)
                traceback.print_exc(file=sys.stderr)
                core.g.message.stderr('-'*60)
            else:
                core.g.message.stderr('%sunexpected error: %s' % (msg,str(e)))
        sys.exit(1)

def usage(msg=''):
    if msg:
        core.g.message.stderr(msg)
    show_help('default', sys.stderr)

def show_help(topic, f=None):
    """Print help topic to file object f."""
    if f is None:
        f = sys.stdout
    # Select help file.
    lang = core.g.config.cmd_attrs.get('lang')
    if lang and lang != 'en':
        help_file = 'help-' + lang + '.conf'
    else:
        help_file = core.g.help_file
    # Print [topic] section from help file.
    core.g.config.load_from_dirs(help_file)
    if len(core.g.config.sections) == 0:
        # Default to English if specified language help files not found.
        help_file = core.g.help_file
        core.g.config.load_from_dirs(help_file)
    if len(core.g.config.sections) == 0:
        core.g.message.stderr('no help topics found')
        sys.exit(1)
    n = 0
    for k in core.g.config.sections:
        if re.match(re.escape(topic), k):
            n += 1
            lines = core.g.config.sections[k]
    if n == 0:
        if topic != 'topics':
            core.g.message.stderr('help topic not found: [%s] in %s' % (topic, help_file))
        core.g.message.stderr('available help topics: %s' % ', '.join(core.g.config.sections.keys()))
        sys.exit(1)
    elif n > 1:
        core.g.message.stderr('ambiguous help topic: %s' % topic)
    else:
        for line in lines:
            f.write(line + '\n')

### Used by asciidocapi.py ###
def execute(cmd, opts, args):
    """Execute `asciidoc` with command-line options and arguments.

    `cmd` is asciidoc command or asciidoc.py path.
    `opts` and `args` conform to values returned by getopt.getopt().
    Raises SystemExit if an error occurs.

    Doctests:

    1. Check execution:

       >>> import io
       >>> infile = io.StringIO('Hello *{author}*')
       >>> outfile = io.StringIO()
       >>> opts = []
       >>> opts.append(('--backend','html4'))
       >>> opts.append(('--no-header-footer',None))
       >>> opts.append(('--attribute','author=Joe Bloggs'))
       >>> opts.append(('--out-file',outfile))
       >>> execute(__file__, opts, [infile])
       >>> print(outfile.getvalue())
       <p>Hello <strong>Joe Bloggs</strong></p>

       >>>
    """
    core.g.config.init(cmd)
    if len(args) > 1:
        usage('Too many arguments')
        sys.exit(1)
    backend = None
    doctype = None
    confiles = []
    outfile = None
    options = []
    help_option = False
    for o, v in opts:
        if o in ('--help', '-h'):
            help_option = True
        #DEPRECATED: --unsafe option.
        if o == '--unsafe':
            core.g.document.safe = False
        if o == '--safe':
            core.g.document.safe = True
        if o == '--version':
            print('asciidoc %s' % VERSION)
            sys.exit(0)
        if o in ('-b','--backend'):
            backend = v
        if o in ('-c','--dump-conf'):
            options.append('-c')
        if o in ('-d','--doctype'):
            doctype = v
        if o in ('-e','--no-conf'):
            options.append('-e')
        if o in ('-f','--conf-file'):
            confiles.append(v)
        if o == '--filter':
            core.g.config.filters.append(v)
        if o in ('-n','--section-numbers'):
            o = '-a'
            v = 'numbered'
        if o == '--theme':
            o = '-a'
            v = 'theme='+v
        if o in ('-a','--attribute'):
            e = parse_entry(v, allow_name_only=True)
            if not e:
                usage('Illegal -a option: %s' % v)
                sys.exit(1)
            k,v = e
            # A @ suffix denotes don't override existing document attributes.
            if v and v[-1] == '@':
                core.g.document.attributes[k] = v[:-1]
            else:
                core.g.config.cmd_attrs[k] = v
        if o in ('-o','--out-file'):
            outfile = v
        if o in ('-s','--no-header-footer'):
            options.append('-s')
        if o in ('-v','--verbose'):
            options.append('-v')
    if help_option:
        if len(args) == 0:
            show_help('default')
        else:
            show_help(args[-1])
        sys.exit(0)
    if len(args) == 0 and len(opts) == 0:
        usage()
        sys.exit(0)
    if len(args) == 0:
        usage('No source file specified')
        sys.exit(1)
    stdin,stdout = sys.stdin,sys.stdout
    try:
        infile = args[0]
        if infile == '-':
            infile = '<stdin>'
        elif isinstance(infile, str):
            infile = os.path.abspath(infile)
        else:   # Input file is file object from API call.
            sys.stdin = infile
            infile = '<stdin>'
        if outfile == '-':
            outfile = '<stdout>'
        elif isinstance(outfile, str):
            outfile = os.path.abspath(outfile)
        elif outfile is None:
            if infile == '<stdin>':
                outfile = '<stdout>'
        else:   # Output file is file object from API call.
            sys.stdout = outfile
            outfile = '<stdout>'
        # Do the work.
        asciidoc(backend, doctype, confiles, infile, outfile, options)
        if core.g.document.has_errors:
            sys.exit(1)
    finally:
        sys.stdin,sys.stdout = stdin,stdout

if __name__ == '__main__':
    # Process command line options.
    import getopt
    try:
        #DEPRECATED: --unsafe option.
        opts,args = getopt.getopt(sys.argv[1:],
            'a:b:cd:ef:hno:svw:',
            ['attribute=','backend=','conf-file=','doctype=','dump-conf',
            'help','no-conf','no-header-footer','out-file=',
            'section-numbers','verbose','version','safe','unsafe',
            'doctest','filter=','theme='])
    except getopt.GetoptError:
        core.g.message.stderr('illegal command options')
        sys.exit(1)
    opt_names = [opt[0] for opt in opts]
    if '--doctest' in opt_names:
        # Run module doctests.
        import doctest
        options = doctest.NORMALIZE_WHITESPACE + doctest.ELLIPSIS
        failures,tries = doctest.testmod(optionflags=options)
        if failures == 0:
            core.g.message.stderr('All doctests passed')
            sys.exit(0)
        else:
            sys.exit(1)
    # Look for plugin management commands.
    count = 0
    for o,v in opts:
        if o in ('-b','--backend','--filter','--theme'):
            if o == '-b':
                o = '--backend'
            plugin = o[2:]
            cmd = v
            if cmd not in Plugin.CMDS:
                continue
            count += 1
    if count > 1:
        die('--backend, --filter and --theme options are mutually exclusive')
    if count == 1:
        # Execute plugin management commands.
        if not cmd:
            die('missing --%s command' % plugin)
        if cmd not in Plugin.CMDS:
            die('illegal --%s command: %s' % (plugin, cmd))
        Plugin.type = plugin
        core.g.config.init(sys.argv[0])
        core.g.config.verbose = bool(set(['-v','--verbose']) & set(opt_names))
        getattr(Plugin,cmd)(args)
    else:
        # Execute asciidoc.
        try:
            execute(sys.argv[0],opts,args)
        except KeyboardInterrupt:
            sys.exit(1)
