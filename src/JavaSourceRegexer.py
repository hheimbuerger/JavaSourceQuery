import re
import sys
import antlr3
from javagrammar15.JavaLexer import JavaLexer
from javagrammar15.JavaParser import JavaParser
from javagrammar15.JavaTreeParser import JavaTreeParser

input = """            package test;
            import java.util.String;

            public class Test {
                public static void main(String[] args, int testArg) {
                    System.out.println("Hello world!");
                }
            }"""

ALIASES = {
           'CLASS_DECL': ('CLASS_TOP_LEVEL_SCOPE',),
           'TOP_LEVEL_CLASS': ('CLASS_TOP_LEVEL_SCOPE',),
           'METHOD_DECL': ('FUNCTION_METHOD_DECL', 'VOID_METHOD_DECL',),
           'PARAMETER_LIST': ('FORMAL_PARAM_LIST',),
           'PARAMETER': ('FORMAL_PARAM_STD_DECL',),
          }

def readAvailableTokens():
    with open('javagrammar15/JavaTreeParser.tokens', 'r') as f:
        lines = f.readlines()
    availableTokens = {}
    for line in lines:
        (token, key) = re.match('(.*)=(\d+)', line).groups()
        availableTokens[token] = int(key)
    return availableTokens
TOKENS = readAvailableTokens()

#class SourceHasBeenInvalidatedError(Exception):
#    def __init__(self):
#        self.args = ['This source has been invalidated.']

class JavaSource:
    def __init__(self, text_or_stream):
        # obtain a stream to the source code
        if type(text_or_stream) == str:
            cStream = antlr3.StringStream(text_or_stream)
        else:
            cStream = antlr3.InputStream(text_or_stream)
        #cStream = antlr3.FileStream('../test/NotificationServiceImpl.java')
        
        self._parse(cStream)

    def _parse(self, cStream):
        # run it through the lexer and parser
        lexer = JavaLexer(cStream)
        self.tokenStream = antlr3.CommonTokenStream(lexer)
        parser = JavaParser(self.tokenStream)
        r = parser.javaSource()

        # now build the tree
        nodes = antlr3.tree.CommonTreeNodeStream(r.tree)
        nodes.setTokenStream(self.tokenStream)
        walker = JavaTreeParser(nodes)
        walker.javaSource()

        self.tree = r.tree

    def getTree(self):
        return self.tree

    def getSource(self, tokenStream):
        return ''.join(map(lambda x: x.text, tokenStream))

    def getTokenStream(self):
        return self.tokenStream.tokens

    def setTokenStream(self, newTokenStream):
        sys.stdout.write("Need to reparse source...")
        self._parse(antlr3.StringStream(self.getSource(newTokenStream)))
        print(" done.")

    def __repr__(self):
        return 'JavaSource[\n' + self.getSource(self.tokenStream.tokens) + '\n]'

class QueryPart:
    def __init__(self, strRepr, options):
        if strRepr.find('=') != -1:
            (typePart, self.textFilter) = strRepr.split('=')
        else:
            (typePart, self.textFilter) = (strRepr, None)
        strTypes = ALIASES[typePart] if ALIASES.has_key(typePart) else (typePart,)
        self.types = map(lambda x: TOKENS[x], strTypes)
        self.isChildSelector = 'CHILD_SELECTOR' in options

    def __repr__(self):
        return 'QueryPart(%s)' % (','.join(map(str, self.types)) + ('=' + self.textFilter if self.textFilter else ''))

class QueryMatch:
    """ a proxy class for nodes """
    def __init__(self, query, node):
        self.query = query
        self.node = node

    def getSource(self):
        return ''.join(map(lambda x: x.text, self.query.source.getTokenStream()[self.node.tokenStartIndex:self.node.tokenStopIndex+1]))

    def getTree(self, root=None, indent=0):
        if not root: root = self.node
        tokenType = [key for key,value in TOKENS.items() if value==root.type][0]
        return '{indent}+ {type}{text}\n'.format(indent=(' ' * indent*2), type=tokenType, text='({})'.format(root.token.text) if tokenType != root.token.text else '') \
             + ''.join(map(lambda x: self.getTree(x, indent+1), root.children))

    def __repr__(self):
        if hasattr(self.node, 'line'):
            return 'QueryMatch(%s@%i:%i)' % (self.node.text, self.node.line, self.node.charPositionInLine+1)
        else:
            return 'QueryMatch(%s)' % (self.node.text)

    type = property(fget=lambda self: self.node.type)
    text = property(fget=lambda self: self.node.text)
    startLine = property(fget=lambda self: self.node.line)
    startColumn = property(fget=lambda self: self.node.charPositionInLine)
    children = property(fget=lambda self: self.node.children)
    tokenStartIndex = property(fget=lambda self: self.node.tokenStartIndex)
    tokenStopIndex = property(fget=lambda self: self.node.tokenStopIndex)

class JavaSourceQuery:
    def __init__(self, source, nodes=None):
        if isinstance(source, JavaSource):
            self.source = source
            self.nodes = nodes
        else:
            self.source = JavaSource(source)
            self.nodes = map(lambda x: QueryMatch(self, x), self.source.getTree().children)

    def _parse(self, query):
        queryPartList = []
        nextIsChildSelector = False
        for arg in query.split(' '):
            options = []
            if nextIsChildSelector:
                options.append('CHILD_SELECTOR')
                nextIsChildSelector = False
            if arg == '>':
                nextIsChildSelector = True
                continue
            queryPartList.append(QueryPart(arg, options))
        return queryPartList

    def _matchOne(self, node, queryPart):
        if node.type in queryPart.types:
            return not queryPart.textFilter or re.match(queryPart.textFilter, node.text)
        return False

    def _match(self, nodes, query):
        # if we've reached the end of the query, return the current tree node as a match
        if len(query) == 0:
            raise Exception('disallowing empty queries for now, but they might make sense later on')

        # otherwise, try to match the element at the top of the query stack against the current nodes
        hasMatched = False
        for node in nodes:
            if self._matchOne(node, query[0]):
                # if we're through with the query, yield a result, otherwise recursively call the generator
                if len(query)-1 == 0:
                    yield node
                else:
                    for match in self._match(node.children, query[1:]):
                        hasMatched = True
                        yield match

        # implicit Kleene at every level
        if not query[0].isChildSelector:
            if not hasMatched:
                for node in nodes:
                    for match in self._match(node.children, query):
                        yield match

    def _filterBySelector(self, query):
        parsedQuery = self._parse(query)
        return JavaSourceQuery(self.source, filter(lambda x: len(list(self._match(x.children, parsedQuery))) > 0, self.nodes))

    def _filterByFunction(self, func):
        return JavaSourceQuery(self.source, filter(func, self.nodes))

    def match(self, query):
        parsedQuery = self._parse(query)
        #print '[DEBUG] parsedQuery: ' + str(parsedQuery)
        return JavaSourceQuery(self.source, map(lambda x: QueryMatch(self, x), self._match(self.nodes, parsedQuery)))

    def filter(self, query):
        return self._filterBySelector(query) if type(query) == str else self._filterByFunction(query)

    def replace(self, replacement):
        # build a new token stream, replacing the selected tokens with dummy tokens of the replacement
        oldTokenStream = self.source.getTokenStream()
        newTokenStream = []
        currentPos = 0
        for matchingNode in self.nodes:
            # append the tokens between the last match and this one
            newTokenStream.extend(oldTokenStream[currentPos:matchingNode.node.tokenStartIndex])
            # append the new dummy token with the replacement
            replacementCode = replacement if type(replacement) == str else replacement(matchingNode)
            newTokenStream.append(antlr3.tokens.CommonToken(type=-1, text=replacementCode))
            # account for the unmodified tokens between the last match and this one
            currentPos += matchingNode.node.tokenStartIndex - currentPos
            # account for the tokens replaced by this replacement
            currentPos += matchingNode.node.tokenStopIndex - matchingNode.node.tokenStartIndex + 1
        # append all the tokens after the last replacement
        newTokenStream.extend(oldTokenStream[currentPos:])

        # assign the new token stream to the source
        self.source.setTokenStream(newTokenStream)

    def getSource(self):
        return '\n'.join(n.getSource() for n in self.nodes)
    
    def getTree(self):
        return '\n'.join(n.getTree() for n in self.nodes)

    def __getitem__(self, index):
        return self.nodes[index]

    def __call__(self, query):
        return self.match(query)

    def __repr__(self):
        return 'JavaSourceQuery[%s]' % ', '.join(map(str, self.nodes))

q = JavaSourceQuery(open('../test/QueryTest.java'))
#q = JavaSourceQuery(input)
print
#print(q.source)
print(q.getTree())
print(q('IDENT=fjdkslfjl'))
#print(q('CLASS_TOP_LEVEL_SCOPE METHOD_DECL IDENT=create.*')
#print(q('TOP_LEVEL_CLASS PARAMETER').getSource())
#print(q('TOP_LEVEL_CLASS PARAMETER'))
#print(q('TOP_LEVEL_CLASS PARAMETER').filter('QUALIFIED_TYPE_IDENT'))
#print(q('TOP_LEVEL_CLASS PARAMETER').filter('QUALIFIED_TYPE_IDENT'))[0].getNodeTree()
#print(q('CLASS_TOP_LEVEL_SCOPE FORMAL_PARAM_STD_DECL').filter('IDENT=args').replace('TEST'))
#print(q('CLASS_TOP_LEVEL_SCOPE METHOD_DECL'))
#q('CLASS_TOP_LEVEL_SCOPE METHOD_DECL FORMAL_PARAM_STD_DECL').replace('TEST')
#print(q.source)
#print
#print(q('CLASS_TOP_LEVEL_SCOPE METHOD_DECL'))
#print(q('VAR_DECLARATION TYPE IDENT').replace('abc'))
#print(map(lambda node: node.startIndex, q.matchedNodes))
#print q.text
#print q.startLine
#print q.startLine
#print q.startColumn
