"""Document element classes.

Document element classes parse AsciiDoc reader input and write DocBook writer
output."""

import time
import re

import core.g
from core.util import InsensitiveDict, time_str, date_str, localapp

class Document:

    # doctype property.
    def getdoctype(self):
        return self.attributes.get('doctype')
    def setdoctype(self,doctype):
        self.attributes['doctype'] = doctype
    doctype = property(getdoctype,setdoctype)

    # backend property.
    def getbackend(self):
        return self.attributes.get('backend')
    def setbackend(self,backend):
        if backend:
            backend = self.attributes.get('backend-alias-' + backend, backend)
        self.attributes['backend'] = backend
    backend = property(getbackend,setbackend)

    def __init__(self):
        self.infile = None      # Source file name.
        self.outfile = None     # Output file name.
        self.attributes = InsensitiveDict()
        self.level = 0          # 0 => front matter. 1,2,3 => sect1,2,3.
        self.has_errors = False # Set true if processing errors were flagged.
        self.has_warnings = False # Set true if warnings were flagged.
        self.safe = False       # Default safe mode.
    def update_attributes(self,attrs=None):
        """
        Set implicit attributes and attributes in 'attrs'.
        """
        t = time.time()
        self.attributes['localtime'] = time_str(t)
        self.attributes['localdate'] = date_str(t)
        self.attributes['asciidoc-version'] = core.g.asciidoc_version
        self.attributes['asciidoc-file'] = core.g.app_file
        self.attributes['asciidoc-dir'] = core.g.app_dir
        if localapp():
            self.attributes['asciidoc-confdir'] = core.g.app_dir
        else:
            self.attributes['asciidoc-confdir'] = core.g.conf_dir
        self.attributes['user-dir'] = core.g.user_dir
        if core.g.config.verbose:
            self.attributes['verbose'] = ''
        # Update with configuration file attributes.
        if attrs:
            self.attributes.update(attrs)
        # Update with command-line attributes.
        self.attributes.update(core.g.config.cmd_attrs)
        # Extract miscellaneous configuration section entries from attributes.
        if attrs:
            core.g.config.load_miscellaneous(attrs)
        core.g.config.load_miscellaneous(core.g.config.cmd_attrs)
        self.attributes['newline'] = core.g.config.newline
        # File name related attributes can't be overridden.
        if self.infile is not None:
            if self.infile and os.path.exists(self.infile):
                t = os.path.getmtime(self.infile)
            elif self.infile == '<stdin>':
                t = time.time()
            else:
                t = None
            if t:
                self.attributes['doctime'] = time_str(t)
                self.attributes['docdate'] = date_str(t)
            if self.infile != '<stdin>':
                self.attributes['infile'] = self.infile
                self.attributes['indir'] = os.path.dirname(self.infile)
                self.attributes['docfile'] = self.infile
                self.attributes['docdir'] = os.path.dirname(self.infile)
                self.attributes['docname'] = os.path.splitext(
                        os.path.basename(self.infile))[0]
        if self.outfile:
            if self.outfile != '<stdout>':
                self.attributes['outfile'] = self.outfile
                self.attributes['outdir'] = os.path.dirname(self.outfile)
                if self.infile == '<stdin>':
                    self.attributes['docname'] = os.path.splitext(
                            os.path.basename(self.outfile))[0]
                ext = os.path.splitext(self.outfile)[1][1:]
            elif core.g.config.outfilesuffix:
                ext = core.g.config.outfilesuffix[1:]
            else:
                ext = ''
            if ext:
                self.attributes['filetype'] = ext
                self.attributes['filetype-'+ext] = ''
    def load_lang(self):
        """
        Load language configuration file.
        """
        lang = self.attributes.get('lang')
        if lang is None:
            filename = 'lang-en.conf'   # Default language file.
        else:
            filename = 'lang-' + lang + '.conf'
        if core.g.config.load_from_dirs(filename):
            self.attributes['lang'] = lang  # Reinstate new lang attribute.
        else:
            if lang is None:
                # The default language file must exist.
                core.g.message.error('missing conf file: %s' % filename, halt=True)
            else:
                core.g.message.warning('missing language conf file: %s' % filename)
    def set_deprecated_attribute(self,old,new):
        """
        Ensures the 'old' name of an attribute that was renamed to 'new' is
        still honored.
        """
        if self.attributes.get(new) is None:
            if self.attributes.get(old) is not None:
                self.attributes[new] = self.attributes[old]
        else:
            self.attributes[old] = self.attributes[new]
    def consume_attributes_and_comments(self,comments_only=False,noblanks=False):
        """
        Returns True if one or more attributes or comments were consumed.
        If 'noblanks' is True then consumation halts if a blank line is
        encountered.
        """
        result = False
        finished = False
        while not finished:
            finished = True
            if noblanks and not core.g.reader.read_next(): return result
            if core.g.blocks.isnext() and 'skip' in core.g.blocks.current.options:
                result = True
                finished = False
                core.g.blocks.current.translate()
            if noblanks and not core.g.reader.read_next(): return result
            if core.g.macros.isnext() and core.g.macros.current.name == 'comment':
                result = True
                finished = False
                core.g.macros.current.translate()
            if not comments_only:
                if AttributeEntry.isnext():
                    result = True
                    finished = False
                    AttributeEntry.translate()
                if AttributeList.isnext():
                    result = True
                    finished = False
                    AttributeList.translate()
        return result
    def parse_header(self,doctype,backend):
        """
        Parses header, sets corresponding document attributes and finalizes
        document doctype and backend properties.
        Returns False if the document does not have a header.
        'doctype' and 'backend' are the doctype and backend option values
        passed on the command-line, None if no command-line option was not
        specified.
        """
        assert self.level == 0
        # Skip comments and attribute entries that preceed the header.
        self.consume_attributes_and_comments()
        if doctype is not None:
            # Command-line overrides header.
            self.doctype = doctype
        elif self.doctype is None:
            # Was not set on command-line or in document header.
            self.doctype = DEFAULT_DOCTYPE
        # Process document header.
        has_header = (Title.isnext() and Title.level == 0
                      and AttributeList.style() != 'float')
        if self.doctype == 'manpage' and not has_header:
            core.g.message.error('manpage document title is mandatory',halt=True)
        if has_header:
            Header.parse()
        # Command-line entries override header derived entries.
        self.attributes.update(core.g.config.cmd_attrs)
        # DEPRECATED: revision renamed to revnumber.
        self.set_deprecated_attribute('revision','revnumber')
        # DEPRECATED: date renamed to revdate.
        self.set_deprecated_attribute('date','revdate')
        if doctype is not None:
            # Command-line overrides header.
            self.doctype = doctype
        if backend is not None:
            # Command-line overrides header.
            self.backend = backend
        elif self.backend is None:
            # Was not set on command-line or in document header.
            self.backend = DEFAULT_BACKEND
        else:
            # Has been set in document header.
            self.backend = self.backend # Translate alias in header.
        assert self.doctype in ('article','manpage','book'), 'illegal document type'
        return has_header
    def translate(self,has_header):
        if self.doctype == 'manpage':
            # Translate mandatory NAME section.
            if Lex.next() is not Title:
                core.g.message.error('name section expected')
            else:
                Title.translate()
                if Title.level != 1:
                    core.g.message.error('name section title must be at level 1')
                if not isinstance(Lex.next(),Paragraph):
                    core.g.message.error('malformed name section body')
                lines = core.g.reader.read_until(r'^$')
                s = ' '.join(lines)
                mo = re.match(r'^(?P<manname>.*?)\s+-\s+(?P<manpurpose>.*)$',s)
                if not mo:
                    core.g.message.error('malformed name section body')
                self.attributes['manname'] = mo.group('manname').strip()
                self.attributes['manpurpose'] = mo.group('manpurpose').strip()
                names = [s.strip() for s in self.attributes['manname'].split(',')]
                if len(names) > 9:
                    core.g.message.warning('too many manpage names')
                for i,name in enumerate(names):
                    self.attributes['manname%d' % (i+1)] = name
        if has_header:
            # Do postponed substitutions (backend confs have been loaded).
            self.attributes['doctitle'] = Title.dosubs(self.attributes['doctitle'])
            if core.g.config.header_footer:
                hdr = core.g.config.subs_section('header',{})
                core.g.writer.write(hdr,trace='header')
            if 'title' in self.attributes:
                del self.attributes['title']
            self.consume_attributes_and_comments()
            if self.doctype in ('article','book'):
                # Translate 'preamble' (untitled elements between header
                # and first section title).
                if Lex.next() is not Title:
                    stag,etag = core.g.config.section2tags('preamble')
                    core.g.writer.write(stag,trace='preamble open')
                    Section.translate_body()
                    core.g.writer.write(etag,trace='preamble close')
            elif self.doctype == 'manpage' and 'name' in core.g.config.sections:
                core.g.writer.write(core.g.config.subs_section('name',{}), trace='name')
        else:
            self.process_author_names()
            if core.g.config.header_footer:
                hdr = core.g.config.subs_section('header',{})
                core.g.writer.write(hdr,trace='header')
            if Lex.next() is not Title:
                Section.translate_body()
        # Process remaining sections.
        while not core.g.reader.eof():
            if Lex.next() is not Title:
                raise EAsciiDoc('section title expected')
            Section.translate()
        Section.setlevel(0) # Write remaining unwritten section close tags.
        # Substitute document parameters and write document footer.
        if core.g.config.header_footer:
            ftr = core.g.config.subs_section('footer',{})
            core.g.writer.write(ftr,trace='footer')
    def parse_author(self,s):
        """ Return False if the author is malformed."""
        attrs = self.attributes # Alias for readability.
        s = s.strip()
        mo = re.match(r'^(?P<name1>[^<>\s]+)'
                '(\s+(?P<name2>[^<>\s]+))?'
                '(\s+(?P<name3>[^<>\s]+))?'
                '(\s+<(?P<email>\S+)>)?$',s)
        if not mo:
            # Names that don't match the formal specification.
            if s:
                attrs['firstname'] = s
            return
        firstname = mo.group('name1')
        if mo.group('name3'):
            middlename = mo.group('name2')
            lastname = mo.group('name3')
        else:
            middlename = None
            lastname = mo.group('name2')
        firstname = firstname.replace('_',' ')
        if middlename:
            middlename = middlename.replace('_',' ')
        if lastname:
            lastname = lastname.replace('_',' ')
        email = mo.group('email')
        if firstname:
            attrs['firstname'] = firstname
        if middlename:
            attrs['middlename'] = middlename
        if lastname:
            attrs['lastname'] = lastname
        if email:
            attrs['email'] = email
        return
    def process_author_names(self):
        """ Calculate any missing author related attributes."""
        attrs = self.attributes # Alias for readability.
        firstname = attrs.get('firstname','')
        middlename = attrs.get('middlename','')
        lastname = attrs.get('lastname','')
        author = attrs.get('author')
        initials = attrs.get('authorinitials')
        if author and not (firstname or middlename or lastname):
            self.parse_author(author)
            attrs['author'] = author.replace('_',' ')
            self.process_author_names()
            return
        if not author:
            author = '%s %s %s' % (firstname, middlename, lastname)
            author = author.strip()
            author = re.sub(r'\s+',' ', author)
        if not initials:
            initials = firstname[:1] + middlename[:1] + lastname[:1]
            initials = initials.upper()
        names = [firstname,middlename,lastname,author,initials]
        for i,v in enumerate(names):
            v = core.g.config.subs_specialchars(v)
            v = subs_attrs(v)
            names[i] = v
        firstname,middlename,lastname,author,initials = names
        if firstname:
            attrs['firstname'] = firstname
        if middlename:
            attrs['middlename'] = middlename
        if lastname:
            attrs['lastname'] = lastname
        if author:
            attrs['author'] = author
        if initials:
            attrs['authorinitials'] = initials
        if author:
            attrs['authored'] = ''


class Header:
    """Static methods and attributes only."""
    REV_LINE_RE = r'^(\D*(?P<revnumber>.*?),)?(?P<revdate>.*?)(:\s*(?P<revremark>.*))?$'
    RCS_ID_RE = r'^\$Id: \S+ (?P<revnumber>\S+) (?P<revdate>\S+) \S+ (?P<author>\S+) (\S+ )?\$$'
    def __init__(self):
        raise AssertionError('no class instances allowed')
    @staticmethod
    def parse():
        assert Lex.next() is Title and Title.level == 0
        attrs = core.g.document.attributes # Alias for readability.
        # Postpone title subs until backend conf files have been loaded.
        Title.translate(skipsubs=True)
        attrs['doctitle'] = Title.attributes['title']
        core.g.document.consume_attributes_and_comments(noblanks=True)
        s = core.g.reader.read_next()
        mo = None
        if s:
            # Process first header line after the title that is not a comment
            # or an attribute entry.
            s = core.g.reader.read()
            mo = re.match(Header.RCS_ID_RE,s)
            if not mo:
                core.g.document.parse_author(s)
                core.g.document.consume_attributes_and_comments(noblanks=True)
                if core.g.reader.read_next():
                    # Process second header line after the title that is not a
                    # comment or an attribute entry.
                    s = core.g.reader.read()
                    s = subs_attrs(s)
                    if s:
                        mo = re.match(Header.RCS_ID_RE,s)
                        if not mo:
                            mo = re.match(Header.REV_LINE_RE,s)
            core.g.document.consume_attributes_and_comments(noblanks=True)
        s = attrs.get('revnumber')
        if s:
            mo = re.match(Header.RCS_ID_RE,s)
        if mo:
            revnumber = mo.group('revnumber')
            if revnumber:
                attrs['revnumber'] = revnumber.strip()
            author = mo.groupdict().get('author')
            if author and 'firstname' not in attrs:
                core.g.document.parse_author(author)
            revremark = mo.groupdict().get('revremark')
            if revremark is not None:
                revremark = [revremark]
                # Revision remarks can continue on following lines.
                while core.g.reader.read_next():
                    if core.g.document.consume_attributes_and_comments(noblanks=True):
                        break
                    revremark.append(core.g.reader.read())
                revremark = Lex.subs(revremark,['normal'])
                revremark = '\n'.join(revremark).strip()
                attrs['revremark'] = revremark
            revdate = mo.group('revdate')
            if revdate:
                attrs['revdate'] = revdate.strip()
            elif revnumber or revremark:
                # Set revision date to ensure valid DocBook revision.
                attrs['revdate'] = attrs['docdate']
        core.g.document.process_author_names()
        if core.g.document.doctype == 'manpage':
            # manpage title formatted like mantitle(manvolnum).
            mo = re.match(r'^(?P<mantitle>.*)\((?P<manvolnum>.*)\)$',
                          attrs['doctitle'])
            if not mo:
                core.g.message.error('malformed manpage title')
            else:
                mantitle = mo.group('mantitle').strip()
                mantitle = subs_attrs(mantitle)
                if mantitle is None:
                    core.g.message.error('undefined attribute in manpage title')
                # mantitle is lowered only if in ALL CAPS
                if mantitle == mantitle.upper():
                    mantitle = mantitle.lower()
                attrs['mantitle'] = mantitle;
                attrs['manvolnum'] = mo.group('manvolnum').strip()

class AttributeEntry:
    """Static methods and attributes only."""
    pattern = None
    subs = None
    name = None
    name2 = None
    value = None
    attributes = {}     # Accumulates all the parsed attribute entries.
    def __init__(self):
        raise AssertionError('no class instances allowed')
    @staticmethod
    def isnext():
        result = False  # Assume not next.
        if not AttributeEntry.pattern:
            pat = core.g.document.attributes.get('attributeentry-pattern')
            if not pat:
                core.g.message.error("[attributes] missing 'attributeentry-pattern' entry")
            AttributeEntry.pattern = pat
        line = core.g.reader.read_next()
        if line:
            # Attribute entry formatted like :<name>[.<name2>]:[ <value>]
            mo = re.match(AttributeEntry.pattern,line)
            if mo:
                AttributeEntry.name = mo.group('attrname')
                AttributeEntry.name2 = mo.group('attrname2')
                AttributeEntry.value = mo.group('attrvalue') or ''
                AttributeEntry.value = AttributeEntry.value.strip()
                result = True
        return result
    @staticmethod
    def translate():
        assert Lex.next() is AttributeEntry
        attr = AttributeEntry    # Alias for brevity.
        core.g.reader.read()            # Discard attribute entry from core.g.reader.
        while attr.value.endswith(' +'):
            if not core.g.reader.read_next(): break
            attr.value = attr.value[:-1] + core.g.reader.read().strip()
        if attr.name2 is not None:
            # Configuration file attribute.
            if attr.name2 != '':
                # Section entry attribute.
                section = {}
                # Some sections can have name! syntax.
                if attr.name in ('attributes','miscellaneous') and attr.name2[-1] == '!':
                    section[attr.name] = [attr.name2]
                else:
                   section[attr.name] = ['%s=%s' % (attr.name2,attr.value)]
                core.g.config.load_sections(section)
                core.g.config.load_miscellaneous(core.g.config.conf_attrs)
            else:
                # Markup template section attribute.
                core.g.config.sections[attr.name] = [attr.value]
        else:
            # Normal attribute.
            if attr.name[-1] == '!':
                # Names like name! undefine the attribute.
                attr.name = attr.name[:-1]
                attr.value = None
            # Strip white space and illegal name chars.
            attr.name = re.sub(r'(?u)[^\w\-_]', '', attr.name).lower()
            # Don't override most command-line attributes.
            if attr.name in core.g.config.cmd_attrs \
                    and attr.name not in ('trace','numbered'):
                return
            # Update document attributes with attribute value.
            if attr.value is not None:
                mo = re.match(r'^pass:(?P<attrs>.*)\[(?P<value>.*)\]$', attr.value)
                if mo:
                    # Inline passthrough syntax.
                    attr.subs = mo.group('attrs')
                    attr.value = mo.group('value')  # Passthrough.
                else:
                    # Default substitution.
                    # DEPRECATED: attributeentry-subs
                    attr.subs = core.g.document.attributes.get('attributeentry-subs',
                                'specialcharacters,attributes')
                attr.subs = parse_options(attr.subs, SUBS_OPTIONS,
                            'illegal substitution option')
                attr.value = Lex.subs((attr.value,), attr.subs)
                attr.value = '\n'.join(attr.value)
                core.g.document.attributes[attr.name] = attr.value
            elif attr.name in core.g.document.attributes:
                del core.g.document.attributes[attr.name]
            attr.attributes[attr.name] = attr.value

class AttributeList:
    """Static methods and attributes only."""
    pattern = None
    match = None
    attrs = {}
    def __init__(self):
        raise AssertionError('no class instances allowed')
    @staticmethod
    def initialize():
        if not 'attributelist-pattern' in core.g.document.attributes:
            core.g.message.error("[attributes] missing 'attributelist-pattern' entry")
        AttributeList.pattern = core.g.document.attributes['attributelist-pattern']
    @staticmethod
    def isnext():
        result = False  # Assume not next.
        line = core.g.reader.read_next()
        if line:
            mo = re.match(AttributeList.pattern, line)
            if mo:
                AttributeList.match = mo
                result = True
        return result
    @staticmethod
    def translate():
        assert Lex.next() is AttributeList
        core.g.reader.read()   # Discard attribute list from core.g.reader.
        attrs = {}
        d = AttributeList.match.groupdict()
        for k,v in d.items():
            if v is not None:
                if k == 'attrlist':
                    v = subs_attrs(v)
                    if v:
                        parse_attributes(v, attrs)
                else:
                    AttributeList.attrs[k] = v
        AttributeList.subs(attrs)
        AttributeList.attrs.update(attrs)
    @staticmethod
    def subs(attrs):
        '''Substitute single quoted attribute values normally.'''
        reo = re.compile(r"^'.*'$")
        for k,v in attrs.items():
            if reo.match(str(v)):
                attrs[k] = Lex.subs_1(v[1:-1], core.g.config.subsnormal)
    @staticmethod
    def style():
        return AttributeList.attrs.get('style') or AttributeList.attrs.get('1')
    @staticmethod
    def consume(d={}):
        """Add attribute list to the dictionary 'd' and reset the list."""
        if AttributeList.attrs:
            d.update(AttributeList.attrs)
            AttributeList.attrs = {}
            # Generate option attributes.
            if 'options' in d:
                options = parse_options(d['options'], (), 'illegal option name')
                for option in options:
                    d[option+'-option'] = ''

class BlockTitle:
    """Static methods and attributes only."""
    title = None
    pattern = None
    def __init__(self):
        raise AssertionError('no class instances allowed')
    @staticmethod
    def isnext():
        result = False  # Assume not next.
        line = core.g.reader.read_next()
        if line:
            mo = re.match(BlockTitle.pattern,line)
            if mo:
                BlockTitle.title = mo.group('title')
                result = True
        return result
    @staticmethod
    def translate():
        assert Lex.next() is BlockTitle
        core.g.reader.read()   # Discard title from core.g.reader.
        # Perform title substitutions.
        if not Title.subs:
            Title.subs = core.g.config.subsnormal
        s = Lex.subs((BlockTitle.title,), Title.subs)
        s = core.g.writer.newline.join(s)
        if not s:
            core.g.message.warning('blank block title')
        BlockTitle.title = s
    @staticmethod
    def consume(d={}):
        """If there is a title add it to dictionary 'd' then reset title."""
        if BlockTitle.title:
            d['title'] = BlockTitle.title
            BlockTitle.title = None

class Title:
    """Processes Header and Section titles. Static methods and attributes
    only."""
    # Class variables
    underlines = ('==','--','~~','^^','++') # Levels 0,1,2,3,4.
    subs = ()
    pattern = None
    level = 0
    attributes = {}
    sectname = None
    section_numbers = [0]*len(underlines)
    dump_dict = {}
    linecount = None    # Number of lines in title (1 or 2).
    def __init__(self):
        raise AssertionError('no class instances allowed')
    @staticmethod
    def translate(skipsubs=False):
        """Parse the Title.attributes and Title.level from the core.g.reader. The
        real work has already been done by parse()."""
        assert Lex.next() in (Title,FloatingTitle)
        # Discard title from core.g.reader.
        for i in range(Title.linecount):
            core.g.reader.read()
        Title.setsectname()
        if not skipsubs:
            Title.attributes['title'] = Title.dosubs(Title.attributes['title'])
    @staticmethod
    def dosubs(title):
        """
        Perform title substitutions.
        """
        if not Title.subs:
            Title.subs = core.g.config.subsnormal
        title = Lex.subs((title,), Title.subs)
        title = core.g.writer.newline.join(title)
        if not title:
            core.g.message.warning('blank section title')
        return title
    @staticmethod
    def isnext():
        lines = core.g.reader.read_ahead(2)
        return Title.parse(lines)
    @staticmethod
    def parse(lines):
        """Parse title at start of lines tuple."""
        if len(lines) == 0: return False
        if len(lines[0]) == 0: return False # Title can't be blank.
        # Check for single-line titles.
        result = False
        for level in range(len(Title.underlines)):
            k = 'sect%s' % level
            if k in Title.dump_dict:
                mo = re.match(Title.dump_dict[k], lines[0])
                if mo:
                    Title.attributes = mo.groupdict()
                    Title.level = level
                    Title.linecount = 1
                    result = True
                    break
        if not result:
            # Check for double-line titles.
            if not Title.pattern: return False  # Single-line titles only.
            if len(lines) < 2: return False
            title,ul = lines[:2]
            title_len = column_width(title)
            ul_len = len(ul)
            if ul_len < 2: return False
            # Fast elimination check.
            if ul[:2] not in Title.underlines: return False
            # Length of underline must be within +-3 of title.
            if not ((ul_len-3 < title_len < ul_len+3)
                    # Next test for backward compatibility.
                    or (ul_len-3 < len(title) < ul_len+3)):
                return False
            # Check for valid repetition of underline character pairs.
            s = ul[:2]*((ul_len+1)//2)
            if ul != s[:ul_len]: return False
            # Don't be fooled by back-to-back delimited blocks, require at
            # least one alphanumeric character in title.
            if not re.search(r'(?u)\w',title): return False
            mo = re.match(Title.pattern, title)
            if mo:
                Title.attributes = mo.groupdict()
                Title.level = list(Title.underlines).index(ul[:2])
                Title.linecount = 2
                result = True
        # Check for expected pattern match groups.
        if result:
            if not 'title' in Title.attributes:
                core.g.message.warning('[titles] entry has no <title> group')
                Title.attributes['title'] = lines[0]
            for k,v in list(Title.attributes.items()):
                if v is None: del Title.attributes[k]
        try:
            Title.level += int(core.g.document.attributes.get('leveloffset','0'))
        except:
            pass
        Title.attributes['level'] = str(Title.level)
        return result

    @staticmethod
    def load(entries):
        """Load and validate [titles] section entries dictionary."""
        if 'underlines' in entries:
            errmsg = 'malformed [titles] underlines entry'
            try:
                underlines = parse_list(entries['underlines'])
            except Exception:
                raise EAsciiDoc(errmsg)
            if len(underlines) != len(Title.underlines):
                raise EAsciiDoc(errmsg)
            for s in underlines:
                if len(s) !=2:
                    raise EAsciiDoc(errmsg)
            Title.underlines = tuple(underlines)
            Title.dump_dict['underlines'] = entries['underlines']
        if 'subs' in entries:
            Title.subs = parse_options(entries['subs'], SUBS_OPTIONS,
                'illegal [titles] subs entry')
            Title.dump_dict['subs'] = entries['subs']
        if 'sectiontitle' in entries:
            pat = entries['sectiontitle']
            if not pat or not is_re(pat):
                raise EAsciiDoc('malformed [titles] sectiontitle entry')
            Title.pattern = pat
            Title.dump_dict['sectiontitle'] = pat
        if 'blocktitle' in entries:
            pat = entries['blocktitle']
            if not pat or not is_re(pat):
                raise EAsciiDoc('malformed [titles] blocktitle entry')
            BlockTitle.pattern = pat
            Title.dump_dict['blocktitle'] = pat
        # Load single-line title patterns.
        for k in ('sect0','sect1','sect2','sect3','sect4'):
            if k in entries:
                pat = entries[k]
                if not pat or not is_re(pat):
                    raise EAsciiDoc('malformed [titles] %s entry' % k)
                Title.dump_dict[k] = pat
        # TODO: Check we have either a Title.pattern or at least one
        # single-line title pattern -- can this be done here or do we need
        # check routine like the other block checkers?
    @staticmethod
    def dump():
        dump_section('titles',Title.dump_dict)
    @staticmethod
    def setsectname():
        """
        Set Title section name:
        If the first positional or 'template' attribute is set use it,
        next search for section title in [specialsections],
        if not found use default 'sect<level>' name.
        """
        sectname = AttributeList.attrs.get('1')
        if sectname and sectname != 'float':
            Title.sectname = sectname
        elif 'template' in AttributeList.attrs:
            Title.sectname = AttributeList.attrs['template']
        else:
            for pat,sect in core.g.config.specialsections.items():
                mo = re.match(pat,Title.attributes['title'])
                if mo:
                    title = mo.groupdict().get('title')
                    if title is not None:
                        Title.attributes['title'] = title.strip()
                    else:
                        Title.attributes['title'] = mo.group().strip()
                    Title.sectname = sect
                    break
            else:
                Title.sectname = 'sect%d' % Title.level
    @staticmethod
    def getnumber(level):
        """Return next section number at section 'level' formatted like
        1.2.3.4."""
        number = ''
        for l in range(len(Title.section_numbers)):
            n = Title.section_numbers[l]
            if l == 0:
                continue
            elif l < level:
                number = '%s%d.' % (number, n)
            elif l == level:
                number = '%s%d.' % (number, n + 1)
                Title.section_numbers[l] = n + 1
            elif l > level:
                # Reset unprocessed section levels.
                Title.section_numbers[l] = 0
        return number


class FloatingTitle(Title):
    '''Floated titles are translated differently.'''
    @staticmethod
    def isnext():
        return Title.isnext() and AttributeList.style() == 'float'
    @staticmethod
    def translate():
        assert Lex.next() is FloatingTitle
        Title.translate()
        Section.set_id()
        AttributeList.consume(Title.attributes)
        template = 'floatingtitle'
        if template in core.g.config.sections:
            stag,etag = core.g.config.section2tags(template,Title.attributes)
            core.g.writer.write(stag,trace='floating title')
        else:
            core.g.message.warning('missing template section: [%s]' % template)


class Section:
    """Static methods and attributes only."""
    endtags = []  # Stack of currently open section (level,endtag) tuples.
    ids = []      # List of already used ids.
    def __init__(self):
        raise AssertionError('no class instances allowed')
    @staticmethod
    def savetag(level,etag):
        """Save section end."""
        Section.endtags.append((level,etag))
    @staticmethod
    def setlevel(level):
        """Set document level and write open section close tags up to level."""
        while Section.endtags and Section.endtags[-1][0] >= level:
            core.g.writer.write(Section.endtags.pop()[1],trace='section close')
        core.g.document.level = level
    @staticmethod
    def gen_id(title):
        """
        The normalized value of the id attribute is an NCName according to
        the 'Namespaces in XML' Recommendation:
        NCName          ::=     NCNameStartChar NCNameChar*
        NCNameChar      ::=     NameChar - ':'
        NCNameStartChar ::=     Letter | '_'
        NameChar        ::=     Letter | Digit | '.' | '-' | '_' | ':'
        """
        # Replace non-alpha numeric characters in title with underscores and
        # convert to lower case.
        base_id = re.sub(r'(?u)\W+', '_', title).strip('_').lower()
        if 'ascii-ids' in core.g.document.attributes:
            # Replace non-ASCII characters with ASCII equivalents.
            import unicodedata
            base_id = unicodedata.normalize('NFKD', base_id).encode('ascii','ignore')
        # Prefix the ID name with idprefix attribute or underscore if not
        # defined. Prefix ensures the ID does not clash with existing IDs.
        idprefix = core.g.document.attributes.get('idprefix','_')
        if isinstance(base_id, bytes):
            encoding = core.g.document.attributes.get('encoding', 'utf-8')
            base_id = base_id.decode(encoding)
        base_id = idprefix + base_id
        i = 1
        while True:
            if i == 1:
                id = base_id
            else:
                id = '%s_%d' % (base_id, i)
            if id not in Section.ids:
                Section.ids.append(id)
                return id
            else:
                id = base_id
            i += 1
    @staticmethod
    def set_id():
        if not core.g.document.attributes.get('sectids') is None \
                and 'id' not in AttributeList.attrs:
            # Generate ids for sections.
            AttributeList.attrs['id'] = Section.gen_id(Title.attributes['title'])
    @staticmethod
    def translate():
        assert Lex.next() is Title
        prev_sectname = Title.sectname
        Title.translate()
        if Title.level == 0 and core.g.document.doctype != 'book':
            core.g.message.error('only book doctypes can contain level 0 sections')
        if Title.level > core.g.document.level \
                and 'basebackend-docbook' in core.g.document.attributes \
                and prev_sectname in ('colophon','abstract', \
                    'dedication','glossary','bibliography'):
            core.g.message.error('%s section cannot contain sub-sections' % prev_sectname)
        if Title.level > core.g.document.level+1:
            # Sub-sections of multi-part book level zero Preface and Appendices
            # are meant to be out of sequence.
            if core.g.document.doctype == 'book' \
                    and core.g.document.level == 0 \
                    and Title.level == 2 \
                    and prev_sectname in ('preface','appendix'):
                pass
            else:
                core.g.message.warning('section title out of sequence: '
                    'expected level %d, got level %d'
                    % (core.g.document.level+1, Title.level))
        Section.set_id()
        Section.setlevel(Title.level)
        if 'numbered' in core.g.document.attributes:
            Title.attributes['sectnum'] = Title.getnumber(core.g.document.level)
        else:
            Title.attributes['sectnum'] = ''
        AttributeList.consume(Title.attributes)
        stag,etag = core.g.config.section2tags(Title.sectname,Title.attributes)
        Section.savetag(Title.level,etag)
        core.g.writer.write(stag,trace='section open: level %d: %s' %
                (Title.level, Title.attributes['title']))
        Section.translate_body()
    @staticmethod
    def translate_body(terminator=Title):
        isempty = True
        next = Lex.next()
        while next and next is not terminator:
            if isinstance(terminator,DelimitedBlock) and next is Title:
                core.g.message.error('section title not permitted in delimited block')
            next.translate()
            next = Lex.next()
            isempty = False
        # The section is not empty if contains a subsection.
        if next and isempty and Title.level > core.g.document.level:
            isempty = False
        # Report empty sections if invalid markup will result.
        if isempty:
            if core.g.document.backend == 'docbook' and Title.sectname != 'index':
                core.g.message.error('empty section is not valid')

class AbstractBlock:

    blocknames = [] # Global stack of names for push_blockname() and pop_blockname().

    def __init__(self):
        # Configuration parameter names common to all core.g.blocks.
        self.CONF_ENTRIES = ('delimiter', 'options', 'subs', 'presubs', 'postsubs',
                             'posattrs', 'style', '.*-style', 'template', 'filter')
        self.start = None       # File reader cursor at start delimiter.
        self.defname = None     # Configuration file block definition section name.
        # Configuration parameters.
        self.delimiter = None   # Regular expression matching block delimiter.
        self.delimiter_reo = None # Compiled delimiter.
        self.template = None    # template section entry.
        self.options = ()       # options entry list.
        self.presubs = None     # presubs/subs entry list.
        self.postsubs = ()      # postsubs entry list.
        self.filter = None      # filter entry.
        self.posattrs = ()      # posattrs entry list.
        self.style = None       # Default style.
        self.styles = collections.OrderedDict() # Each entry is a styles dictionary.
        # Before a block is processed it's attributes (from it's
        # attributes list) are merged with the block configuration parameters
        # (by self.merge_attributes()) resulting in the template substitution
        # dictionary (self.attributes) and the block's processing parameters
        # (self.parameters).
        self.attributes = {}
        # The names of block parameters.
        self.PARAM_NAMES = ('template', 'options', 'presubs', 'postsubs', 'filter')
        self.parameters = None
        # Leading delimiter match object.
        self.mo = None

    def short_name(self):
        """ Return the text following the first dash in the section name."""
        i = self.defname.find('-')
        if i == -1:
            return self.defname
        else:
            return self.defname[i+1:]
    def error(self, msg, cursor=None, halt=False):
        core.g.message.error('[%s] %s' % (self.defname,msg), cursor, halt)
    def is_conf_entry(self,param):
        """Return True if param matches an allowed configuration file entry
        name."""
        for s in self.CONF_ENTRIES:
            if re.match('^'+s+'$',param):
                return True
        return False
    def load(self,defname,entries):
        """Update block definition from section 'entries' dictionary."""
        self.defname = defname
        self.update_parameters(entries, self, all=True)
    def update_parameters(self, src, dst=None, all=False):
        """
        Parse processing parameters from src dictionary to dst object.
        dst defaults to self.parameters.
        If all is True then copy src entries that aren't parameter names.
        """
        dst = dst or self.parameters
        msg = '[%s] malformed entry %%s: %%s' % self.defname
        def copy(obj,k,v):
            if isinstance(obj,dict):
                obj[k] = v
            else:
                setattr(obj,k,v)
        for k,v in src.items():
            if not re.match(r'\d+',k) and not is_name(k):
                raise EAsciiDoc(msg % (k,v))
            if k == 'template':
                if not is_name(v):
                    raise EAsciiDoc(msg % (k,v))
                copy(dst,k,v)
            elif k == 'filter':
                copy(dst,k,v)
            elif k == 'options':
                if isinstance(v,str):
                    v = parse_options(v, (), msg % (k,v))
                    # Merge with existing options.
                    v = tuple(set(dst.options).union(set(v)))
                copy(dst,k,v)
            elif k in ('subs','presubs','postsubs'):
                # Subs is an alias for presubs.
                if k == 'subs': k = 'presubs'
                if isinstance(v,str):
                    v = parse_options(v, SUBS_OPTIONS, msg % (k,v))
                copy(dst,k,v)
            elif k == 'delimiter':
                if v and is_re(v):
                    copy(dst,k,v)
                else:
                    raise EAsciiDoc(msg % (k,v))
            elif k == 'style':
                if is_name(v):
                    copy(dst,k,v)
                else:
                    raise EAsciiDoc(msg % (k,v))
            elif k == 'posattrs':
                v = parse_options(v, (), msg % (k,v))
                copy(dst,k,v)
            else:
                mo = re.match(r'^(?P<style>.*)-style$',k)
                if mo:
                    if not v:
                        raise EAsciiDoc(msg % (k,v))
                    style = mo.group('style')
                    if not is_name(style):
                        raise EAsciiDoc(msg % (k,v))
                    d = {}
                    if not parse_named_attributes(v,d):
                        raise EAsciiDoc(msg % (k,v))
                    if 'subs' in d:
                        # Subs is an alias for presubs.
                        d['presubs'] = d['subs']
                        del d['subs']
                    self.styles[style] = d
                elif all or k in self.PARAM_NAMES:
                    copy(dst,k,v) # Derived class specific entries.
    def get_param(self,name,params=None):
        """
        Return named processing parameter from params dictionary.
        If the parameter is not in params look in self.parameters.
        """
        if params and name in params:
            return params[name]
        elif name in self.parameters:
            return self.parameters[name]
        else:
            return None
    def get_subs(self,params=None):
        """
        Return (presubs,postsubs) tuple.
        """
        presubs = self.get_param('presubs',params)
        postsubs = self.get_param('postsubs',params)
        return (presubs,postsubs)
    def dump(self):
        """Write block definition to stdout."""
        write = lambda s: sys.stdout.write('%s%s' % (s,writer.newline))
        write('['+self.defname+']')
        if self.is_conf_entry('delimiter'):
            write('delimiter='+self.delimiter)
        if self.template:
            write('template='+self.template)
        if self.options:
            write('options='+','.join(self.options))
        if self.presubs:
            if self.postsubs:
                write('presubs='+','.join(self.presubs))
            else:
                write('subs='+','.join(self.presubs))
        if self.postsubs:
            write('postsubs='+','.join(self.postsubs))
        if self.filter:
            write('filter='+self.filter)
        if self.posattrs:
            write('posattrs='+','.join(self.posattrs))
        if self.style:
            write('style='+self.style)
        if self.styles:
            for style,d in self.styles.items():
                s = ''
                for k,v in d.items(): s += '%s=%r,' % (k,v)
                write('%s-style=%s' % (style,s[:-1]))

    def validate(self):
        """Validate block after the complete configuration has been loaded."""
        if self.is_conf_entry('delimiter') and not self.delimiter:
            raise EAsciiDoc('[%s] missing delimiter' % self.defname)
        if self.style:
            if not is_name(self.style):
                raise EAsciiDoc('illegal style name: %s' % self.style)
            if not self.style in self.styles:
                if not isinstance(self,List):   # Lists don't have templates.
                    core.g.message.warning('[%s] \'%s\' style not in %s' % (
                        self.defname,self.style,list(self.styles.keys())))
        # Check all styles for missing templates.
        all_styles_have_template = True
        for k,v in self.styles.items():
            t = v.get('template')
            if t and not t in core.g.config.sections:
                # Defer check if template name contains attributes.
                if not re.search(r'{.+}',t):
                    core.g.message.warning('missing template section: [%s]' % t)
            if not t:
                all_styles_have_template = False
        # Check we have a valid template entry or alternatively that all the
        # styles have templates.
        if self.is_conf_entry('template') and not 'skip' in self.options:
            if self.template:
                if not self.template in core.g.config.sections:
                    # Defer check if template name contains attributes.
                    if not re.search(r'{.+}',self.template):
                        core.g.message.warning('missing template section: [%s]'
                                        % self.template)
            elif not all_styles_have_template:
                if not isinstance(self,List): # Lists don't have templates.
                    core.g.message.warning('missing styles templates: [%s]' % self.defname)

    def isnext(self):
        """Check if this block is next in document core.g.reader."""
        result = False
        core.g.reader.skip_blank_lines()
        if core.g.reader.read_next():
            if not self.delimiter_reo:
                # Cache compiled delimiter optimization.
                self.delimiter_reo = re.compile(self.delimiter)
            mo = self.delimiter_reo.match(core.g.reader.read_next())
            if mo:
                self.mo = mo
                result = True
        return result

    def translate(self):
        """Translate block from document core.g.reader."""
        if not self.presubs:
            self.presubs = core.g.config.subsnormal
        if core.g.reader.cursor:
            self.start = core.g.reader.cursor[:]

    def push_blockname(self, blockname=None):
        '''On block entry set the `blockname` attribute.

        Only applies to delimited blocks, lists and core.g.tables.
        '''
        if blockname is None:
            blockname = self.attributes.get('style', self.short_name()).lower()
        core.g.trace('push blockname', blockname)
        self.blocknames.append(blockname)
        core.g.document.attributes['blockname'] = blockname

    def pop_blockname(self):
        '''
        On block exits restore previous (parent) `blockname` attribute or
        undefine it if we're no longer inside a block.
        '''
        assert len(self.blocknames) > 0
        blockname = self.blocknames.pop()
        core.g.trace('pop blockname', blockname)
        if len(self.blocknames) == 0:
            core.g.document.attributes['blockname'] = None
        else:
            core.g.document.attributes['blockname'] = self.blocknames[-1]

    def merge_attributes(self, attrs, params=[]):
        """Merge given attributes to the current block.

        Use the current block's attribute list (`attrs` dictionary) to build a
        dictionary of block processing parameters (`self.parameters`) and tag
        substitution attributes (`self.attributes`).

        1. Copy the default parameters (`self.*`) to `self.parameters`.
        The `self.parameters` are used internally to render the current block.
        Optional `params` array of additional parameters.

        2. Copy `attrs` to `self.attributes`. The `self.attributes` are used
        for template and tag substitution in the current block.

        3. If a style attribute was specified update `self.parameters` with the
        corresponding style parameters; if there are any style parameters
        remaining add them to `self.attributes` (existing attribute list entries
        take precedence).

        4. Set named positional attributes in `self.attributes` if `self.posattrs`
        was specified.

        5. Finally `self.parameters` is updated with any corresponding parameters
        specified `in attrs`.
        """

        def check_array_parameter(param):
            # Check the parameter is a sequence type.
            if not is_array(self.parameters[param]):
                core.g.message.error('malformed %s parameter: %s' %
                        (param, self.parameters[param]))
                # Revert to default value.
                self.parameters[param] = getattr(self,param)

        params = list(self.PARAM_NAMES) + params
        self.attributes = {}
        if self.style:
            # If a default style is defined make it available in the template.
            self.attributes['style'] = self.style
        self.attributes.update(attrs)
        # Calculate dynamic block parameters.
        # Start with configuration file defaults.
        self.parameters = AttrDict()
        for name in params:
            self.parameters[name] = getattr(self,name)
        # Load the selected style attributes.
        posattrs = self.posattrs
        if posattrs and posattrs[0] == 'style':
            # Positional attribute style has highest precedence.
            style = self.attributes.get('1')
        else:
            style = None
        if not style:
            # Use explicit style attribute, fall back to default style.
            style = self.attributes.get('style',self.style)
        if style:
            if not is_name(style):
                core.g.message.error('illegal style name: %s' % style)
                style = self.style
            # Lists have implicit styles and do their own style checks.
            elif style not in self.styles and not isinstance(self,List):
                core.g.message.warning('missing style: [%s]: %s' % (self.defname,style))
                style = self.style
            if style in self.styles:
                self.attributes['style'] = style
                for k,v in self.styles[style].items():
                    if k == 'posattrs':
                        posattrs = v
                    elif k in params:
                        self.parameters[k] = v
                    elif not k in self.attributes:
                        # Style attributes don't take precedence over explicit.
                        self.attributes[k] = v
        # Set named positional attributes.
        for i,v in enumerate(posattrs):
            if str(i+1) in self.attributes:
                self.attributes[v] = self.attributes[str(i+1)]
        # Override config and style attributes with attribute list attributes.
        self.update_parameters(attrs)
        check_array_parameter('options')
        check_array_parameter('presubs')
        check_array_parameter('postsubs')

class AbstractBlocks:
    """List of block definitions."""
    PREFIX = ''         # Conf file section name prefix set in derived classes.
    BLOCK_TYPE = None   # Block type set in derived classes.

    def __init__(self):
        self.current=None
        self.blocks = []        # List of Block objects.
        self.default = None     # Default Block.
        self.delimiters = None  # Combined delimiters regular expression.

    def load(self,sections):
        """Load block definition from 'sections' dictionary."""
        for k in sections.keys():
            if re.match(r'^'+ self.PREFIX + r'.+$',k):
                d = {}
                parse_entries(sections.get(k,()),d)
                for b in self.blocks:
                    if b.defname == k:
                        break
                else:
                    b = self.BLOCK_TYPE()
                    self.blocks.append(b)
                try:
                    b.load(k,d)
                except EAsciiDoc as e:
                    raise EAsciiDoc('[%s] %s' % (k,str(e)))

    def dump(self):
        for b in self.blocks:
            b.dump()

    def isnext(self):
        for b in self.blocks:
            if b.isnext():
                self.current = b
                return True;
        return False

    def validate(self):
        """Validate the block definitions."""
        # Validate delimiters and build combined lists delimiter pattern.
        delimiters = []
        for b in self.blocks:
            assert b.__class__ is self.BLOCK_TYPE
            b.validate()
            if b.delimiter:
                delimiters.append(b.delimiter)
        self.delimiters = re_join(delimiters)


class Paragraph(AbstractBlock):
    def __init__(self):
        AbstractBlock.__init__(self)
        self.text=None          # Text in first line of paragraph.
    def load(self,name,entries):
        AbstractBlock.load(self,name,entries)
    def dump(self):
        AbstractBlock.dump(self)
        write = lambda s: sys.stdout.write('%s%s' % (s,writer.newline))
        write('')
    def isnext(self):
        result = AbstractBlock.isnext(self)
        if result:
            self.text = self.mo.groupdict().get('text')
        return result
    def translate(self):
        AbstractBlock.translate(self)
        attrs = self.mo.groupdict().copy()
        if 'text' in attrs: del attrs['text']
        BlockTitle.consume(attrs)
        AttributeList.consume(attrs)
        self.merge_attributes(attrs)
        core.g.reader.read()   # Discard (already parsed item first line).
        body = core.g.reader.read_until(core.g.paragraphs.terminators)
        if 'skip' in self.parameters.options:
            return
        body = [self.text] + list(body)
        presubs = self.parameters.presubs
        postsubs = self.parameters.postsubs
        if core.g.document.attributes.get('plaintext') is None:
            body = Lex.set_margin(body) # Move body to left margin.
        body = Lex.subs(body,presubs)
        template = self.parameters.template
        template = subs_attrs(template,attrs)
        stag = core.g.config.section2tags(template, self.attributes,skipend=True)[0]
        if self.parameters.filter:
            body = filter_lines(self.parameters.filter,body,self.attributes)
        body = Lex.subs(body,postsubs)
        etag = core.g.config.section2tags(template, self.attributes,skipstart=True)[1]
        # Write start tag, content, end tag.
        core.g.writer.write(dovetail_tags(stag,body,etag),trace='paragraph')

class Paragraphs(AbstractBlocks):
    """List of paragraph definitions."""
    BLOCK_TYPE = Paragraph
    PREFIX = 'paradef-'
    def __init__(self):
        AbstractBlocks.__init__(self)
        self.terminators=None    # List of compiled re's.
    def initialize(self):
        self.terminators = [
                re.compile(r'^\+$|^$'),
                re.compile(AttributeList.pattern),
                re.compile(core.g.blocks.delimiters),
                re.compile(core.g.tables.delimiters),
                re.compile(core.g.tables_OLD.delimiters),
            ]
    def load(self,sections):
        AbstractBlocks.load(self,sections)
    def validate(self):
        AbstractBlocks.validate(self)
        # Check we have a default paragraph definition, put it last in list.
        for b in self.blocks:
            if b.defname == 'paradef-default':
                self.blocks.append(b)
                self.default = b
                self.blocks.remove(b)
                break
        else:
            raise EAsciiDoc('missing section: [paradef-default]')

class List(AbstractBlock):
    NUMBER_STYLES= ('arabic','loweralpha','upperalpha','lowerroman',
                    'upperroman')
    def __init__(self):
        AbstractBlock.__init__(self)
        self.CONF_ENTRIES += ('type','tags')
        self.PARAM_NAMES += ('tags',)
        # listdef conf file parameters.
        self.type=None
        self.tags=None      # Name of listtags-<tags> conf section.
        # Calculated parameters.
        self.tag=None       # Current tags AttrDict.
        self.label=None     # List item label (labeled lists).
        self.text=None      # Text in first line of list item.
        self.index=None     # Matched delimiter 'index' group (numbered lists).
        self.type=None      # List type ('numbered','bulleted','labeled').
        self.ordinal=None   # Current list item ordinal number (1..)
        self.number_style=None # Current numbered list style ('arabic'..)
    def load(self,name,entries):
        AbstractBlock.load(self,name,entries)
    def dump(self):
        AbstractBlock.dump(self)
        write = lambda s: sys.stdout.write('%s%s' % (s,writer.newline))
        write('type='+self.type)
        write('tags='+self.tags)
        write('')
    def validate(self):
        AbstractBlock.validate(self)
        tags = [self.tags]
        tags += [s['tags'] for s in self.styles.values() if 'tags' in s]
        for t in tags:
            if t not in core.g.lists.tags:
                self.error('missing section: [listtags-%s]' % t,halt=True)
    def isnext(self):
        result = AbstractBlock.isnext(self)
        if result:
            self.label = self.mo.groupdict().get('label')
            self.text = self.mo.groupdict().get('text')
            self.index = self.mo.groupdict().get('index')
        return result
    def translate_entry(self):
        assert self.type == 'labeled'
        entrytag = subs_tag(self.tag.entry, self.attributes)
        labeltag = subs_tag(self.tag.label, self.attributes)
        core.g.writer.write(entrytag[0],trace='list entry open')
        core.g.writer.write(labeltag[0],trace='list label open')
        # Write labels.
        while Lex.next() is self:
            core.g.reader.read()   # Discard (already parsed item first line).
            core.g.writer.write_tag(self.tag.term, [self.label],
                             self.presubs, self.attributes,trace='list term')
            if self.text: break
        core.g.writer.write(labeltag[1],trace='list label close')
        # Write item text.
        self.translate_item()
        core.g.writer.write(entrytag[1],trace='list entry close')
    def translate_item(self):
        if self.type == 'callout':
            self.attributes['coids'] = core.g.calloutmap.calloutids(self.ordinal)
        itemtag = subs_tag(self.tag.item, self.attributes)
        core.g.writer.write(itemtag[0],trace='list item open')
        # Write ItemText.
        text = core.g.reader.read_until(core.g.lists.terminators)
        if self.text:
            text = [self.text] + list(text)
        if text:
            core.g.writer.write_tag(self.tag.text, text, self.presubs, self.attributes,trace='list text')
        # Process explicit and implicit list item continuations.
        while True:
            continuation = core.g.reader.read_next() == '+'
            if continuation: core.g.reader.read()  # Discard continuation line.
            while Lex.next() in (BlockTitle,AttributeList):
                # Consume continued element title and attributes.
                Lex.next().translate()
            if not continuation and BlockTitle.title:
                # Titled elements terminate the list.
                break
            next = Lex.next()
            if next in core.g.lists.open:
                break
            elif isinstance(next,List):
                next.translate()
            elif isinstance(next,Paragraph) and 'listelement' in next.options:
                next.translate()
            elif continuation:
                # This is where continued elements are processed.
                if next is Title:
                    core.g.message.error('section title not allowed in list item',halt=True)
                next.translate()
            else:
                break
        core.g.writer.write(itemtag[1],trace='list item close')

    @staticmethod
    def calc_style(index):
        """Return the numbered list style ('arabic'...) of the list item index.
        Return None if unrecognized style."""
        if re.match(r'^\d+[\.>]$', index):
            style = 'arabic'
        elif re.match(r'^[ivx]+\)$', index):
            style = 'lowerroman'
        elif re.match(r'^[IVX]+\)$', index):
            style = 'upperroman'
        elif re.match(r'^[a-z]\.$', index):
            style = 'loweralpha'
        elif re.match(r'^[A-Z]\.$', index):
            style = 'upperalpha'
        else:
            assert False
        return style

    @staticmethod
    def calc_index(index,style):
        """Return the ordinal number of (1...) of the list item index
        for the given list style."""
        def roman_to_int(roman):
            roman = roman.lower()
            digits = {'i':1,'v':5,'x':10}
            result = 0
            for i in range(len(roman)):
                digit = digits[roman[i]]
                # If next digit is larger this digit is negative.
                if i+1 < len(roman) and digits[roman[i+1]] > digit:
                    result -= digit
                else:
                    result += digit
            return result
        index = index[:-1]
        if style == 'arabic':
            ordinal = int(index)
        elif style == 'lowerroman':
            ordinal = roman_to_int(index)
        elif style == 'upperroman':
            ordinal = roman_to_int(index)
        elif style == 'loweralpha':
            ordinal = ord(index) - ord('a') + 1
        elif style == 'upperalpha':
            ordinal = ord(index) - ord('A') + 1
        else:
            assert False
        return ordinal

    def check_index(self):
        """Check calculated self.ordinal (1,2,...) against the item number
        in the document (self.index) and check the number style is the same as
        the first item (self.number_style)."""
        assert self.type in ('numbered','callout')
        if self.index:
            style = self.calc_style(self.index)
            if style != self.number_style:
                core.g.message.warning('list item style: expected %s got %s' %
                        (self.number_style,style), offset=1)
            ordinal = self.calc_index(self.index,style)
            if ordinal != self.ordinal:
                core.g.message.warning('list item index: expected %s got %s' %
                        (self.ordinal,ordinal), offset=1)

    def check_tags(self):
        """ Check that all necessary tags are present. """
        tags = set(Lists.TAGS)
        if self.type != 'labeled':
            tags = tags.difference(['entry','label','term'])
        missing = tags.difference(list(self.tag.keys()))
        if missing:
            self.error('missing tag(s): %s' % ','.join(missing), halt=True)
    def translate(self):
        AbstractBlock.translate(self)
        if self.short_name() in ('bibliography','glossary','qanda'):
            core.g.message.deprecated('old %s list syntax' % self.short_name())
        core.g.lists.open.append(self)
        attrs = self.mo.groupdict().copy()
        for k in ('label','text','index'):
            if k in attrs: del attrs[k]
        if self.index:
            # Set the numbering style from first list item.
            attrs['style'] = self.calc_style(self.index)
        BlockTitle.consume(attrs)
        AttributeList.consume(attrs)
        self.merge_attributes(attrs,['tags'])
        self.push_blockname()
        if self.type in ('numbered','callout'):
            self.number_style = self.attributes.get('style')
            if self.number_style not in self.NUMBER_STYLES:
                core.g.message.error('illegal numbered list style: %s' % self.number_style)
                # Fall back to default style.
                self.attributes['style'] = self.number_style = self.style
        self.tag = core.g.lists.tags[self.parameters.tags]
        self.check_tags()
        if 'width' in self.attributes:
            # Set horizontal list 'labelwidth' and 'itemwidth' attributes.
            v = str(self.attributes['width'])
            mo = re.match(r'^(\d{1,2})%?$',v)
            if mo:
                labelwidth = int(mo.group(1))
                self.attributes['labelwidth'] = str(labelwidth)
                self.attributes['itemwidth'] = str(100-labelwidth)
            else:
                self.error('illegal attribute value: width="%s"' % v)
        stag,etag = subs_tag(self.tag.list, self.attributes)
        if stag:
            core.g.writer.write(stag,trace='list open')
        self.ordinal = 0
        # Process list till list syntax changes or there is a new title.
        while Lex.next() is self and not BlockTitle.title:
            self.ordinal += 1
            core.g.document.attributes['listindex'] = str(self.ordinal)
            if self.type in ('numbered','callout'):
                self.check_index()
            if self.type in ('bulleted','numbered','callout'):
                core.g.reader.read()   # Discard (already parsed item first line).
                self.translate_item()
            elif self.type == 'labeled':
                self.translate_entry()
            else:
                raise AssertionError('illegal [%s] list type' % self.defname)
        if etag:
            core.g.writer.write(etag,trace='list close')
        if self.type == 'callout':
            core.g.calloutmap.validate(self.ordinal)
            core.g.calloutmap.listclose()
        core.g.lists.open.pop()
        if len(core.g.lists.open):
            core.g.document.attributes['listindex'] = str(core.g.lists.open[-1].ordinal)
        self.pop_blockname()

class Lists(AbstractBlocks):
    """List of List objects."""
    BLOCK_TYPE = List
    PREFIX = 'listdef-'
    TYPES = ('bulleted','numbered','labeled','callout')
    TAGS = ('list', 'entry','item','text', 'label','term')
    def __init__(self):
        AbstractBlocks.__init__(self)
        self.open = []  # A stack of the current and parent core.g.lists.
        self.tags={}    # List tags dictionary. Each entry is a tags AttrDict.
        self.terminators=None    # List of compiled re's.
    def initialize(self):
        self.terminators = [
                re.compile(r'^\+$|^$'),
                re.compile(AttributeList.pattern),
                re.compile(core.g.lists.delimiters),
                re.compile(core.g.blocks.delimiters),
                re.compile(core.g.tables.delimiters),
                re.compile(core.g.tables_OLD.delimiters),
            ]
    def load(self,sections):
        AbstractBlocks.load(self,sections)
        self.load_tags(sections)
    def load_tags(self,sections):
        """
        Load listtags-* conf file sections to self.tags.
        """
        for section in sections.keys():
            mo = re.match(r'^listtags-(?P<name>\w+)$',section)
            if mo:
                name = mo.group('name')
                if name in self.tags:
                    d = self.tags[name]
                else:
                    d = AttrDict()
                parse_entries(sections.get(section,()),d)
                for k in d.keys():
                    if k not in self.TAGS:
                        core.g.message.warning('[%s] contains illegal list tag: %s' %
                                (section,k))
                self.tags[name] = d
    def validate(self):
        AbstractBlocks.validate(self)
        for b in self.blocks:
            # Check list has valid type.
            if not b.type in Lists.TYPES:
                raise EAsciiDoc('[%s] illegal type' % b.defname)
            b.validate()
    def dump(self):
        AbstractBlocks.dump(self)
        for k,v in self.tags.items():
            dump_section('listtags-'+k, v)


class DelimitedBlock(AbstractBlock):
    def __init__(self):
        AbstractBlock.__init__(self)
    def load(self,name,entries):
        AbstractBlock.load(self,name,entries)
    def dump(self):
        AbstractBlock.dump(self)
        write = lambda s: sys.stdout.write('%s%s' % (s,writer.newline))
        write('')
    def isnext(self):
        return AbstractBlock.isnext(self)
    def translate(self):
        AbstractBlock.translate(self)
        core.g.reader.read()   # Discard delimiter.
        self.merge_attributes(AttributeList.attrs)
        if not 'skip' in self.parameters.options:
            BlockTitle.consume(self.attributes)
            AttributeList.consume()
        self.push_blockname()
        options = self.parameters.options
        if 'skip' in options:
            core.g.reader.read_until(self.delimiter,same_file=True)
        elif safe() and self.defname == 'blockdef-backend':
            core.g.message.unsafe('Backend Block')
            core.g.reader.read_until(self.delimiter,same_file=True)
        else:
            template = self.parameters.template
            template = subs_attrs(template,self.attributes)
            name = self.short_name()+' block'
            if 'sectionbody' in options:
                # The body is treated like a section body.
                stag,etag = core.g.config.section2tags(template,self.attributes)
                core.g.writer.write(stag,trace=name+' open')
                Section.translate_body(self)
                core.g.writer.write(etag,trace=name+' close')
            else:
                stag = core.g.config.section2tags(template,self.attributes,skipend=True)[0]
                body = core.g.reader.read_until(self.delimiter,same_file=True)
                presubs = self.parameters.presubs
                postsubs = self.parameters.postsubs
                body = Lex.subs(body,presubs)
                if self.parameters.filter:
                    body = filter_lines(self.parameters.filter,body,self.attributes)
                body = Lex.subs(body,postsubs)
                # Write start tag, content, end tag.
                etag = core.g.config.section2tags(template,self.attributes,skipstart=True)[1]
                core.g.writer.write(dovetail_tags(stag,body,etag),trace=name)
            core.g.trace(self.short_name()+' block close',etag)
        if core.g.reader.eof():
            self.error('missing closing delimiter',self.start)
        else:
            delimiter = core.g.reader.read()   # Discard delimiter line.
            assert re.match(self.delimiter,delimiter)
        self.pop_blockname()

class DelimitedBlocks(AbstractBlocks):
    """List of delimited core.g.blocks."""
    BLOCK_TYPE = DelimitedBlock
    PREFIX = 'blockdef-'
    def __init__(self):
        AbstractBlocks.__init__(self)
    def load(self,sections):
        """Update blocks defined in 'sections' dictionary."""
        AbstractBlocks.load(self,sections)
    def validate(self):
        AbstractBlocks.validate(self)

class Column:
    """Table column."""
    def __init__(self, width=None, align_spec=None, style=None):
        self.width = width or '1'
        self.halign, self.valign = Table.parse_align_spec(align_spec)
        self.style = style      # Style name or None.
        # Calculated attribute values.
        self.abswidth = None    # 1..   (page units).
        self.pcwidth = None     # 1..99 (percentage).

class Cell:
    def __init__(self, data, span_spec=None, align_spec=None, style=None):
        self.data = data
        self.span, self.vspan = Table.parse_span_spec(span_spec)
        self.halign, self.valign = Table.parse_align_spec(align_spec)
        self.style = style
        self.reserved = False
    def __repr__(self):
        return '<Cell: %d.%d %s.%s %s "%s">' % (
                self.span, self.vspan,
                self.halign, self.valign,
                self.style or '',
                self.data)
    def clone_reserve(self):
        """Return a clone of self to reserve vertically spanned cell."""
        result = copy.copy(self)
        result.vspan = 1
        result.reserved = True
        return result

class Table(AbstractBlock):
    ALIGN = {'<': 'left', '>': 'right', '^': 'center'}
    VALIGN = {'<': 'top', '>': 'bottom', '^': 'middle'}
    FORMATS = ('psv', 'csv', 'dsv')
    SEPARATORS = dict(
        csv=',',
        dsv=r':|\n',
        # The count and align group matches are not exact.
        psv=r'((?<!\S)((?P<span>[\d.]+)(?P<op>[*+]))?(?P<align>[<\^>.]{,3})?(?P<style>[a-z])?)?\|'
    )
    def __init__(self):
        AbstractBlock.__init__(self)
        self.CONF_ENTRIES += ('format','tags','separator')
        # tabledef conf file parameters.
        self.format='psv'
        self.separator=None
        self.tags=None          # Name of tabletags-<tags> conf section.
        # Calculated parameters.
        self.abswidth=None      # 1..   (page units).
        self.pcwidth = None     # 1..99 (percentage).
        self.rows=[]            # Parsed rows, each row is a list of Cells.
        self.columns=[]         # List of Columns.
    @staticmethod
    def parse_align_spec(align_spec):
        """
        Parse AsciiDoc cell alignment specifier and return 2-tuple with
        horizonatal and vertical alignment names. Unspecified alignments
        set to None.
        """
        result = (None, None)
        if align_spec:
            mo = re.match(r'^([<\^>])?(\.([<\^>]))?$', align_spec)
            if mo:
                result = (Table.ALIGN.get(mo.group(1)),
                          Table.VALIGN.get(mo.group(3)))
        return result
    @staticmethod
    def parse_span_spec(span_spec):
        """
        Parse AsciiDoc cell span specifier and return 2-tuple with horizonatal
        and vertical span counts. Set default values (1,1) if not
        specified.
        """
        result = (None, None)
        if span_spec:
            mo = re.match(r'^(\d+)?(\.(\d+))?$', span_spec)
            if mo:
                result = (mo.group(1) and int(mo.group(1)),
                          mo.group(3) and int(mo.group(3)))
        return (result[0] or 1, result[1] or 1)
    def load(self,name,entries):
        AbstractBlock.load(self,name,entries)
    def dump(self):
        AbstractBlock.dump(self)
        write = lambda s: sys.stdout.write('%s%s' % (s,writer.newline))
        write('format='+self.format)
        write('')
    def validate(self):
        AbstractBlock.validate(self)
        if self.format not in Table.FORMATS:
            self.error('illegal format=%s' % self.format,halt=True)
        self.tags = self.tags or 'default'
        tags = [self.tags]
        tags += [s['tags'] for s in self.styles.values() if 'tags' in s]
        for t in tags:
            if t not in core.g.tables.tags:
                self.error('missing section: [tabletags-%s]' % t,halt=True)
        if self.separator:
            # Evaluate escape characters.
            self.separator = literal_eval('"'+self.separator+'"')
        #TODO: Move to class Tables
        # Check global table parameters.
        elif core.g.config.pagewidth is None:
            self.error('missing [miscellaneous] entry: pagewidth')
        elif core.g.config.pageunits is None:
            self.error('missing [miscellaneous] entry: pageunits')
    def validate_attributes(self):
        """Validate and parse table attributes."""
        # Set defaults.
        format = self.format
        tags = self.tags
        separator = self.separator
        abswidth = float(core.g.config.pagewidth)
        pcwidth = 100.0
        for k,v in self.attributes.items():
            if k == 'format':
                if v not in self.FORMATS:
                    self.error('illegal %s=%s' % (k,v))
                else:
                    format = v
            elif k == 'tags':
                if v not in core.g.tables.tags:
                    self.error('illegal %s=%s' % (k,v))
                else:
                    tags = v
            elif k == 'separator':
                separator = v
            elif k == 'width':
                if not re.match(r'^\d{1,3}%$',v) or int(v[:-1]) > 100:
                    self.error('illegal %s=%s' % (k,v))
                else:
                    abswidth = float(v[:-1])/100 * core.g.config.pagewidth
                    pcwidth = float(v[:-1])
        # Calculate separator if it has not been specified.
        if not separator:
            separator = Table.SEPARATORS[format]
        if format == 'csv':
            if len(separator) > 1:
                self.error('illegal csv separator=%s' % separator)
                separator = ','
        else:
            if not is_re(separator):
                self.error('illegal regular expression: separator=%s' %
                        separator)
        self.parameters.format = format
        self.parameters.tags = tags
        self.parameters.separator = separator
        self.abswidth = abswidth
        self.pcwidth = pcwidth
    def get_tags(self,params):
        tags = self.get_param('tags',params)
        assert(tags and tags in core.g.tables.tags)
        return core.g.tables.tags[tags]
    def get_style(self,prefix):
        """
        Return the style dictionary whose name starts with 'prefix'.
        """
        if prefix is None:
            return None
        names = sorted(self.styles.keys())
        for name in names:
            if name.startswith(prefix):
                return self.styles[name]
        else:
            self.error('missing style: %s*' % prefix)
            return None
    def parse_cols(self, cols, halign, valign):
        """
        Build list of column objects from table 'cols', 'halign' and 'valign'
        attributes.
        """
        # [<multiplier>*][<align>][<width>][<style>]
        COLS_RE1 = r'^((?P<count>\d+)\*)?(?P<align>[<\^>.]{,3})?(?P<width>\d+%?)?(?P<style>[a-z]\w*)?$'
        # [<multiplier>*][<width>][<align>][<style>]
        COLS_RE2 = r'^((?P<count>\d+)\*)?(?P<width>\d+%?)?(?P<align>[<\^>.]{,3})?(?P<style>[a-z]\w*)?$'
        reo1 = re.compile(COLS_RE1)
        reo2 = re.compile(COLS_RE2)
        cols = str(cols)
        if re.match(r'^\d+$',cols):
            for i in range(int(cols)):
                self.columns.append(Column())
        else:
            for col in re.split(r'\s*,\s*',cols):
                mo = reo1.match(col)
                if not mo:
                    mo = reo2.match(col)
                if mo:
                    count = int(mo.groupdict().get('count') or 1)
                    for i in range(count):
                        self.columns.append(
                            Column(mo.group('width'), mo.group('align'),
                                   self.get_style(mo.group('style')))
                        )
                else:
                    self.error('illegal column spec: %s' % col,self.start)
        # Set column (and indirectly cell) default alignments.
        for col in self.columns:
            col.halign = col.halign or halign or core.g.document.attributes.get('halign') or 'left'
            col.valign = col.valign or valign or core.g.document.attributes.get('valign') or 'top'
        # Validate widths and calculate missing widths.
        n = 0; percents = 0; props = 0
        for col in self.columns:
            if col.width:
                if col.width[-1] == '%': percents += int(col.width[:-1])
                else: props += int(col.width)
                n += 1
        if percents > 0 and props > 0:
            self.error('mixed percent and proportional widths: %s'
                    % cols,self.start)
        pcunits = percents > 0
        # Fill in missing widths.
        if n < len(self.columns) and percents < 100:
            if pcunits:
                width = float(100 - percents)/float(len(self.columns) - n)
            else:
                width = 1
            for col in self.columns:
                if not col.width:
                    if pcunits:
                        col.width = str(int(width))+'%'
                        percents += width
                    else:
                        col.width = str(width)
                        props += width
        # Calculate column alignment and absolute and percent width values.
        percents = 0
        for col in self.columns:
            if pcunits:
                col.pcwidth = float(col.width[:-1])
            else:
                col.pcwidth = (float(col.width)/props)*100
            col.abswidth = self.abswidth * (col.pcwidth/100)
            if core.g.config.pageunits in ('cm','mm','in','em'):
                col.abswidth = '%.2f' % round(col.abswidth,2)
            else:
                col.abswidth = '%d' % round(col.abswidth)
            percents += col.pcwidth
            col.pcwidth = int(col.pcwidth)
        if round(percents) > 100:
            self.error('total width exceeds 100%%: %s' % cols,self.start)
        elif round(percents) < 100:
            self.error('total width less than 100%%: %s' % cols,self.start)
    def build_colspecs(self):
        """
        Generate column related substitution attributes.
        """
        cols = []
        i = 1
        for col in self.columns:
            colspec = self.get_tags(col.style).colspec
            if colspec:
                self.attributes['halign'] = col.halign
                self.attributes['valign'] = col.valign
                self.attributes['colabswidth'] = col.abswidth
                self.attributes['colpcwidth'] = col.pcwidth
                self.attributes['colnumber'] = str(i)
                s = subs_attrs(colspec, self.attributes)
                if not s:
                    core.g.message.warning('colspec dropped: contains undefined attribute')
                else:
                    cols.append(s)
            i += 1
        if cols:
            self.attributes['colspecs'] = core.g.writer.newline.join(cols)
    def parse_rows(self, text):
        """
        Parse the table source text into self.rows (a list of rows, each row
        is a list of Cells.
        """
        reserved = {}  # Reserved cells generated by rowspans.
        if self.parameters.format in ('psv','dsv'):
            colcount = len(self.columns)
            parsed_cells = self.parse_psv_dsv(text)
            ri = 0  # Current row index 0..
            ci = 0  # Column counter 0..colcount
            row = []
            i = 0
            while True:
                resv = reserved.get(ri) and reserved[ri].get(ci)
                if resv:
                    # We have a cell generated by a previous row span so
                    # process it before continuing with the current parsed
                    # cell.
                    cell = resv
                else:
                    if i >= len(parsed_cells):
                        break   # No more parsed or reserved cells.
                    cell = parsed_cells[i]
                    i += 1
                    if cell.vspan > 1:
                        # Generate ensuing reserved cells spanned vertically by
                        # the current cell.
                        for j in range(1, cell.vspan):
                            if not ri+j in reserved:
                                reserved[ri+j] = {}
                            reserved[ri+j][ci] = cell.clone_reserve()
                ci += cell.span
                if ci <= colcount:
                    row.append(cell)
                if ci >= colcount:
                    self.rows.append(row)
                    ri += 1
                    row = []
                    ci = 0
        elif self.parameters.format == 'csv':
            self.rows = self.parse_csv(text)
        else:
            assert True,'illegal table format'
        # Check for empty rows containing only reserved (spanned) cells.
        for ri,row in enumerate(self.rows):
            empty = True
            for cell in row:
                if not cell.reserved:
                    empty = False
                    break
            if empty:
                core.g.message.warning('table row %d: empty spanned row' % (ri+1))
        # Check that all row spans match.
        for ri,row in enumerate(self.rows):
            row_span = 0
            for cell in row:
                row_span += cell.span
            if ri == 0:
                header_span = row_span
            if row_span < header_span:
                core.g.message.warning('table row %d: does not span all columns' % (ri+1))
            if row_span > header_span:
                core.g.message.warning('table row %d: exceeds columns span' % (ri+1))
    def subs_rows(self, rows, rowtype='body'):
        """
        Return a string of output markup from a list of rows, each row
        is a list of raw data text.
        """
        tags = core.g.tables.tags[self.parameters.tags]
        if rowtype == 'header':
            rtag = tags.headrow
        elif rowtype == 'footer':
            rtag = tags.footrow
        else:
            rtag = tags.bodyrow
        result = []
        stag,etag = subs_tag(rtag,self.attributes)
        for row in rows:
            result.append(stag)
            result += self.subs_row(row,rowtype)
            result.append(etag)
        return core.g.writer.newline.join(result)
    def subs_row(self, row, rowtype):
        """
        Substitute the list of Cells using the data tag.
        Returns a list of marked up table cell elements.
        """
        result = []
        i = 0
        for cell in row:
            if cell.reserved:
                # Skip vertically spanned placeholders.
                i += cell.span
                continue
            if i >= len(self.columns):
                break   # Skip cells outside the header width.
            col = self.columns[i]
            self.attributes['halign'] = cell.halign or col.halign
            self.attributes['valign'] = cell.valign or  col.valign
            self.attributes['colabswidth'] = col.abswidth
            self.attributes['colpcwidth'] = col.pcwidth
            self.attributes['colnumber'] = str(i+1)
            self.attributes['colspan'] = str(cell.span)
            self.attributes['colstart'] = self.attributes['colnumber']
            self.attributes['colend'] = str(i+cell.span)
            self.attributes['rowspan'] = str(cell.vspan)
            self.attributes['morerows'] = str(cell.vspan-1)
            # Fill missing column data with blanks.
            if i > len(self.columns) - 1:
                data = ''
            else:
                data = cell.data
            if rowtype == 'header':
                # Use table style unless overriden by cell style.
                colstyle = cell.style
            else:
                # If the cell style is not defined use the column style.
                colstyle = cell.style or col.style
            tags = self.get_tags(colstyle)
            presubs,postsubs = self.get_subs(colstyle)
            data = [data]
            data = Lex.subs(data, presubs)
            data = filter_lines(self.get_param('filter',colstyle),
                                data, self.attributes)
            data = Lex.subs(data, postsubs)
            if rowtype != 'header':
                ptag = tags.paragraph
                if ptag:
                    stag,etag = subs_tag(ptag,self.attributes)
                    text = '\n'.join(data).strip()
                    data = []
                    for para in re.split(r'\n{2,}',text):
                        data += dovetail_tags([stag],para.split('\n'),[etag])
            if rowtype == 'header':
                dtag = tags.headdata
            elif rowtype == 'footer':
                dtag = tags.footdata
            else:
                dtag = tags.bodydata
            stag,etag = subs_tag(dtag,self.attributes)
            result = result + dovetail_tags([stag],data,[etag])
            i += cell.span
        return result
    def parse_csv(self,text):
        """
        Parse the table source text and return a list of rows, each row
        is a list of Cells.
        """
        import io
        import csv
        rows = []
        rdr = csv.reader(io.StringIO('\n'.join(text)),
                     delimiter=self.parameters.separator, skipinitialspace=True)
        try:
            for row in rdr:
                rows.append([Cell(data) for data in row])
        except Exception:
            self.error('csv parse error: %s' % row)
        return rows
    def parse_psv_dsv(self,text):
        """
        Parse list of PSV or DSV table source text lines and return a list of
        Cells.
        """
        def append_cell(data, span_spec, op, align_spec, style):
            op = op or '+'
            if op == '*':   # Cell multiplier.
                span = Table.parse_span_spec(span_spec)[0]
                for i in range(span):
                    cells.append(Cell(data, '1', align_spec, style))
            elif op == '+': # Column spanner.
                cells.append(Cell(data, span_spec, align_spec, style))
            else:
                self.error('illegal table cell operator')
        text = '\n'.join(text)
        separator = '(?msu)'+self.parameters.separator
        format = self.parameters.format
        start = 0
        span = None
        op = None
        align = None
        style = None
        cells = []
        data = ''
        for mo in re.finditer(separator,text):
            data += text[start:mo.start()]
            if data.endswith('\\'):
                data = data[:-1]+mo.group() # Reinstate escaped separators.
            else:
                append_cell(data, span, op, align, style)
                span = mo.groupdict().get('span')
                op = mo.groupdict().get('op')
                align = mo.groupdict().get('align')
                style = mo.groupdict().get('style')
                if style:
                    style = self.get_style(style)
                data = ''
            start = mo.end()
        # Last cell follows final separator.
        data += text[start:]
        append_cell(data, span, op, align, style)
        # We expect a dummy blank item preceeding first PSV cell.
        if format == 'psv':
            if cells[0].data.strip() != '':
                self.error('missing leading separator: %s' % separator,
                        self.start)
            else:
                cells.pop(0)
        return cells
    def translate(self):
        AbstractBlock.translate(self)
        core.g.reader.read()   # Discard delimiter.
        # Reset instance specific properties.
        self.columns = []
        self.rows = []
        attrs = {}
        BlockTitle.consume(attrs)
        # Mix in document attribute list.
        AttributeList.consume(attrs)
        self.merge_attributes(attrs)
        self.validate_attributes()
        # Add global and calculated configuration parameters.
        self.attributes['pagewidth'] = core.g.config.pagewidth
        self.attributes['pageunits'] = core.g.config.pageunits
        self.attributes['tableabswidth'] = int(self.abswidth)
        self.attributes['tablepcwidth'] = int(self.pcwidth)
        # Read the entire table.
        text = core.g.reader.read_until(self.delimiter)
        if core.g.reader.eof():
            self.error('missing closing delimiter',self.start)
        else:
            delimiter = core.g.reader.read()   # Discard closing delimiter.
            assert re.match(self.delimiter,delimiter)
        if len(text) == 0:
            core.g.message.warning('[%s] table is empty' % self.defname)
            return
        self.push_blockname('table')
        cols = attrs.get('cols')
        if not cols:
            # Calculate column count from number of items in first line.
            if self.parameters.format == 'csv':
                cols = text[0].count(self.parameters.separator) + 1
            else:
                cols = 0
                for cell in self.parse_psv_dsv(text[:1]):
                    cols += cell.span
        self.parse_cols(cols, attrs.get('halign'), attrs.get('valign'))
        # Set calculated attributes.
        self.attributes['colcount'] = len(self.columns)
        self.build_colspecs()
        self.parse_rows(text)
        # The 'rowcount' attribute is used by the experimental LaTeX backend.
        self.attributes['rowcount'] = str(len(self.rows))
        # Generate headrows, footrows, bodyrows.
        # Headrow, footrow and bodyrow data replaces same named attributes in
        # the table markup template. In order to ensure this data does not get
        # a second attribute substitution (which would interfere with any
        # already substituted inline passthroughs) unique placeholders are used
        # (the tab character does not appear elsewhere since it is expanded on
        # input) which are replaced after template attribute substitution.
        headrows = footrows = bodyrows = None
        for option in self.parameters.options:
            self.attributes[option+'-option'] = ''
        if self.rows and 'header' in self.parameters.options:
            headrows = self.subs_rows(self.rows[0:1],'header')
            self.attributes['headrows'] = '\x07headrows\x07'
            self.rows = self.rows[1:]
        if self.rows and 'footer' in self.parameters.options:
            footrows = self.subs_rows( self.rows[-1:], 'footer')
            self.attributes['footrows'] = '\x07footrows\x07'
            self.rows = self.rows[:-1]
        if self.rows:
            bodyrows = self.subs_rows(self.rows)
            self.attributes['bodyrows'] = '\x07bodyrows\x07'
        table = subs_attrs(core.g.config.sections[self.parameters.template],
                           self.attributes)
        table = core.g.writer.newline.join(table)
        # Before we finish replace the table head, foot and body place holders
        # with the real data.
        if headrows:
            table = table.replace('\x07headrows\x07', headrows, 1)
        if footrows:
            table = table.replace('\x07footrows\x07', footrows, 1)
        if bodyrows:
            table = table.replace('\x07bodyrows\x07', bodyrows, 1)
        core.g.writer.write(table,trace='table')
        self.pop_blockname()

class Tables(AbstractBlocks):
    """List of core.g.tables."""
    BLOCK_TYPE = Table
    PREFIX = 'tabledef-'
    TAGS = ('colspec', 'headrow','footrow','bodyrow',
            'headdata','footdata', 'bodydata','paragraph')
    def __init__(self):
        AbstractBlocks.__init__(self)
        # Table tags dictionary. Each entry is a tags dictionary.
        self.tags={}
    def load(self,sections):
        AbstractBlocks.load(self,sections)
        self.load_tags(sections)
    def load_tags(self,sections):
        """
        Load tabletags-* conf file sections to self.tags.
        """
        for section in sections.keys():
            mo = re.match(r'^tabletags-(?P<name>\w+)$',section)
            if mo:
                name = mo.group('name')
                if name in self.tags:
                    d = self.tags[name]
                else:
                    d = AttrDict()
                parse_entries(sections.get(section,()),d)
                for k in d.keys():
                    if k not in self.TAGS:
                        core.g.message.warning('[%s] contains illegal table tag: %s' %
                                (section,k))
                self.tags[name] = d
    def validate(self):
        AbstractBlocks.validate(self)
        # Check we have a default table definition,
        for i in range(len(self.blocks)):
            if self.blocks[i].defname == 'tabledef-default':
                default = self.blocks[i]
                break
        else:
            raise EAsciiDoc('missing section: [tabledef-default]')
        # Propagate defaults to unspecified table parameters.
        for b in self.blocks:
            if b is not default:
                if b.format is None: b.format = default.format
                if b.template is None: b.template = default.template
        # Check tags and propagate default tags.
        if not 'default' in self.tags:
            raise EAsciiDoc('missing section: [tabletags-default]')
        default = self.tags['default']
        for tag in ('bodyrow','bodydata','paragraph'): # Mandatory default tags.
            if tag not in default:
                raise EAsciiDoc('missing [tabletags-default] entry: %s' % tag)
        for t in list(self.tags.values()):
            if t is not default:
                if t.colspec is None: t.colspec = default.colspec
                if t.headrow is None: t.headrow = default.headrow
                if t.footrow is None: t.footrow = default.footrow
                if t.bodyrow is None: t.bodyrow = default.bodyrow
                if t.headdata is None: t.headdata = default.headdata
                if t.footdata is None: t.footdata = default.footdata
                if t.bodydata is None: t.bodydata = default.bodydata
                if t.paragraph is None: t.paragraph = default.paragraph
        # Use body tags if header and footer tags are not specified.
        for t in self.tags.values():
            if not t.headrow: t.headrow = t.bodyrow
            if not t.footrow: t.footrow = t.bodyrow
            if not t.headdata: t.headdata = t.bodydata
            if not t.footdata: t.footdata = t.bodydata
        # Check table definitions are valid.
        for b in self.blocks:
            b.validate()
    def dump(self):
        AbstractBlocks.dump(self)
        for k,v in self.tags.items():
            dump_section('tabletags-'+k, v)

class Macros:
    # Default system macro syntax.
    SYS_RE = r'(?u)^(?P<name>[\\]?\w(\w|-)*?)::(?P<target>\S*?)' + \
             r'(\[(?P<attrlist>.*?)\])$'
    def __init__(self):
        self.macros = []        # List of Macros.
        self.current = None     # The last matched block macro.
        self.passthroughs = []
        # Initialize default system macro.
        m = Macro()
        m.pattern = self.SYS_RE
        m.prefix = '+'
        m.reo = re.compile(m.pattern)
        self.macros.append(m)
    def load(self,entries):
        for entry in entries:
            m = Macro()
            m.load(entry)
            if m.name is None:
                # Delete undefined macro.
                for i,m2 in list(enumerate(self.macros)):
                    if m2.pattern == m.pattern:
                        del self.macros[i]
                        break
                else:
                    core.g.message.warning('unable to delete missing macro: %s' % m.pattern)
            else:
                # Check for duplicates.
                for m2 in self.macros:
                    if m2.pattern == m.pattern:
                        core.g.message.verbose('macro redefinition: %s%s' % (m.prefix,m.name))
                        break
                else:
                    self.macros.append(m)
    def dump(self):
        write = lambda s: sys.stdout.write('%s%s' % (s,writer.newline))
        write('[macros]')
        # Dump all macros except the first (built-in system) macro.
        for m in self.macros[1:]:
            # Escape = in pattern.
            macro = '%s=%s%s' % (m.pattern.replace('=',r'\='), m.prefix, m.name)
            if m.subslist is not None:
                macro += '[' + ','.join(m.subslist) + ']'
            write(macro)
        write('')
    def validate(self):
        # Check all named sections exist.
        if core.g.config.verbose:
            for m in self.macros:
                if m.name and m.prefix != '+':
                    m.section_name()
    def subs(self,text,prefix='',callouts=False):
        # If callouts is True then only callout macros are processed, if False
        # then all non-callout macros are processed.
        result = text
        for m in self.macros:
            if m.prefix == prefix:
                if callouts ^ (m.name != 'callout'):
                    result = m.subs(result)
        return result
    def isnext(self):
        """Return matching macro if block macro is next on core.g.reader."""
        core.g.reader.skip_blank_lines()
        line = core.g.reader.read_next()
        if line:
            for m in self.macros:
                if m.prefix == '#':
                    if m.reo.match(line):
                        self.current = m
                        return m
        return False
    def match(self,prefix,name,text):
        """Return re match object matching 'text' with macro type 'prefix',
        macro name 'name'."""
        for m in self.macros:
            if m.prefix == prefix:
                mo = m.reo.match(text)
                if mo:
                    if m.name == name:
                        return mo
                    if re.match(name, mo.group('name')):
                        return mo
        return None
    def extract_passthroughs(self,text,prefix=''):
        """ Extract the passthrough text and replace with temporary
        placeholders."""
        self.passthroughs = []
        for m in self.macros:
            if m.has_passthrough() and m.prefix == prefix:
                text = m.subs_passthroughs(text, self.passthroughs)
        return text
    def restore_passthroughs(self,text):
        """ Replace passthough placeholders with the original passthrough
        text."""
        for i,v in enumerate(self.passthroughs):
            text = text.replace('\x07'+str(i)+'\x07', self.passthroughs[i])
        return text

class Macro:
    def __init__(self):
        self.pattern = None     # Matching regular expression.
        self.name = ''          # Conf file macro name (None if implicit).
        self.prefix = ''        # '' if inline, '+' if system, '#' if block.
        self.reo = None         # Compiled pattern re object.
        self.subslist = []      # Default subs for macros passtext group.
    def has_passthrough(self):
        return self.pattern.find(r'(?P<passtext>') >= 0
    def section_name(self,name=None):
        """Return macro markup template section name based on macro name and
        prefix.  Return None section not found."""
        assert self.prefix != '+'
        if not name:
            assert self.name
            name = self.name
        if self.prefix == '#':
            suffix = '-blockmacro'
        else:
            suffix = '-inlinemacro'
        if name+suffix in core.g.config.sections:
            return name+suffix
        else:
            core.g.message.warning('missing macro section: [%s]' % (name+suffix))
            return None
    def load(self,entry):
        e = parse_entry(entry)
        if e is None:
            # Only the macro pattern was specified, mark for deletion.
            self.name = None
            self.pattern = entry
            return
        if not is_re(e[0]):
            raise EAsciiDoc('illegal macro regular expression: %s' % e[0])
        pattern, name = e
        if name and name[0] in ('+','#'):
            prefix, name = name[0], name[1:]
        else:
            prefix = ''
        # Parse passthrough subslist.
        mo = re.match(r'^(?P<name>[^[]*)(\[(?P<subslist>.*)\])?$', name)
        name = mo.group('name')
        if name and not is_name(name):
            raise EAsciiDoc('illegal section name in macro entry: %s' % entry)
        subslist = mo.group('subslist')
        if subslist is not None:
            # Parse and validate passthrough subs.
            subslist = parse_options(subslist, SUBS_OPTIONS,
                                 'illegal subs in macro entry: %s' % entry)
        self.pattern = pattern
        self.reo = re.compile(pattern)
        self.prefix = prefix
        self.name = name
        self.subslist = subslist or []

    def subs(self,text):
        def subs_func(mo):
            """Function called to perform macro substitution.
            Uses matched macro regular expression object and returns string
            containing the substituted macro body."""
            # Check if macro reference is escaped.
            if mo.group()[0] == '\\':
                return mo.group()[1:]   # Strip leading backslash.
            d = mo.groupdict()
            # Delete groups that didn't participate in match.
            for k,v in list(d.items()):
                if v is None: del d[k]
            if self.name:
                name = self.name
            else:
                if not 'name' in d:
                    core.g.message.warning('missing macro name group: %s' % mo.re.pattern)
                    return ''
                name = d['name']
            section_name = self.section_name(name)
            if not section_name:
                return ''
            # If we're dealing with a block macro get optional block ID and
            # block title.
            if self.prefix == '#' and self.name != 'comment':
                AttributeList.consume(d)
                BlockTitle.consume(d)
            # Parse macro attributes.
            if 'attrlist' in d:
                if d['attrlist'] in (None,''):
                    del d['attrlist']
                else:
                    if self.prefix == '':
                        # Unescape ] characters in inline core.g.macros.
                        d['attrlist'] = d['attrlist'].replace('\\]',']')
                    parse_attributes(d['attrlist'],d)
                    # Generate option attributes.
                    if 'options' in d:
                        options = parse_options(d['options'], (),
                                '%s: illegal option name' % name)
                        for option in options:
                            d[option+'-option'] = ''
                    # Substitute single quoted attribute values in block core.g.macros.
                    if self.prefix == '#':
                        AttributeList.subs(d)
            if name == 'callout':
                listindex =int(d['index'])
                d['coid'] = core.g.calloutmap.add(listindex)
            # The alt attribute is the first image macro positional attribute.
            if name == 'image' and '1' in d:
                d['alt'] = d['1']
            # Unescape special characters in LaTeX target file names.
            if core.g.document.backend == 'latex' and 'target' in d and d['target']:
                if not '0' in d:
                    d['0'] = d['target']
                d['target']= core.g.config.subs_specialchars_reverse(d['target'])
            # BUG: We've already done attribute substitution on the macro which
            # means that any escaped attribute references are now unescaped and
            # will be substituted by core.g.config.subs_section() below. As a partial
            # fix have withheld {0} from substitution but this kludge doesn't
            # fix it for other attributes containing unescaped references.
            # Passthrough macros don't have this problem.
            a0 = d.get('0')
            if a0:
                d['0'] = chr(0)  # Replace temporarily with unused character.
            body = core.g.config.subs_section(section_name,d)
            if len(body) == 0:
                result = ''
            elif len(body) == 1:
                result = body[0]
            else:
                if self.prefix == '#':
                    result = core.g.writer.newline.join(body)
                else:
                    # Internally processed inline macros use UNIX line
                    # separator.
                    result = '\n'.join(body)
            if a0:
                result = result.replace(chr(0), a0)
            return result

        return self.reo.sub(subs_func, text)

    def translate(self):
        """ Block macro translation."""
        assert self.prefix == '#'
        s = core.g.reader.read()
        before = s
        if self.has_passthrough():
            s = core.g.macros.extract_passthroughs(s,'#')
        s = subs_attrs(s)
        if s:
            s = self.subs(s)
            if self.has_passthrough():
                s = core.g.macros.restore_passthroughs(s)
            if s:
                core.g.trace('macro block',before,s)
                core.g.writer.write(s)

    def subs_passthroughs(self, text, passthroughs):
        """ Replace macro attribute lists in text with placeholders.
        Substitute and append the passthrough attribute lists to the
        passthroughs list."""
        def subs_func(mo):
            """Function called to perform inline macro substitution.
            Uses matched macro regular expression object and returns string
            containing the substituted macro body."""
            # Don't process escaped macro references.
            if mo.group()[0] == '\\':
                return mo.group()
            d = mo.groupdict()
            if not 'passtext' in d:
                core.g.message.warning('passthrough macro %s: missing passtext group' %
                        d.get('name',''))
                return mo.group()
            passtext = d['passtext']
            if re.search('\x07\\d+\x07', passtext):
                core.g.message.warning('nested inline passthrough')
                return mo.group()
            if d.get('subslist'):
                if d['subslist'].startswith(':'):
                    core.g.message.error('block macro cannot occur here: %s' % mo.group(),
                          halt=True)
                subslist = parse_options(d['subslist'], SUBS_OPTIONS,
                          'illegal passthrough macro subs option')
            else:
                subslist = self.subslist
            passtext = Lex.subs_1(passtext,subslist)
            if passtext is None: passtext = ''
            if self.prefix == '':
                # Unescape ] characters in inline core.g.macros.
                passtext = passtext.replace('\\]',']')
            passthroughs.append(passtext)
            # Tabs guarantee the placeholders are unambiguous.
            result = (
                text[mo.start():mo.start('passtext')] +
                '\x07' + str(len(passthroughs)-1) + '\x07' +
                text[mo.end('passtext'):mo.end()]
            )
            return result

        return self.reo.sub(subs_func, text)


class CalloutMap:
    def __init__(self):
        self.comap = {}         # key = list index, value = callouts list.
        self.calloutindex = 0   # Current callout index number.
        self.listnumber = 1     # Current callout list number.
    def listclose(self):
        # Called when callout list is closed.
        self.listnumber += 1
        self.calloutindex = 0
        self.comap = {}
    def add(self,listindex):
        # Add next callout index to listindex map entry. Return the callout id.
        self.calloutindex += 1
        # Append the coindex to a list in the comap dictionary.
        if not listindex in self.comap:
            self.comap[listindex] = [self.calloutindex]
        else:
            self.comap[listindex].append(self.calloutindex)
        return self.calloutid(self.listnumber, self.calloutindex)
    @staticmethod
    def calloutid(listnumber,calloutindex):
        return 'CO%d-%d' % (listnumber,calloutindex)
    def calloutids(self,listindex):
        # Retieve list of callout indexes that refer to listindex.
        if listindex in self.comap:
            result = ''
            for coindex in self.comap[listindex]:
                result += ' ' + self.calloutid(self.listnumber,coindex)
            return result.strip()
        else:
            core.g.message.warning('no callouts refer to list item '+str(listindex))
            return ''
    def validate(self,maxlistindex):
        # Check that all list indexes referenced by callouts exist.
        for listindex in self.comap.keys():
            if listindex > maxlistindex:
                core.g.message.warning('callout refers to non-existent list item '
                        + str(listindex))


#---------------------------------------------------------------------------
# Deprecated old table classes follow.
# Naming convention is an _OLD name suffix.
# These will be removed from future versions of AsciiDoc


def join_lines_OLD(lines):
    """Return a list in which lines terminated with the backslash line
    continuation character are joined."""
    result = []
    s = ''
    continuation = False
    for line in lines:
        if line and line[-1] == '\\':
            s = s + line[:-1]
            continuation = True
            continue
        if continuation:
            result.append(s+line)
            s = ''
            continuation = False
        else:
            result.append(line)
    if continuation:
        result.append(s)
    return result

class Column_OLD:
    """Table column."""
    def __init__(self):
        self.colalign = None    # 'left','right','center'
        self.rulerwidth = None
        self.colwidth = None    # Output width in page units.

class Table_OLD(AbstractBlock):
    COL_STOP = r"(`|'|\.)"  # RE.
    ALIGNMENTS = {'`': 'left', "'": 'right', '.': 'center'}
    FORMATS = ('fixed', 'csv', 'dsv')

    def __init__(self):
        AbstractBlock.__init__(self)
        self.CONF_ENTRIES += ('template','fillchar','format','colspec',
                              'headrow','footrow','bodyrow','headdata',
                              'footdata', 'bodydata')
        # Configuration parameters.
        self.fillchar=None
        self.format=None    # 'fixed','csv','dsv'
        self.colspec=None
        self.headrow=None
        self.footrow=None
        self.bodyrow=None
        self.headdata=None
        self.footdata=None
        self.bodydata=None
        # Calculated parameters.
        self.underline=None     # RE matching current table underline.
        self.isnumeric=False    # True if numeric ruler.
        self.tablewidth=None    # Optional table width scale factor.
        self.columns=[]         # List of Columns.
        # Other.
        self.check_msg=''       # Message set by previous self.validate() call.
    def load(self,name,entries):
        AbstractBlock.load(self,name,entries)
        """Update table definition from section entries in 'entries'."""
        for k,v in entries.items():
            if k == 'fillchar':
                if v and len(v) == 1:
                    self.fillchar = v
                else:
                    raise EAsciiDoc('malformed table fillchar: %s' % v)
            elif k == 'format':
                if v in Table_OLD.FORMATS:
                    self.format = v
                else:
                    raise EAsciiDoc('illegal table format: %s' % v)
            elif k == 'colspec':
                self.colspec = v
            elif k == 'headrow':
                self.headrow = v
            elif k == 'footrow':
                self.footrow = v
            elif k == 'bodyrow':
                self.bodyrow = v
            elif k == 'headdata':
                self.headdata = v
            elif k == 'footdata':
                self.footdata = v
            elif k == 'bodydata':
                self.bodydata = v
    def dump(self):
        AbstractBlock.dump(self)
        write = lambda s: sys.stdout.write('%s%s' % (s,writer.newline))
        write('fillchar='+self.fillchar)
        write('format='+self.format)
        if self.colspec:
            write('colspec='+self.colspec)
        if self.headrow:
            write('headrow='+self.headrow)
        if self.footrow:
            write('footrow='+self.footrow)
        write('bodyrow='+self.bodyrow)
        if self.headdata:
            write('headdata='+self.headdata)
        if self.footdata:
            write('footdata='+self.footdata)
        write('bodydata='+self.bodydata)
        write('')
    def validate(self):
        AbstractBlock.validate(self)
        """Check table definition and set self.check_msg if invalid else set
        self.check_msg to blank string."""
        # Check global table parameters.
        if core.g.config.textwidth is None:
            self.check_msg = 'missing [miscellaneous] textwidth entry'
        elif core.g.config.pagewidth is None:
            self.check_msg = 'missing [miscellaneous] pagewidth entry'
        elif core.g.config.pageunits is None:
            self.check_msg = 'missing [miscellaneous] pageunits entry'
        elif self.headrow is None:
            self.check_msg = 'missing headrow entry'
        elif self.footrow is None:
            self.check_msg = 'missing footrow entry'
        elif self.bodyrow is None:
            self.check_msg = 'missing bodyrow entry'
        elif self.headdata is None:
            self.check_msg = 'missing headdata entry'
        elif self.footdata is None:
            self.check_msg = 'missing footdata entry'
        elif self.bodydata is None:
            self.check_msg = 'missing bodydata entry'
        else:
            # No errors.
            self.check_msg = ''
    def isnext(self):
        return AbstractBlock.isnext(self)
    def parse_ruler(self,ruler):
        """Parse ruler calculating underline and ruler column widths."""
        fc = re.escape(self.fillchar)
        # Strip and save optional tablewidth from end of ruler.
        mo = re.match(r'^(.*'+fc+r'+)([\d\.]+)$',ruler)
        if mo:
            ruler = mo.group(1)
            self.tablewidth = float(mo.group(2))
            self.attributes['tablewidth'] = str(float(self.tablewidth))
        else:
            self.tablewidth = None
            self.attributes['tablewidth'] = '100.0'
        # Guess whether column widths are specified numerically or not.
        if ruler[1] != self.fillchar:
            # If the first column does not start with a fillchar then numeric.
            self.isnumeric = True
        elif ruler[1:] == self.fillchar*len(ruler[1:]):
            # The case of one column followed by fillchars is numeric.
            self.isnumeric = True
        else:
            self.isnumeric = False
        # Underlines must be 3 or more fillchars.
        self.underline = r'^' + fc + r'{3,}$'
        splits = re.split(self.COL_STOP,ruler)[1:]
        # Build self.columns.
        for i in range(0,len(splits),2):
            c = Column_OLD()
            c.colalign = self.ALIGNMENTS[splits[i]]
            s = splits[i+1]
            if self.isnumeric:
                # Strip trailing fillchars.
                s = re.sub(fc+r'+$','',s)
                if s == '':
                    c.rulerwidth = None
                else:
                    try:
                        val = int(s)
                        if not val > 0:
                            raise ValueError('not > 0')
                        c.rulerwidth = val
                    except ValueError:
                        raise EAsciiDoc('malformed ruler: bad width')
            else:   # Calculate column width from inter-fillchar intervals.
                if not re.match(r'^'+fc+r'+$',s):
                    raise EAsciiDoc('malformed ruler: illegal fillchars')
                c.rulerwidth = len(s)+1
            self.columns.append(c)
        # Fill in unspecified ruler widths.
        if self.isnumeric:
            if self.columns[0].rulerwidth is None:
                prevwidth = 1
            for c in self.columns:
                if c.rulerwidth is None:
                    c.rulerwidth = prevwidth
                prevwidth = c.rulerwidth
    def build_colspecs(self):
        """Generate colwidths and colspecs. This can only be done after the
        table arguments have been parsed since we use the table format."""
        self.attributes['cols'] = len(self.columns)
        # Calculate total ruler width.
        totalwidth = 0
        for c in self.columns:
            totalwidth = totalwidth + c.rulerwidth
        if totalwidth <= 0:
            raise EAsciiDoc('zero width table')
        # Calculate marked up colwidths from rulerwidths.
        for c in self.columns:
            # Convert ruler width to output page width.
            width = float(c.rulerwidth)
            if self.format == 'fixed':
                if self.tablewidth is None:
                    # Size proportional to ruler width.
                    colfraction = width/config.textwidth
                else:
                    # Size proportional to page width.
                    colfraction = width/totalwidth
            else:
                    # Size proportional to page width.
                colfraction = width/totalwidth
            c.colwidth = colfraction * core.g.config.pagewidth # To page units.
            if self.tablewidth is not None:
                c.colwidth = c.colwidth * self.tablewidth   # Scale factor.
                if self.tablewidth > 1:
                    c.colwidth = c.colwidth/100 # tablewidth is in percent.
        # Build colspecs.
        if self.colspec:
            cols = []
            i = 0
            for c in self.columns:
                i += 1
                self.attributes['colalign'] = c.colalign
                self.attributes['colwidth'] = str(int(c.colwidth))
                self.attributes['colnumber'] = str(i + 1)
                s = subs_attrs(self.colspec,self.attributes)
                if not s:
                    core.g.message.warning('colspec dropped: contains undefined attribute')
                else:
                    cols.append(s)
            self.attributes['colspecs'] = core.g.writer.newline.join(cols)
    def split_rows(self,rows):
        """Return a two item tuple containing a list of lines up to but not
        including the next underline (continued lines are joined ) and the
        tuple of all lines after the underline."""
        reo = re.compile(self.underline)
        i = 0
        while not reo.match(rows[i]):
            i = i+1
        if i == 0:
            raise EAsciiDoc('missing table rows')
        if i >= len(rows):
            raise EAsciiDoc('closing [%s] underline expected' % self.defname)
        return (join_lines_OLD(rows[:i]), rows[i+1:])
    def parse_rows(self, rows, rtag, dtag):
        """Parse rows list using the row and data tags. Returns a substituted
        list of output lines."""
        result = []
        # Source rows are parsed as single block, rather than line by line, to
        # allow the CSV reader to handle multi-line rows.
        if self.format == 'fixed':
            rows = self.parse_fixed(rows)
        elif self.format == 'csv':
            rows = self.parse_csv(rows)
        elif self.format == 'dsv':
            rows = self.parse_dsv(rows)
        else:
            assert True,'illegal table format'
        # Substitute and indent all data in all rows.
        stag,etag = subs_tag(rtag,self.attributes)
        for row in rows:
            result.append('  '+stag)
            for data in self.subs_row(row,dtag):
                result.append('    '+data)
            result.append('  '+etag)
        return result
    def subs_row(self, data, dtag):
        """Substitute the list of source row data elements using the data tag.
        Returns a substituted list of output table data items."""
        result = []
        if len(data) < len(self.columns):
            core.g.message.warning('fewer row data items then table columns')
        if len(data) > len(self.columns):
            core.g.message.warning('more row data items than table columns')
        for i in range(len(self.columns)):
            if i > len(data) - 1:
                d = ''  # Fill missing column data with blanks.
            else:
                d = data[i]
            c = self.columns[i]
            self.attributes['colalign'] = c.colalign
            self.attributes['colwidth'] = str(int(c.colwidth))
            self.attributes['colnumber'] = str(i + 1)
            stag,etag = subs_tag(dtag,self.attributes)
            # Insert AsciiDoc line break (' +') where row data has newlines
            # ('\n').  This is really only useful when the table format is csv
            # and the output markup is HTML. It's also a bit dubious in that it
            # assumes the user has not modified the shipped line break pattern.
            subs = self.get_subs()[0]
            if 'replacements2' in subs:
                # Insert line breaks in cell data.
                d = re.sub(r'(?m)\n',r' +\n',d)
                d = d.split('\n')    # So core.g.writer.newline is written.
            else:
                d = [d]
            result = result + [stag] + Lex.subs(d,subs) + [etag]
        return result
    def parse_fixed(self,rows):
        """Parse the list of source table rows. Each row item in the returned
        list contains a list of cell data elements."""
        result = []
        for row in rows:
            data = []
            start = 0
            # build a representation
            for c in self.columns:
                end = start + c.rulerwidth
                if c is self.columns[-1]:
                    # Text in last column can continue forever.
                    # Use the encoded string to slice, but convert back
                    # to plain string before further processing
                    data.append(row[start:].strip())
                else:
                    data.append(row[start:end].strip())
                start = end
            result.append(data)
        return result
    def parse_csv(self,rows):
        """Parse the list of source table rows. Each row item in the returned
        list contains a list of cell data elements."""
        import io
        import csv
        result = []
        rdr = csv.reader(io.StringIO('\n'.join(rows)),
            skipinitialspace=True)
        try:
            for row in rdr:
                result.append(row)
        except Exception:
            raise EAsciiDoc('csv parse error: %s' % row)
        return result
    def parse_dsv(self,rows):
        """Parse the list of source table rows. Each row item in the returned
        list contains a list of cell data elements."""
        separator = self.attributes.get('separator',':')
        separator = literal_eval('"'+separator+'"')
        if len(separator) != 1:
            raise EAsciiDoc('malformed dsv separator: %s' % separator)
        # TODO If separator is preceeded by an odd number of backslashes then
        # it is escaped and should not delimit.
        result = []
        for row in rows:
            # Skip blank lines
            if row == '': continue
            # Unescape escaped characters.
            row = literal_eval('"'+row.replace('"','\\"')+'"')
            data = row.split(separator)
            data = [s.strip() for s in data]
            result.append(data)
        return result
    def translate(self):
        core.g.message.deprecated('old tables syntax')
        AbstractBlock.translate(self)
        # Reset instance specific properties.
        self.underline = None
        self.columns = []
        attrs = {}
        BlockTitle.consume(attrs)
        # Add relevant globals to table substitutions.
        attrs['pagewidth'] = str(core.g.config.pagewidth)
        attrs['pageunits'] = core.g.config.pageunits
        # Mix in document attribute list.
        AttributeList.consume(attrs)
        # Validate overridable attributes.
        for k,v in attrs.items():
            if k == 'format':
                if v not in self.FORMATS:
                    raise EAsciiDoc('illegal [%s] %s: %s' % (self.defname,k,v))
                self.format = v
            elif k == 'tablewidth':
                try:
                    self.tablewidth = float(attrs['tablewidth'])
                except Exception:
                    raise EAsciiDoc('illegal [%s] %s: %s' % (self.defname,k,v))
        self.merge_attributes(attrs)
        # Parse table ruler.
        ruler = core.g.reader.read()
        assert re.match(self.delimiter,ruler)
        self.parse_ruler(ruler)
        # Read the entire table.
        table = []
        while True:
            line = core.g.reader.read_next()
            # Table terminated by underline followed by a blank line or EOF.
            if len(table) > 0 and re.match(self.underline,table[-1]):
                if line in ('',None):
                    break;
            if line is None:
                raise EAsciiDoc('closing [%s] underline expected' % self.defname)
            table.append(core.g.reader.read())
        # EXPERIMENTAL: The number of lines in the table, requested by Benjamin Klum.
        self.attributes['rows'] = str(len(table))
        if self.check_msg:  # Skip if table definition was marked invalid.
            core.g.message.warning('skipping [%s] table: %s' % (self.defname,self.check_msg))
            return
        self.push_blockname('table')
        # Generate colwidths and colspecs.
        self.build_colspecs()
        # Generate headrows, footrows, bodyrows.
        # Headrow, footrow and bodyrow data replaces same named attributes in
        # the table markup template. In order to ensure this data does not get
        # a second attribute substitution (which would interfere with any
        # already substituted inline passthroughs) unique placeholders are used
        # (the tab character does not appear elsewhere since it is expanded on
        # input) which are replaced after template attribute substitution.
        headrows = footrows = []
        bodyrows,table = self.split_rows(table)
        if table:
            headrows = bodyrows
            bodyrows,table = self.split_rows(table)
            if table:
                footrows,table = self.split_rows(table)
        if headrows:
            headrows = self.parse_rows(headrows, self.headrow, self.headdata)
            headrows = core.g.writer.newline.join(headrows)
            self.attributes['headrows'] = '\x07headrows\x07'
        if footrows:
            footrows = self.parse_rows(footrows, self.footrow, self.footdata)
            footrows = core.g.writer.newline.join(footrows)
            self.attributes['footrows'] = '\x07footrows\x07'
        bodyrows = self.parse_rows(bodyrows, self.bodyrow, self.bodydata)
        bodyrows = core.g.writer.newline.join(bodyrows)
        self.attributes['bodyrows'] = '\x07bodyrows\x07'
        table = subs_attrs(core.g.config.sections[self.template],self.attributes)
        table = core.g.writer.newline.join(table)
        # Before we finish replace the table head, foot and body place holders
        # with the real data.
        if headrows:
            table = table.replace('\x07headrows\x07', headrows, 1)
        if footrows:
            table = table.replace('\x07footrows\x07', footrows, 1)
        table = table.replace('\x07bodyrows\x07', bodyrows, 1)
        core.g.writer.write(table,trace='table')
        self.pop_blockname()

class Tables_OLD(AbstractBlocks):
    """List of core.g.tables."""
    BLOCK_TYPE = Table_OLD
    PREFIX = 'old_tabledef-'
    def __init__(self):
        AbstractBlocks.__init__(self)
    def load(self,sections):
        AbstractBlocks.load(self,sections)
    def validate(self):
        # Does not call AbstractBlocks.validate().
        # Check we have a default table definition,
        for i in range(len(self.blocks)):
            if self.blocks[i].defname == 'old_tabledef-default':
                default = self.blocks[i]
                break
        else:
            raise EAsciiDoc('missing section: [OLD_tabledef-default]')
        # Set default table defaults.
        if default.format is None: default.subs = 'fixed'
        # Propagate defaults to unspecified table parameters.
        for b in self.blocks:
            if b is not default:
                if b.fillchar is None: b.fillchar = default.fillchar
                if b.format is None: b.format = default.format
                if b.template is None: b.template = default.template
                if b.colspec is None: b.colspec = default.colspec
                if b.headrow is None: b.headrow = default.headrow
                if b.footrow is None: b.footrow = default.footrow
                if b.bodyrow is None: b.bodyrow = default.bodyrow
                if b.headdata is None: b.headdata = default.headdata
                if b.footdata is None: b.footdata = default.footdata
                if b.bodydata is None: b.bodydata = default.bodydata
        # Check all tables have valid fill character.
        for b in self.blocks:
            if not b.fillchar or len(b.fillchar) != 1:
                raise EAsciiDoc('[%s] missing or illegal fillchar' % b.defname)
        # Build combined tables delimiter patterns and assign defaults.
        delimiters = []
        for b in self.blocks:
            # Ruler is:
            #   (ColStop,(ColWidth,FillChar+)?)+, FillChar+, TableWidth?
            b.delimiter = r'^(' + Table_OLD.COL_STOP \
                + r'(\d*|' + re.escape(b.fillchar) + r'*)' \
                + r')+' \
                + re.escape(b.fillchar) + r'+' \
                + '([\d\.]*)$'
            delimiters.append(b.delimiter)
            if not b.headrow:
                b.headrow = b.bodyrow
            if not b.footrow:
                b.footrow = b.bodyrow
            if not b.headdata:
                b.headdata = b.bodydata
            if not b.footdata:
                b.footdata = b.bodydata
        self.delimiters = re_join(delimiters)
        # Check table definitions are valid.
        for b in self.blocks:
            b.validate()
            if core.g.config.verbose:
                if b.check_msg:
                    core.g.message.warning('[%s] table definition: %s' % (b.defname,b.check_msg))

# End of deprecated old table classes.
#---------------------------------------------------------------------------
                        