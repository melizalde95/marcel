import subprocess
import textwrap

import marcel.util

# Text to be formatted consists of lines grouped into paragraphs.
# Paragraphs boundaries are implicit, or explicit, using markup.
# In either case, a paragraph has attributes controlling its
# wrapping and indenting. Within a paragraph, markup can be used to
# format text.
#
# Markup syntax is {FORMAT[:TEXT]}. The optional :TEXT is present within
# a paragraph only. Without :TEXT, the markup specifies paragraph
# formatting. FORMAT strings are case-insensitive.
#
# Paragraph boundaries:
#
# A paragraph is a sequence of lines, delimited by paragraph boundaries.
# {p} and {L} can be used to introduce explicit paragraph boundaries.
# In addition, a paragraph boundary is inferred where an empty line is
# adjacent to a non-empty line. An inferred paragraph boundary
# has default properties (indent = 0, wrap = True).
#
# A line containing only whitespace and paragraph markup only is ignored.
# It does not count as a line in the paragraph on either side.
#
# Paragraph formatting:
#
# FORMAT is one of:
#
#     - p[,indent=int][,wrap[=bool]]: Indicates a text paragraph. The
#       default value of indent is 0. The default value of wrap is
#       T, (boolean values are indicated by T for true, and F for false).
#
#     - L[,indent=int[:int]][,wrap[=bool]]: Indicates a multi-line
#       list item. The default indent is 2:4. If two indents are specified,
#       the first int is for the first line of the paragraph, and the
#       second int is for subsequent lines. The default value of wrap is True.
#
# Text formatting:
#
# The opening and closing braces must occur in the same paragraph.
# FORMAT is one of:
#
#     - r: Indicates a reference to an item being described, e.g a flag
#       in an op's help.
#
#     - b: bold. Useful for section titles.
#
#     - i: italic. Useful for introducing terminology.
#
#     - n: name. Highlighting a name defined in some other document,
#       e.g. an object or op that is relevant to the topic at hand, but
#       discussed in detail elsewhere.
#
#     - cRGB[bi]: color, where RGB values are 0..5, and bi are flags for
#       bold, italic
#
# The implementation treats paragraph and text markup separately. Paragraph markup
# is noted and used to define and format paragraphs. Text markup positions are noted
# and removed. After wrapping and indenting, colorization is performed using the positions
# recorded previously. Position is identified by the number of non-whitespace characters preceding
# the markup. THIS MEANS THAT MARKUP MUST NOT INTRODUCE NON-WHITESPACE TEXT. This constrains the
# design of the markup language. E.g., there can't be a list formatting markup item that introduces
# list markup text (bullets or numbers). This is fixable, but then the non-whitespace counters would
# need to be adjusted.


class TextPointer:

    MARKUP_OPEN = -1
    MARKUP_CLOSE = -2
    END = -3

    def __init__(self, text):
        self.text = text
        self.n = len(text)  # Includes escape chars
        self.p = 0
        self.ws = 0  # whitespace count up to and not including p

    def __eq__(self, other):
        return self.p == other.p

    def __ne__(self, other):
        return self.p != other.p

    def __lt__(self, other):
        return self.p < other.p

    def __le__(self, other):
        return self.p <= other.p

    def __gt__(self, other):
        return self.p > other.p

    def __ge__(self, other):
        return self.p >= other.p

    def peek(self):
        try:
            c = self.text[self.p]
            if c == '{':
                return TextPointer.MARKUP_OPEN
            elif c == '}':
                return TextPointer.MARKUP_CLOSE
            elif c == '\\':
                c = self.text[self.p + 1]
            return c
        except IndexError:
            return TextPointer.END

    def next(self):
        try:
            c = self.text[self.p]
            self.p += 1
            if c == '{':
                return TextPointer.MARKUP_OPEN
            elif c == '}':
                return TextPointer.MARKUP_CLOSE
            elif c == '\\':
                c = self.text[self.p]
                self.p += 1
            if not c.isspace():
                self.ws += 1
            return c
        except IndexError:
            return TextPointer.END

    def at_end(self):
        return self.p >= self.n

    def whitespace_count(self):
        return self.ws

    def advance_past(self, c):
        assert TextPointer.is_markup_boundary(c) or (type(c) is str and len(c) == 1), c
        next = self.next()
        while next != c and next != TextPointer.END:
            next = self.next()

    @staticmethod
    def is_markup_boundary(x):
        return x == TextPointer.MARKUP_OPEN or x == TextPointer.MARKUP_CLOSE


class Markup:

    def __init__(self, text):
        if not (text[0] == '{' and text[-1] == '}'):
            self.raise_invalid_formatting_exception()
        self.text = text

    def __repr__(self):
        return self.text

    def raise_invalid_formatting_exception(self):
        raise Exception(f'Invalid formatting specification: {self.text}')


class ParagraphMarkup(Markup):

    def __init__(self, text):
        super().__init__(text)
        self.code = None
        self.indent1 = None
        self.indent2 = None
        self.wrap = None
        self.parse_paragraph_formatting()

    def parse_paragraph_formatting(self):
        parts = self.text[1:-1].split(',')
        self.code = parts[0].lower()
        if len(self.code) > 1:
            self.raise_invalid_formatting_exception()
        assert self.code in 'pl', self.code
        for part in parts[1:]:
            tokens = part.split('=')
            if len(tokens) == 1:
                if tokens[0].lower() == 'wrap':
                    self.wrap = True
                else:
                    self.raise_invalid_formatting_exception()
            elif len(tokens) == 2:
                key, value = tokens
                key = key.lower()
                if key == 'indent':
                    try:
                        indents = [int(x) for x in value.split(':')]
                        if len(indents) < 1 or len(indents) > 2:
                            self.raise_invalid_formatting_exception()
                        self.indent1 = indents[0]
                        self.indent2 = indents[1] if len(indents) > 1 else self.indent1
                    except ValueError:
                        self.raise_invalid_formatting_exception()
                elif key == 'wrap':
                    self.wrap = value == 'T'
            else:
                self.raise_invalid_formatting_exception()
        if self.indent1 is None:
            self.indent1, self.indent2 = (0, 0) if self.code == 'p' else (2, 4)
        if self.wrap is None:
            self.wrap = True


class TextMarkup(Markup):

    def __init__(self, text, open, preceding_non_ws_count, color_scheme):
        self.preceding_non_ws_count = preceding_non_ws_count
        # Parse the formatting, and get past the colon
        self.color, text_start = self.formatting(text, open + 1, color_scheme)
        # Find the closing } of the markup, and count non-whitespace characters
        self.non_ws_count = 0
        close = None
        n = len(text)
        p = text_start
        while p < n and close is None:
            c = text[p]
            if c == '}' and text[p - 1] != '\\':
                close = p
            else:
                if not c.isspace():
                    self.non_ws_count += 1
                p += 1
        if close is None:
            self.text = text[open:min(open + 10, n)]  # For exception message
            self.raise_invalid_formatting_exception()
        close += 1
        super().__init__(text[open:close])
        self.content = text[text_start:close-1]
        self.size = close - open  #  { ... }

    def __repr__(self):
        return f'({self.preceding_non_ws_count} : {self.content} : {self.non_ws_count})'

    def formatting(self, text, p, color_scheme):
        color = None
        try:
            c = text[p]
            p += 1
            if c in 'rbin':
                if text[p] != ':':
                    self.raise_invalid_formatting_exception()
                p += 1
                if c == 'r':
                    color = color_scheme.help_reference
                elif c == 'b':
                    color = color_scheme.help_bold
                elif c == 'i':
                    color = color_scheme.help_italic
                elif c == 'n':
                    color = color_scheme.help_name
            elif c == 'c':
                r, g, b = int(text[p]), int(text[p+1]), int(text[p+2])
                p += 3
                colon = text.find(':', p)
                if colon == -1 or colon > p + 2:
                    self.raise_invalid_formatting_exception()
                style = 0
                for x in text(p, colon):
                    if x == 'b':
                        style = style | color_scheme.bold()
                    elif x == 'i':
                        style = style | color_scheme.italic()
                    else:
                        self.raise_invalid_formatting_exception()
                p = colon + 1
                color = color_scheme.color(r, g, b, style)
            else:
                self.raise_invalid_formatting_exception()
            assert color is not None
            return color, p
        except ValueError:
            self.raise_invalid_formatting_exception()
        except IndexError:
            self.raise_invalid_formatting_exception()

    @staticmethod
    def starts_here(text, p):
        return text[p] == '{' and (p == 0 or text[p - 1] != '\\')


class Paragraph:
    BLANK_LINE = ''
    DEFAULT_MARKUP = '{p}'

    def __init__(self, help_formatter, markup=DEFAULT_MARKUP):
        self.help_formatter = help_formatter
        self.lines = []
        self.paragraph_markup = ParagraphMarkup(markup)
        self.text_markup = None
        self.plaintext = None
        self.wrapped = None
        self.indented = None

    def __repr__(self):
        text = '\n'.join(self.lines)
        return f'{self.paragraph_markup}[{text}]'

    def append(self, line):
        line = Paragraph.normalize(line)
        if len(self.lines) == 0 or (self.lines[-1] is Paragraph.BLANK_LINE) == (line is Paragraph.BLANK_LINE):
            self.lines.append(line)
            return True
        else:
            return False

    def remove_markup(self):
        self.text_markup = []
        self.plaintext = ''
        text = '\n'.join(self.lines)
        n = len(text)
        non_ws_count = 0
        p = 0
        while p < n:
            if TextMarkup.starts_here(text, p):
                markup = TextMarkup(text, p, non_ws_count, self.help_formatter.color_scheme)
                self.text_markup.append(markup)
                non_ws_count += markup.non_ws_count
                self.plaintext += markup.content
                p += markup.size  # includes the markup notation itself
            else:
                if not text[p].isspace():
                    non_ws_count += 1
                self.plaintext += text[p]
                p += 1

    def wrap(self):
        if self.paragraph_markup.wrap:
            # Trim lines. textwrap.wrap should do this (based on my understanding of the docs)
            # but doesn't seem to.
            self.trim_lines_to_be_wrapped()
            indent = self.paragraph_markup.indent1
            columns = self.help_formatter.help_columns - indent
            self.wrapped = textwrap.wrap(self.plaintext,
                                         width=columns,
                                         break_long_words=False)
        else:
            self.wrapped = self.plaintext.split('\n')

    def trim_lines_to_be_wrapped(self):
        trimmed = []
        for line in self.plaintext.split('\n'):
            trimmed.append(line.strip())
        self.plaintext = ' '.join(trimmed)

    def indent(self):
        indent = self.paragraph_markup.indent1
        if indent == 0:
            indented_lines = self.wrapped
        else:
            indented_lines = []
            padding1 = ' ' * indent
            padding2 = ' ' * self.paragraph_markup.indent2
            padding = padding1
            for line in self.wrapped:
                indented_lines.append(padding + line)
                padding = padding2
        self.indented = '\n'.join(indented_lines)

    def format(self):
        formatted = ''
        text = self.indented
        n = len(text)
        p = 0  # position in text
        format_function = self.help_formatter.format_function
        m = 0  # markup index
        non_ws_count = 0
        while p < n and m < len(self.text_markup):
            markup = self.text_markup[m]
            while non_ws_count < markup.preceding_non_ws_count:
                c = text[p]
                p += 1
                formatted += c
                if not c.isspace():
                    non_ws_count += 1
            # There may be some whitespace
            while text[p].isspace():
                formatted += text[p]
                p += 1
            # Process markup. Don't use markup.context, as formatting may have modified it (bug 39).
            markup_text = ''
            markup_non_ws_count = 0
            while markup_non_ws_count < markup.non_ws_count:
                c = text[p]
                p += 1
                markup_text += c
                if not c.isspace():
                    markup_non_ws_count += 1
            formatted += format_function(markup_text, markup.color)
            non_ws_count += markup_non_ws_count
            m += 1
        formatted += text[p:]
        return formatted

    @staticmethod
    def normalize(line):
        return Paragraph.BLANK_LINE if len(line.strip()) == 0 else line


class HelpFormatter:

    RIGHT_MARGIN = 0.10

    def __init__(self, color_scheme, format_function=marcel.util.colorize):
        self.color_scheme = color_scheme
        self.format_function = format_function
        self.help_columns = None

    def format(self, text):
        self.find_console_width()
        if text is None:
            return None
        blocks = self.find_explicit_paragraph_boundaries(text)
        paragraphs = self.make_implicit_paragraph_boundaries_explicit(blocks)
        buffer = []
        for paragraph in paragraphs:
            paragraph.remove_markup()
            paragraph.wrap()
            paragraph.indent()
            buffer.append(paragraph.format())
        return '\n'.join(buffer)

    # Input: marked-up text
    # Output: List of text blocks interspersed with Paragraphs from paragraph markup ({p}, {L}).
    def find_explicit_paragraph_boundaries(self, text):
        blocks = []
        p = 0
        n = len(text)
        while p < n:
            open, close = HelpFormatter.find_paragraph_markup(text, p)
            if open == -1:
                blocks.append(text[p:])
                p = n
            else:
                if p < open:
                    blocks.append(text[p:open])
                blocks.append(Paragraph(self, text[open:close]))
                # Skip whitespace after close, up to and including the first \n
                p = close
                while p < n and text[p].isspace() and text[p] != '\n':
                    p += 1
                if p < n and text[p] == '\n':
                    p += 1
        return blocks

    # Input: Array of text blocks and Paragraphs.
    # Output: Array of Paragraphs. A text block may give rise to multiple Paragraphs due to implicit boundaries.
    def make_implicit_paragraph_boundaries_explicit(self, blocks):
        paragraphs = []
        n = len(blocks)
        paragraph = None
        # Make sure first paragraph is marked
        if n > 0 and not isinstance(blocks[0], Paragraph):
            paragraph = Paragraph(self)
            paragraphs.append(paragraph)
        b = 0
        while b < n:
            block = blocks[b]
            b += 1
            if isinstance(block, Paragraph):
                paragraph = block
                paragraphs.append(paragraph)
            else:
                lines = block.split('\n')
                if HelpFormatter.ignore(lines[-1]):
                    del lines[-1]
                for line in lines:
                    appended = paragraph.append(line)
                    if not appended:
                        # Line rejected because it doesn't match the lines of the current paragraph.
                        # Start a new one.
                        paragraph = Paragraph(self)
                        paragraphs.append(paragraph)
                        appended = paragraph.append(line)
                        assert appended
        return paragraphs

    def find_console_width(self):
        process = subprocess.Popen('stty size',
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL,
                                   universal_newlines=True)
        process.wait()
        stdout, _ = process.communicate()
        try:
            console_columns = int(stdout.split()[1])
        except Exception:
            # Not running in a console.
            console_columns = 70  # Default for textwrap module
        self.help_columns = int((1 - HelpFormatter.RIGHT_MARGIN) * console_columns)

    @staticmethod
    def find_paragraph_markup(text, p):
        open = text.find('{', p)
        while open != -1 and not HelpFormatter.is_paragraph_markup_open(text, open):
            open = text.find('{', open + 1)
        if open == -1:
            return -1, None
        close = text.find('}', open)
        while not HelpFormatter.is_paragraph_markup_close(text, close):
            close = text.find('}', close)
        if close == -1:
            raise Exception(f'Unterminated markup at position {p}')
        return open, close + 1

    @staticmethod
    def is_paragraph_markup_open(text, p):
        assert text[p] == '{'
        if p > 0 and text[p - 1] == '\\':
            return False
        return p + 1 < len(text) and text[p + 1] in 'pPlL'

    @staticmethod
    def is_paragraph_markup_close(text, p):
        assert p > 0
        assert text[p] == '}'
        return text[p - 1] != '\\'

    # ignore if all whitespace without \n
    @staticmethod
    def ignore(s):
        return s.isspace() and s.count('\n') == 0
