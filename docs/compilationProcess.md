# Compilation Process

## Links
[github.com/markjasongalang/Lexical-Syntax-and-Semantic-Analyzer-in-GUI-using-Java](https://github.com/markjasongalang/Lexical-Syntax-and-Semantic-Analyzer-in-GUI-using-Java)

[docsbot.ai/prompts/programming/lexical-analyzer-with-gui](https://docsbot.ai/prompts/programming/lexical-analyzer-with-gui)

[dev.to/balapriya/abstract-syntax-tree-ast-explained-in-plain-english-1h38](https://dev.to/balapriya/abstract-syntax-tree-ast-explained-in-plain-english-1h38)

[keleshev.com/abstract-syntax-tree-an-example-in-c/](https://keleshev.com/abstract-syntax-tree-an-example-in-c/)

[www-old.cs.utah.edu/flux/flick/current/doc/guts/gutsch6.html](https://www-old.cs.utah.edu/flux/flick/current/doc/guts/gutsch6.html)

[docs.python.org/3/library/ast.html](https://docs.python.org/3/library/ast.html)

[en.wikipedia.org/wiki/Abstract_syntax_tree](https://en.wikipedia.org/wiki/Abstract_syntax_tree)


## Steps

### Lexical Analysis (Tokenization)
- Breaks the source code into tokens.
- Done by the lexer (also called the scanner).

### Syntactic Analysis (Parsing)
- The parser organizes tokens into an AST.
- Ensures the syntax follows the language grammar (e.g., {} must match in C++).

### Semantic Analysis
- Checks for logical errors (e.g., type mismatches, undefined variables).
- Ensures valid function calls (e.g., correct number of arguments).

### Intermediate Representation (IR) Generation
- Converts the AST into an intermediate representation (IR).
- Clang uses LLVM IR, while GCC has GIMPLE & RTL.

### Optimization
- The IR is optimized to remove redundant operations and improve performance.

### Code Generation
- The compiler translates IR into assembly code.

### Assembly and Linking
- The assembler converts assembly code into machine code (binary).
- The linker combines object files into the final executable.



## Reproduce Steps

### Tokenization
```bash
clang -Xclang -dump-tokens -fsyntax-only -nostdinc try.c > "$(basename try.c .c)_tokens.txt" 2>&1
```

Poissibly useless command to move it to a json (check for correct file names):
```bash
awk '
BEGIN { print "[" } 
{
    if (NR > 1) print ",";
    # Split the token string into type, value, and location
    type = $1;
    value = $2;
    location = substr($0, index($0,$3));  # Extract the location part (everything after the value)
    
    # Print the JSON object for each token
    printf "  { \"type\": \"%s\", \"value\": \"%s\", \"location\": \"%s\" }", type, value, location
} 
END { print "\n]" }' try_tokens.txt > try_tokens.json
```

### Parsing
Output on terminal
```bash
clang -Xclang -ast-dump -fsyntax-only victims/try.c
```

Output on .ansi
```bash
clang -Xclang -ast-dump -fsyntax-only victims/try.c > try_ast.ansi
```

Json output
```bash
clang -Xclang -ast-dump=json -fsyntax-only victims/try.c > try_ast.json
```
