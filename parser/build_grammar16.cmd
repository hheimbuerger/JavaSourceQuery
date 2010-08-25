java -Xmx512m -cp antlr-3.1.2\antlr-3.1.2.jar org.antlr.Tool -Xconversiontimeout 100000 -o ..\src\javagrammar16 Java16.g

@echo.
@echo ANTLR 3.1.2 seems to generate invalid Python parsers, a type declaration slips in at one point. Please replace all instances of "CommonTree modifiers" with "modifiers" in JavaParser.py.
@echo.
@echo This parser currently is not supported, as there is no tree parser for it.
